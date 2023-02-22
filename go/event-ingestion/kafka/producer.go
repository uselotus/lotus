package kafka

import (
	"context"
	"encoding/binary"
	"encoding/json"

	"github.com/twmb/franz-go/pkg/kgo"
	"github.com/uselotus/lotus/go/event-ingestion/config"
	"github.com/uselotus/lotus/go/event-ingestion/types"
)

type StreamEvent struct {
	OrganizationID int                 `json:"organization_id"`
	Event          types.VerifiedEvent `json:"event"`
}

func Produce(ctx context.Context, cl *kgo.Client, event types.VerifiedEvent) error {
	streamEvent := StreamEvent{
		OrganizationID: event.OrganizationID,
		Event:          event,
	}

	value, err := json.Marshal(streamEvent)

	if err != nil {
		return err
	}

	keyBytes := make([]byte, 4)
	binary.BigEndian.PutUint32(keyBytes, uint32(event.OrganizationID))

	record := &kgo.Record{
		Topic: config.Conf.KafkaTopic,
		Value: value,
		Key:   keyBytes,
	}

	if err = cl.ProduceSync(ctx, record).FirstErr(); err != nil {
		return err
	}

	return nil
}
