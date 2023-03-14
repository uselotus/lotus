package types

import (
	"database/sql"
	"errors"
	"time"
)

type APIKey struct {
	OrganizationID int64        `json:"organization_id"`
	Created        time.Time    `json:"created"`
	Name           string       `json:"name"`
	Revoked        bool         `json:"revoked"`
	ExpiryDate     sql.NullTime `json:"expiry_date"`
	HashedKey      string       `json:"hashed_key"`
	Prefix         string       `json:"prefix"`
}

func (apiKey *APIKey) Validate() error {
	if apiKey.Revoked {
		return errors.New("the API key has been revoked, which cannot be undone")
	}
	if apiKey.ExpiryDate.Valid {
		if apiKey.ExpiryDate.Time.Before(time.Now()) {
			return errors.New("the API key has expired")
		}
	}

	return nil
}
