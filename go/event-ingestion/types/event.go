package types

import "time"

type (
	RawEvent struct {
		CustomerID    string                 `json:"customer_id,omitempty"`
		IdempotencyID string                 `json:"idempotency_id,omitempty"`
		TimeCreated   time.Time              `json:"time_created,omitempty"`
		Properties    map[string]interface{} `json:"properties,omitempty"`
		EventName     string                 `json:"event_name,omitempty"`
	}

	VerifiedEvent struct {
		OrganizationID int64                  `json:"organization_id,omitempty"`
		CustID         string                 `json:"customer_id,omitempty"`
		IdempotencyID  string                 `json:"idempotency_id,omitempty"`
		TimeCreated    time.Time              `json:"time_created,omitempty"`
		Properties     map[string]interface{} `json:"properties,omitempty"`
		EventName      string                 `json:"event_name,omitempty"`
	}
)

func (e RawEvent) IsValid(now time.Time) (bool, string) {
	if e.IdempotencyID == "" {
		return false, "No idempotency_id provided"
	}

	if e.CustomerID == "" {
		return false, "No customer_id provided"
	}

	if e.TimeCreated.IsZero() {
		return false, "Invalid time_created"
	}

	timeCreated, err := time.ParseInLocation(time.RFC3339, e.TimeCreated.Format(time.RFC3339), time.UTC)

	if err != nil {
		return false, "Invalid time_created"
	}

	// now.Sub(time.Hour*24*30)
	startDate := now.AddDate(0, 0, -30)
	endDate := now.AddDate(0, 0, 1)

	if timeCreated.Before(startDate) || timeCreated.After(endDate) {
		return false, "Time created too far in the past or future. Events must be within 30 days before or 1 day ahead of current time."
	}

	return true, ""
}

func (e RawEvent) Transform(organizationID int64) VerifiedEvent {
	return VerifiedEvent{
		OrganizationID: organizationID,
		CustID:         e.CustomerID,
		IdempotencyID:  e.IdempotencyID,
		TimeCreated:    e.TimeCreated,
		Properties:     e.Properties,
		EventName:      e.EventName,
	}
}
