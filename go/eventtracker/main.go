package main

import (
	"net/http"
	"time"

	"github.com/labstack/echo/v4"
	"github.com/labstack/echo/v4/middleware"
)

type Event struct {
	CustomerID    string                 `json:"customer_id"`
	IdempotencyID string                 `json:"idempotency_id"`
	TimeCreated   time.Time              `json:"time_created"`
	Properties    map[string]interface{} `json:"properties"`
	EventName     string                 `json:"event_name"`
}

type IngestedEvent struct {
	OrganizationID string                 `json:"organization_id"`
	CustID         string                 `json:"customer_id"`
	IdempotencyID  string                 `json:"idempotency_id"`
	TimeCreated    time.Time              `json:"time_created"`
	Properties     map[string]interface{} `json:"properties"`
	EventName      string                 `json:"event_name"`
}

type TrackEventResponse struct {
	Success      string            `json:"success"`
	FailedEvents map[string]string `json:"failed_events"`
}

func (e Event) isValid() (bool, string) {
	if e.IdempotencyID == "" {
		return false, "No idempotency_id provided"
	}

	if e.CustomerID == "" {
		return false, "No customer_id provided"
	}

	if e.TimeCreated.IsZero() {
		return false, "Invalid time_created"
	}

	return true, ""
}

func (e Event) transform(organizationID string) IngestedEvent {
	return IngestedEvent{
		OrganizationID: organizationID,
		CustID:         e.CustomerID,
		IdempotencyID:  e.IdempotencyID,
		TimeCreated:    e.TimeCreated,
		Properties:     e.Properties,
		EventName:      e.EventName,
	}
}

func main() {
	e := echo.New()

	e.Use(middleware.Logger())

	badEvents := make(map[string]string)

	e.POST("/events", func(c echo.Context) error {
		events := &[]Event{}

		if err := c.Bind(events); err != nil {
			return err
		}

		for _, event := range *events {
			if valid, reason := event.isValid(); !valid {
				if event.IdempotencyID != "" {
					badEvents[event.IdempotencyID] = reason
				} else {
					badEvents["no_idempotency_id"] = reason
				}

				continue
			}

			// TODO Soham: Check if the event is a future event or past event
			transformedEvent := event.transform("org_id")

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
			Success:      "all",
			FailedEvents: badEvents,
		})
	})
}
