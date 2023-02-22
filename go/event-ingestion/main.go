package main

import (
	"context"
	"crypto/tls"
	"fmt"
	"log"
	"net"
	"net/http"
	"time"

	"github.com/labstack/echo/v4"
	"github.com/labstack/echo/v4/middleware"
	_ "github.com/lib/pq"
	"github.com/twmb/franz-go/pkg/kgo"
	"github.com/twmb/franz-go/pkg/sasl/scram"
	"github.com/uselotus/lotus/go/event-ingestion/authn"
	"github.com/uselotus/lotus/go/event-ingestion/cache"
	"github.com/uselotus/lotus/go/event-ingestion/config"
	"github.com/uselotus/lotus/go/event-ingestion/database"
	"github.com/uselotus/lotus/go/event-ingestion/kafka"
	"github.com/uselotus/lotus/go/event-ingestion/types"
)

type TrackEventResponse struct {
	Success      string            `json:"success"`
	FailedEvents map[string]string `json:"failed_events"`
}

type RawEventBatch struct {
	Batch []types.RawEvent `json:"batch"`
}

func main() {
	db, err := database.New()

	if err != nil {
		log.Fatalf("Error connecting to database: %v", err)
	}

	defer db.Close()

	cacheClient, err := cache.New(config.Conf)

	if err != nil {
		log.Fatalf("Error connecting to cache: %v", err)
	}

	seeds := []string{config.Conf.KafkaURL}

	opts := []kgo.Opt{
		kgo.SeedBrokers(seeds...),
		kgo.ConsumerGroup("default"),
		kgo.ConsumeTopics(config.Conf.KafkaTopic),
		kgo.DisableAutoCommit(),
	}

	saslUsername := config.Conf.KafkaSASLUsername
	saslPassword := config.Conf.KafkaSASLPassword

	if saslUsername != "" && saslPassword != "" {
		opts = append(opts, kgo.SASL(scram.Auth{
			User: saslUsername,
			Pass: saslPassword,
		}.AsSha512Mechanism()))
		// Configure TLS. Uses SystemCertPool for RootCAs by default.
		tlsDialer := &tls.Dialer{NetDialer: &net.Dialer{Timeout: 10 * time.Second}}
		opts = append(opts, kgo.Dialer(tlsDialer.DialContext))
	}

	cl, err := kgo.NewClient(
		opts...,
	)

	ctx := context.Background()

	if err != nil {
		log.Fatalf("Error creating kafka client: %v", err)
	}

	defer cl.Close()

	e := echo.New()

	e.Use(middleware.Logger())
	e.Use(database.Middleware(db))
	e.Use(authn.Middleware(cacheClient))

	e.POST("/api/track/", func(c echo.Context) error {
		now := time.Now()

		events := RawEventBatch{}

		if err := c.Bind(&events); err != nil {
			singleEvent := types.RawEvent{}

			if err := c.Bind(&singleEvent); err != nil {
				return c.JSON(http.StatusBadRequest, TrackEventResponse{
					Success:      "none",
					FailedEvents: map[string]string{"no_idempotency_id": "Invalid JSON"},
				})
			}

			events.Batch = append(events.Batch, singleEvent)
		}

		badEvents := make(map[string]string)

		for _, event := range events.Batch {
			if valid, reason := event.IsValid(now); !valid {
				if event.IdempotencyID != "" {
					badEvents[event.IdempotencyID] = reason
				} else {
					badEvents["no_idempotency_id"] = reason
				}

				continue
			}

			key := c.Get("apiKey").(types.APIKey)

			transformedEvent := event.Transform(key.OrganizationID)

			if err := kafka.Produce(ctx, cl, transformedEvent); err != nil {
				badEvents[event.IdempotencyID] = fmt.Sprintf("Failed to produce event to kafka: %v", err)
			}
		}

		if len(badEvents) == len(events.Batch) {
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
