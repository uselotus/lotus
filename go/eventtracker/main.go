package main

import (
	"context"
	"fmt"
	"log"
	"net/http"
	_ "net/http"

	"github.com/labstack/echo/v4"
	"github.com/labstack/echo/v4/middleware"
	_ "github.com/lib/pq"
	"github.com/twmb/franz-go/pkg/kgo"
	"github.com/uselotus/lotus/go/eventtracker/config"
	"github.com/uselotus/lotus/go/eventtracker/database"
	"github.com/uselotus/lotus/go/eventtracker/kafka"
	"github.com/uselotus/lotus/go/eventtracker/types"
)

type TrackEventResponse struct {
	Success      string            `json:"success"`
	FailedEvents map[string]string `json:"failed_events"`
}

func main() {
	db, err := database.New()

	if err != nil {
		log.Fatalf("Error connecting to database: %v", err)
	}

	fmt.Println("Connect to database successfully!")

	defer db.Close()

	seeds := []string{config.Conf.KafkaURL}

	cl, err := kgo.NewClient(
		kgo.SeedBrokers(seeds...),
		kgo.ConsumerGroup("default"),
		kgo.ConsumeTopics(config.Conf.KafkaTopic),
		kgo.DisableAutoCommit(),
	)

	ctx := context.Background()

	if err != nil {
		log.Fatalf("Error creating kafka client: %v", err)
	}

	defer cl.Close()

	e := echo.New()

	e.Use(middleware.Logger())
	e.Use(database.Middleware(db))

	e.POST("/", func(c echo.Context) error {
		events := &[]types.Event{}

		if err := c.Bind(events); err != nil {
			return err
		}

		badEvents := make(map[string]string)

		for _, event := range *events {
			if valid, reason := event.IsValid(); !valid {
				if event.IdempotencyID != "" {
					badEvents[event.IdempotencyID] = reason
				} else {
					badEvents["no_idempotency_id"] = reason
				}

				continue
			}

			organization := c.Get("organization").(string)

			transformedEvent := event.Transform(organization)

			if err := kafka.Produce(ctx, cl, transformedEvent); err != nil {
				badEvents[event.IdempotencyID] = fmt.Sprintf("Failed to produce event to kafka: %v", err)
			}
		}

		if len(badEvents) == len(*events) {
			return c.JSON(http.StatusBadRequest, TrackEventResponse{
				Success:      "none",
				FailedEvents: badEvents,
			})
		}

		if len(badEvents) > 0 {
			return c.JSON(http.StatusCreated, TrackEventResponse{
				Success:      "some",
				FailedEvents: badEvents,
			})
		}

		return c.JSON(http.StatusCreated, TrackEventResponse{
			Success: "all",
		})
	})

	e.Logger.Fatal(e.Start(fmt.Sprintf(":%d", config.Conf.Port)))
}
