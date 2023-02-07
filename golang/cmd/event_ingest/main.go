package main

import (
	"context"
	"encoding/json"
	"fmt"

	"time"

	"github.com/lib/pq"
	"github.com/twmb/franz-go/pkg/kgo"
	"github.com/uselotus/lotus/pkg/event_ingest"
)

const batchSize = 100
const flushInterval = time.Second

func main() {
	topic := "demo"
	ctx := context.Background()
	seeds := []string{"localhost:9092"}

	client, err := kgo.NewClient(
		kgo.SeedBrokers(seeds...),
		kgo.ConsumerGroup("demo-group"),
		kgo.ConsumeTopics(topic),
		kgo.ConsumeResetOffset(kgo.NewOffset().AtStart()),
	)
	if err != nil {
		panic(err)
	}
	defer client.Close()

	for {
		fetches := client.PollFetches(ctx)
		if errs := fetches.Errors(); len(errs) > 0 {
			// All errors are retried internally when fetching, but non-retriable
			// errors are returned from polls so that users can notice and take
			// action.
			panic(fmt.Sprint(errs))
		}

		iter := fetches.RecordIter()
		for !iter.Done() {
			record := iter.Next()
			var event event_ingest.Event // Event will have null Customer fk and time_created
			err := json.Unmarshal(record.Value, &event)
			if err != nil {
				panic(err)
			}

			topicInfo := fmt.Sprintf("topic: %s (%d|%d)",
				record.Topic, record.Partition, record.Offset)
			messageInfo := fmt.Sprintf("key: %s, Value: %+v",
				record.Key, event)
			fmt.Printf("Message consumed: %s, %s \n", topicInfo, messageInfo)
		}
	}
}

func flushBuffer(db *pq.DB, buffer []event_ingest.Event) {
	// Start a transaction
	txn, err := db.Begin()
	if err != nil {
		fmt.Println("Error starting transaction:", err)
		return
	}

	// Prepare the statement
	stmt, err := txn.Prepare(pq.CopyIn("your_table", "column1", "column2", "idempotency_id", "time_created", "time_inserted"))
	if err != nil {
		fmt.Println("Error preparing statement:", err)
		return
	}

	// Execute the statement for each event in the buffer
	for _, ev := range buffer {
		_, err := stmt.Exec(string(ev.Key), string(ev.Value), ev.IdempotencyID, ev.TimeCreated, ev.TimeInserted)
		if err != nil {
			fmt.Println("Error inserting event:", err)
			return
		}
	}

	// Close the statement
	_, err = stmt.Exec()
	if err != nil {
		fmt.Println("Error closing statement:", err)
		return
	}

	// Commit the transaction
	err = txn.Commit()
	if err != nil {
		fmt.Println("Error committing transaction:", err)
		return
	}

	// Clear the buffer
	buffer = nil
}
