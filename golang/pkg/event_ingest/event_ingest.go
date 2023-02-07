package event_ingest

import (
	"fmt"
	"time"
)

type Event struct {
	OrganizationID int                    `json:"organization,omitempty"`
	CustomerID     int                    `json:"customer,omitempty"`
	CustID         string                 `json:"cust_id,omitempty"`
	EventName      string                 `json:"event_name,omitempty"`
	TimeCreated    time.Time              `json:"time_created,omitempty"`
	Properties     map[string]interface{} `json:"properties,omitempty"`
	IdempotencyID  string                 `json:"idempotency_id,omitempty"`
	InsertedAt     time.Time              `json:"inserted_at,omitempty"`
}

func GetHello(s string) string {
	return fmt.Sprintf("Hello World from %s", s)
}
