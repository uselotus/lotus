package main

import (
	"context"
	"database/sql"
	"encoding/json"
	"errors"
	"fmt"
	"os"
	"strings"
	"time"

	_ "github.com/lib/pq"
	"github.com/twmb/franz-go/pkg/kgo"
)

const batchSize = 1000

type Event struct {
	OrganizationID int                    `json:"organization_id,omitempty"`
	CustomerID     *int                   `json:"customer_id,omitempty"`
	CustID         string                 `json:"cust_id,omitempty"`
	EventName      string                 `json:"event_name,omitempty"`
	TimeCreated    time.Time              `json:"time_created,omitempty"`
	Properties     map[string]interface{} `json:"properties,omitempty"`
	IdempotencyID  string                 `json:"idempotency_id,omitempty"`
	InsertedAt     time.Time              `json:"inserted_at,omitempty"`
}

type StreamEvents struct {
	Events         []Event `json:"events"`
	OrganizationID int64   `json:"organization_id"`
	Event          *Event  `json:"event"`
}

type batch struct {
	tx         *sql.Tx
	insertStmt *sql.Stmt
	count      int
}

func (b *batch) addRecord(event *Event) error {
	propertiesJSON, errJSON := json.Marshal(event.Properties)
	if errJSON != nil {
		fmt.Printf("Error encoding properties to JSON: %s\n", errJSON)
		return errJSON
	}

	_, err := b.insertStmt.Exec(event.OrganizationID, event.CustomerID, event.CustID, event.EventName, event.TimeCreated, propertiesJSON, event.IdempotencyID, event.InsertedAt)
	if err != nil {
		return err
	}

	b.count++
	if b.count >= batchSize {
		if err := b.tx.Commit(); err != nil {
			return err
		}
		b.count = 0
	}

	return nil
}

func main() {
	var kafkaURL string
	if kafkaURL = os.Getenv("KAFKA_URL"); kafkaURL == "" {
		kafkaURL = "localhost:9092"
	}
	var kafkaTopic string
	if kafkaTopic = os.Getenv("EVENTS_TOPIC"); kafkaTopic == "" {
		kafkaTopic = "test-topic"
	}
	seeds := []string{kafkaURL}
	ctx := context.Background()

	// Setup kafka consumer
	cl, err := kgo.NewClient(
		kgo.SeedBrokers(seeds...),
		kgo.ConsumerGroup("default"),
		kgo.ConsumeTopics(kafkaTopic),
		kgo.DisableAutoCommit(),
	)
	if err != nil {
		panic(err)
	}
	defer cl.Close()

	var dbURL string
	if dbURL = os.Getenv("DATABASE_URL"); dbURL == "" {
		host := "localhost"
		dockerized := os.Getenv("DOCKERIZED")
		if dockerized != "" && dockerized != "0" && strings.ToLower(dockerized) != "false" {
			host = "db"
		}
		if os.Getenv("POSTGRES_USER") == "" {
			os.Setenv("POSTGRES_USER", "lotus")
		}
		if os.Getenv("POSTGRES_PASSWORD") == "" {
			os.Setenv("POSTGRES_PASSWORD", "lotus")
		}
		if os.Getenv("POSTGRES_DB") == "" {
			os.Setenv("POSTGRES_DB", "lotus")
		}

		dbURL = fmt.Sprintf("postgres://%s:%s@%s:5432/%s?sslmode=disable", os.Getenv("POSTGRES_USER"), os.Getenv("POSTGRES_PASSWORD"), host, os.Getenv("POSTGRES_DB"))
	}
	db, err := sql.Open("postgres", dbURL)
	if err != nil {
		panic(err)
	}
	defer db.Close()

	insertStmt, err := db.Prepare("INSERT INTO metering_billing_usageevent (organization_id, customer_id, cust_id, event_name, time_created, properties, idempotency_id, inserted_at) VALUES ($1, $2, $3, $4, $5, $6, $7, $8) ON CONFLICT DO NOTHING")
	if err != nil {
		panic(err)
	}
	defer insertStmt.Close()

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
			panic(fmt.Sprint(errs))
		}

		tx, err := db.Begin()
		if err != nil {
			fmt.Printf("Error starting transaction: %s\n", err)
			continue
		}
		batch := &batch{
			tx:         tx,
			insertStmt: insertStmt,
		}

		fetches.EachRecord(func(r *kgo.Record) {
			fmt.Printf("Received record: %s", r.Value)
			var streamEvents StreamEvents
			err := json.Unmarshal(r.Value, &streamEvents)
			if err != nil {
				fmt.Printf("Error unmarshalling event: %s\n", err)
				return
			}

			if streamEvents.Event == nil {
				if len(streamEvents.Events) > 0 {
					streamEvents.Event = &streamEvents.Events[0]
				} else {
					fmt.Println("Error: both event and events fields are missing from stream_events")
					return
				}
			}

			event := streamEvents.Event
			event.CustomerID = nil
			event.InsertedAt = time.Now()

			if err := batch.addRecord(event); err != nil {
				fmt.Printf("Error inserting event: %s\n", err)
				return
			}
		})

		if batch.count > 0 {
			if err := tx.Commit(); err != nil {
				fmt.Printf("Error inserting events into database: %s\n", err)
				return
			}
			if err := cl.CommitUncommittedOffsets(context.Background()); err != nil {
				fmt.Printf("commit records failed: %v", err)
				panic(errors.New("commit records failed"))
			}
		}
	}
}
