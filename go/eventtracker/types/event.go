package types

type (
	Event struct {
		CustomerID    string                 `json:"customer_id"`
		IdempotencyID string                 `json:"idempotency_id"`
		TimeCreated   string                 `json:"time_created"`
		Properties    map[string]interface{} `json:"properties"`
		EventName     string                 `json:"event_name"`
	}

	IngestedEvent struct {
		OrganizationID string                 `json:"organization_id"`
		CustID         string                 `json:"customer_id"`
		IdempotencyID  string                 `json:"idempotency_id"`
		TimeCreated    string                 `json:"time_created"`
		Properties     map[string]interface{} `json:"properties"`
		EventName      string                 `json:"event_name"`
	}
)

func (e Event) IsValid() (bool, string) {
	if e.IdempotencyID == "" {
		return false, "No idempotency_id provided"
	}

	if e.CustomerID == "" {
		return false, "No customer_id provided"
	}

	if e.TimeCreated == "" {
		return false, "Invalid time_created"
	}

	return true, ""
}

func (e Event) Transform(organizationID string) IngestedEvent {
	return IngestedEvent{
		OrganizationID: organizationID,
		CustID:         e.CustomerID,
		IdempotencyID:  e.IdempotencyID,
		TimeCreated:    e.TimeCreated,
		Properties:     e.Properties,
		EventName:      e.EventName,
	}
}
