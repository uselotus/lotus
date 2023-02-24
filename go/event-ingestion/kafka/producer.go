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
	OrganizationID int64               `json:"organization_id"`
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

	keyBytes := make([]byte, 8)

	binary.BigEndian.PutUint64(keyBytes, uint64(event.OrganizationID))

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
