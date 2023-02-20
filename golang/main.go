package main

import (
	"context"
	"database/sql"
	"encoding/json"
	"errors"
	"fmt"
	"log"
	"os"
	"strings"
	"time"

	_ "github.com/lib/pq"
	"github.com/twmb/franz-go/pkg/kgo"
	"github.com/twmb/franz-go/pkg/sasl/plain"
)

const batchSize = 1000

type Event struct {
	OrganizationID int                    `json:"organization_id,omitempty"`
	CustID         string                 `json:"cust_id,omitempty"`
	EventName      string                 `json:"event_name,omitempty"`
	TimeCreated    time.Time              `json:"time_created,omitempty"`
	Properties     map[string]interface{} `json:"properties,omitempty"`
	IdempotencyID  string                 `json:"idempotency_id,omitempty"`
	InsertedAt     time.Time              `json:"inserted_at,omitempty"`
}

type StreamEvents struct {
	Events         *[]Event `json:"events"`
	OrganizationID int64    `json:"organization_id"`
	Event          *Event   `json:"event"`
}

type batch struct {
	tx              *sql.Tx
	insertStatement *sql.Stmt
	count           int
}

func (b *batch) addRecord(event *Event) (bool, error) {
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
		event.InsertedAt,
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
	opts := []kgo.Opt{
		kgo.SeedBrokers(seeds...),
		kgo.ConsumerGroup("default"),
		kgo.ConsumeTopics(kafkaTopic),
		kgo.DisableAutoCommit(),
	}
	if saslUsername != "" && saslPassword != "" {
		log.Printf("Using SASL authentication with username: %s, password: %s", saslUsername, saslPassword)
		opts = append(opts, kgo.SASL(plain.Auth{
			User: saslUsername,
			Pass: saslPassword,
		}.AsMechanism()))
	}
	cl, err := kgo.NewClient(opts...)

	if err != nil {
		panic(err)
	}

	defer cl.Close()

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
	db, err := sql.Open("postgres", dbURL)
	if err != nil {
		log.Printf("Error opening database url: %s", dbURL)
		panic(err)
	}
	defer db.Close()

	insertStatement, err := db.Prepare("INSERT INTO metering_billing_usageevent (organization_id, cust_id, event_name, time_created, properties, idempotency_id, inserted_at) VALUES ($1, $2, $3, $4, $5, $6, $7) ON CONFLICT DO NOTHING")
	if err != nil {
		panic(err)
	}
	defer insertStatement.Close()
	log.Printf("Connected to database: %s", dbURL)
	for {
		fetches := cl.PollFetches(ctx)
		if fetches == nil {
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
		batch := &batch{
			tx:              tx,
			insertStatement: insertStatement,
		}

		fetches.EachRecord(func(r *kgo.Record) {
			log.Printf("Received record: %s\n", r.Value)
			var streamEvents StreamEvents
			err := json.Unmarshal(r.Value, &streamEvents)
			if err != nil {
				log.Printf("Error unmarshalling event: %s\n", err)
				// since we check in the prevuious statement that the event has the correct format, an error unmarshalling should be a fatal error
				panic(err)
			}

			if streamEvents.Event == nil {
				if streamEvents.Events != nil {
					if len(*streamEvents.Events) > 0 {
						streamEvents.Event = &(*streamEvents.Events)[0]
					} else {
						log.Println("Error: event is nil and events is empty")
						panic(fmt.Errorf("event is nil and events is empty"))
					}
				} else {
					log.Println("Error: both event and events fields are missing from stream_events")
					panic(fmt.Errorf("both event and events fields are missing from stream_events"))
				}
			}

			event := streamEvents.Event
			event.InsertedAt = time.Now()

			if committed, err := batch.addRecord(event); err != nil {
				//only thing that can go wrong in batch is either bugs in the code or a serious database failure/network partition of some kind. Because the usual referential integrity issues are already dealt with (on conflict do nothing), all that's left is bad stuff.
				log.Printf("Error inserting event: %s\n", err)
				panic(err)
			} else if committed {
				if err := cl.CommitUncommittedOffsets(context.Background()); err != nil {
					// this is a fatal error
					log.Printf("commit records failed: %v", err)
					panic(fmt.Errorf("commit records failed: %w", err))
				}
			}
		})

		if batch.count > 0 {
			if err := tx.Commit(); err != nil {
				// again, this should be a fatal error
				log.Printf("Error inserting events into database: %s\n", err)
				panic(err)
			}
			if err := cl.CommitUncommittedOffsets(context.Background()); err != nil {
				// this is a fatal error
				log.Printf("commit records failed: %v", err)
				panic(fmt.Errorf("commit records failed: %w", err))
			}
		} else {
			if err := tx.Rollback(); err != nil {
				// again, this should be a fatal error
				log.Printf("Error rolling back transaction: %s\n", err)
				panic(err)
			}
		}

	}
}
