package main

import (
	"context"
	"crypto/tls"
	"database/sql"
	"encoding/json"
	"errors"
	"fmt"
	"log"
	"net"
	"os"
	"strings"
	"time"

	_ "github.com/lib/pq"
	"github.com/posthog/posthog-go"
	"github.com/twmb/franz-go/pkg/kgo"
	"github.com/twmb/franz-go/pkg/sasl/scram"
	"github.com/uselotus/lotus/go/pkg/types"
)

const batchSize = 2

type StreamEvents struct {
	OrganizationID int64                `json:"organization_id"`
	Event          *types.VerifiedEvent `json:"event"`
}

type insertBatch struct {
	tx              *sql.Tx
	insertStatement *sql.Stmt
	count           int
}

func (b *insertBatch) addRecord(event *types.VerifiedEvent) (bool, error) {
	propertiesJSON, errJSON := json.Marshal(event.Properties)
	if errJSON != nil {
		log.Printf("Error encoding properties to JSON: %s\n", errJSON)
		return false, errJSON
	}

	_, err := b.insertStatement.Exec(
		event.OrganizationID,
		event.CustID,
		event.EventName,
		event.TimeCreated,
		propertiesJSON,
		event.IdempotencyID,
	)
	if err != nil {
		return false, err
	}

	b.count++
	if b.count >= batchSize {
		if err := b.tx.Commit(); err != nil {
			return false, err
		}
		b.count = 0
		return true, nil
	}

	return false, nil
}
func main() {
	log.SetOutput(os.Stdout)
	fmt.Printf("Starting event-guidance\n")

	// setup kafkda envs
	var kafkaURL string
	if kafkaURL = os.Getenv("KAFKA_URL"); kafkaURL == "" {
		kafkaURL = "localhost:9092"
	}

	var kafkaTopic string
	if kafkaTopic = os.Getenv("EVENTS_TOPIC"); kafkaTopic == "" {
		kafkaTopic = "test-topic"
	}
	saslUsername := os.Getenv("KAFKA_SASL_USERNAME")
	saslPassword := os.Getenv("KAFKA_SASL_PASSWORD")
	seeds := []string{kafkaURL}
	ctx := context.Background()

	// Setup kafka consumer
	consumerGroup := os.Getenv("KAFKA_CONSUMER_GROUP")
	if consumerGroup == "" {
		consumerGroup = "default"
	}
	opts := []kgo.Opt{
		kgo.SeedBrokers(seeds...),
		kgo.ConsumerGroup(consumerGroup),
		kgo.ConsumeTopics(kafkaTopic),
		kgo.DisableAutoCommit(),
	}

	if saslUsername != "" && saslPassword != "" {
		opts = append(opts, kgo.SASL(scram.Auth{
			User: saslUsername,
			Pass: saslPassword,
		}.AsSha512Mechanism()))
		// Configure TLS. Uses SystemCertPool for RootCAs by default.
		tlsDialer := &tls.Dialer{NetDialer: &net.Dialer{Timeout: 10 * time.Second}}
		opts = append(opts, kgo.Dialer(tlsDialer.DialContext))
	}

	cl, err := kgo.NewClient(opts...)
	if err != nil {
		panic(err)
	}
	defer cl.Close()

	// Setup postgres connection
	var dbURL string
	if dbURL = os.Getenv("DATABASE_URL"); dbURL == "" {
		host := "localhost"
		dockerized := strings.ToLower(os.Getenv("DOCKERIZED"))
		if !(dockerized == "false" || dockerized == "0" || dockerized == "no" || dockerized == "f" || dockerized == "") {
			host = "db"
		}

		pgUser := os.Getenv("POSTGRES_USER")
		if pgUser == "" {
			pgUser = "lotus"
		}

		pgPassword := os.Getenv("POSTGRES_PASSWORD")
		if pgPassword == "" {
			pgPassword = "lotus"
		}
		pgDB := os.Getenv("POSTGRES_DB")
		if pgDB == "" {
			pgDB = "lotus"
		}

		dbURL = fmt.Sprintf("postgres://%s:%s@%s:5432/%s?sslmode=disable", pgUser, pgPassword, host, pgDB)
	}
	log.Printf("Connecting to database: %s", dbURL)
	db, err := sql.Open("postgres", dbURL)
	if err != nil {
		log.Printf("Error opening database url: %s", dbURL)
		panic(err)
	}
	defer db.Close()

	// Setup prepared statement
	insertStatement, err := db.Prepare("SELECT insert_metric($1, $2, $3, $4, $5, $6)")

	if err != nil {
		panic(err)
	}

	defer insertStatement.Close()

	// setup posthog envs + client
	phWorks := false
	phKey := os.Getenv("POSTHOG_API_KEY")
	phClient, phErr := posthog.NewWithConfig(
		phKey,
		posthog.Config{},
	)
	if phKey == "" {
		log.Printf("No posthog key found. Skipping posthog events.")
	} else {
		if phErr == nil {
			phWorks = true
			defer phClient.Close()
			log.Printf("Posthog client created successfully")
		} else {
			log.Printf("Error creating posthog client: %s", phErr)
		}
	}

	// confirm
	fmt.Printf("Starting event fetching\n")

	for {
		log.Print("Before polling for messages...")
		fetches := cl.PollFetches(ctx)
		log.Print("Polling for messages...")

		if fetches == nil {
			log.Print("No fetches returned, retrying in 1s")
			continue
		}

		if fetches.IsClientClosed() {
			panic(errors.New("client is closed"))
		}

		if errs := fetches.Errors(); len(errs) > 0 {
			// All errors are retried internally when fetching, but non-retriable errors are
			// returned from polls so that users can notice and take action.
			log.Printf("Error fetching: %v\n", errs)
			panic(fmt.Sprint(errs))
		}

		tx, err := db.Begin()

		if err != nil {
			log.Printf("Error starting transaction: %s\n", err)
			panic(err)
		}

		batch := &insertBatch{
			tx:              tx,
			insertStatement: insertStatement,
			count:           0,
		}

		// make a map of organizationID (bigint) ro integers to keep track of the number of events we have processed for each organization
		processedEvents := make(map[int64]int)

		fetches.EachRecord(func(r *kgo.Record) {
			log.Printf("Received record: %s\n", r.Value)
			//extract event from kafka message
			var streamEvents StreamEvents
			err := json.Unmarshal(r.Value, &streamEvents)
			if err != nil {
				log.Printf("Error unmarshalling event: %s\n", err)
				// since we check in the previous step in the pipeline that the event has the correct format, an error unmarshalling should be a fatal error
				panic(err)
			}
			if streamEvents.Event == nil {
				log.Printf("event from OrganizationID %d is empty", streamEvents.OrganizationID)
				panic(fmt.Errorf("event from OrganizationID %d is empty", streamEvents.OrganizationID))
			}
			event := streamEvents.Event

			// commit the record
			if committed, err := batch.addRecord(event); err != nil {
				//only thing that can go wrong in batch is either bugs in the code or a serious database failure/network partition of some kind. Because the usual referential integrity issues are already dealt with (on conflict do nothing), all that's left is bad stuff.
				log.Printf("Error inserting event: %s\n", err)
				panic(err)
			} else {
				if committed {
					// commit offsets
					if err := cl.CommitUncommittedOffsets(context.Background()); err != nil {
						// this is a fatal error
						log.Printf("commit records failed: %v", err)
						panic(fmt.Errorf("commit records failed: %w", err))
					}

					// start a new transaction and reset the batch
					tx, err := db.Begin()
					if err != nil {
						log.Printf("Error starting transaction: %s\n", err)
						panic(err)
					}
					batch.tx = tx
				}

				// send posthog event if orgID has changed or we've reached batchSize (and set batch.count to 0)
				processedEvents[event.OrganizationID]++
			}

		})

		if batch.count > 0 {
			if err := tx.Commit(); err != nil {
				// again, this should be a fatal error
				log.Printf("Error inserting events into database: %s\n", err)
				panic(err)
			} else {
				if err := cl.CommitUncommittedOffsets(context.Background()); err != nil {
					// this is a fatal error
					log.Printf("commit records failed: %v", err)
					panic(fmt.Errorf("commit records failed: %w", err))
				}
			}
		}

		// send posthog event
		if phWorks {
			posthogTrack(phClient, processedEvents)
		}

	}
}

func posthogTrack(phClient posthog.Client, processedEvents map[int64]int) {
	// send posthog event
	for organizationID, numEvents := range processedEvents {
		phClient.Enqueue(posthog.Capture{
			DistinctId: fmt.Sprintf("%d (API Key)", organizationID),
			Event:      "track_event",
			Properties: posthog.NewProperties().
				Set("num_events", numEvents),
		})
	}
}
