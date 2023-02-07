package event_ingest

import (
	"testing"

	"github.com/stretchr/testify/assert"
)

func TestGetHello(t *testing.T) {
	expected := "Hello World from TEST"
	actual := GetHello("TEST")

	assert.Equal(t, actual, expected)
}
