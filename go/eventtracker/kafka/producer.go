package kafka

import (
	"context"
	"encoding/json"

	"github.com/twmb/franz-go/pkg/kgo"
	"github.com/uselotus/lotus/go/eventtracker/config"
	"github.com/uselotus/lotus/go/eventtracker/types"
)

type StreamEvents struct {
	OrganizationID string                `json:"organization_id"`
	Events         []types.IngestedEvent `json:"events"`
	Event          types.Event           `json:"event"`
}

func Produce(ctx context.Context, cl *kgo.Client, event types.IngestedEvent) error {
	streamEvents := StreamEvents{
		OrganizationID: event.OrganizationID,
		Events:         []types.IngestedEvent{event},
	}

	value, err := json.Marshal(streamEvents)

	if err != nil {
		return err
	}

	record := &kgo.Record{
		Topic: config.Conf.KafkaTopic,
		Value: value,
		Key:   []byte(event.OrganizationID),
	}

	if err = cl.ProduceSync(ctx, record).FirstErr(); err != nil {
		return err
	}

	return nil
}
