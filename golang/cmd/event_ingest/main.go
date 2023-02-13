package main

import (
	"context"
	"database/sql"
	"encoding/json"
	"fmt"
	"time"

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

func main() {
	seeds := []string{"localhost:9092"}
	ctx := context.Background()

	// Setup kafka consumer
	cl, err := kgo.NewClient(
		kgo.SeedBrokers(seeds...),
		kgo.ConsumerGroup("default"),
		kgo.ConsumeTopics("test-topic"),
		kgo.DisableAutoCommit(),
	)
	if err != nil {
		panic(err)
	}
	defer cl.Close()

	//setup db connection
	db, err := sql.Open("postgres", "postgres://user:password@localhost/dbname?sslmode=disable")
	if err != nil {
		panic(err)
	}
	defer db.Close()

	// Set up prepared statement for insert
	stmt, err := db.Prepare(`INSERT INTO events (organization_id, customer_id, cust_id, event_name, time_created, properties, idempotency_id, inserted_at)
		VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
		ON CONFLICT DO NOTHING`)
	if err != nil {
		panic(err)
	}

	for {
		fetches := cl.PollFetches(ctx)
		if fetches == nil {
			continue
		}
		if fetches.IsClientClosed() {
			return
		}
		if errs := fetches.Errors(); len(errs) > 0 {
			// All errors are retried internally when fetching, but non-retriable errors are
			// returned from polls so that users can notice and take action.
			panic(fmt.Sprint(errs))
		}

		events := make([]*Event, 0)
		fetches.EachRecord(func(r *kgo.Record) {
			event := &Event{}
			err := json.Unmarshal(r.Value, event)
			if err != nil {
				fmt.Printf("Error unmarshalling event: %s\n", err)
				return
			}
			event.CustomerID = nil
			event.InsertedAt = time.Now()
			events = append(events, event)

			if len(events) >= batchSize {
				err = insertEvents(stmt, events, db, ctx)
				if err != nil {
					fmt.Printf("Error inserting events into database: %s\n", err)
				}
				events = make([]*Event, 0)
				if err := cl.CommitUncommittedOffsets(context.Background()); err != nil {
					fmt.Printf("commit records failed: %v", err)
				}
			}
		})

		if len(events) > 0 {
			err := insertEvents(stmt, events, db, ctx)
			if err != nil {
				fmt.Printf("Error inserting events into database: %s\n", err)
				return
			}
			if err := cl.CommitUncommittedOffsets(context.Background()); err != nil {
				fmt.Printf("commit records failed: %v", err)
			}
		}
	}
}

func insertEvents(stmt *sql.Stmt, events []*Event, db *sql.DB, ctx context.Context) error {
	tx, err := db.BeginTx(ctx, nil)
	if err != nil {
		return fmt.Errorf("error starting transaction: %s", err)
	}
	defer tx.Rollback()

	// Create a slice to hold the values to be inserted
	var values []interface{}

	// Loop through the events and add their values to the slice
	for _, event := range events {
		values = append(values, event.OrganizationID, event.CustomerID, event.CustID, event.EventName, event.TimeCreated, event.Properties, event.IdempotencyID, event.InsertedAt)
	}

	// Execute the batch insert statement with the values slice
	_, err = stmt.Exec(values...)
	if err != nil {
		return fmt.Errorf("error executing statement: %s", err)
	}

	err = tx.Commit()
	if err != nil {
		return fmt.Errorf("error committing transaction: %s", err)
	}

	return nil
}
