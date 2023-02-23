package authn

import (
	"database/sql"
	"net/http"
	"strings"

	"github.com/labstack/echo/v4"
	"github.com/uselotus/lotus/go/event-ingestion/cache"
	"github.com/uselotus/lotus/go/event-ingestion/types"
)

func getAPIKeyFromHeader(h http.Header) string {
	key := h.Get("X-API-KEY")

	if key == "" {
		for k, v := range h {
			if strings.ToLower(k) == "x-api-key" {
				key = v[0]
				break
			}
		}
	}

	return key
}

func getFromDB(db *sql.DB, prefix string) (*types.APIKey, error) {
	var apiKey types.APIKey

	if err := db.QueryRow("SELECT organization_id, created, name, revoked, expiry_date, hashed_key, prefix FROM metering_billing_apitoken WHERE prefix = $1 AND revoked = 'false' LIMIT 1", prefix).Scan(
		&apiKey.OrganizationID,
		&apiKey.Created,
		&apiKey.Name,
		&apiKey.Revoked,
		&apiKey.ExpiryDate,
		&apiKey.HashedKey,
		&apiKey.Prefix,
	); err != nil {
		return nil, err
	}

	return &apiKey, nil
}

func Middleware(cacheClient cache.Cache) echo.MiddlewareFunc {
	return func(next echo.HandlerFunc) echo.HandlerFunc {
		return func(c echo.Context) error {
			key := getAPIKeyFromHeader(c.Request().Header)

			if key == "" {
				return echo.NewHTTPError(http.StatusBadRequest, "No API key found in request")
			}

			if organizationID, err := cacheClient.Get(key); err == nil {
				c.Set("organization", organizationID)
				return next(c)
			}

			db := c.Get("db").(*sql.DB)

			prefix, _, _ := strings.Cut(key, ".")

			apiKey, err := getFromDB(db, prefix)

			if err == sql.ErrNoRows {
				return echo.NewHTTPError(http.StatusBadRequest, "Invalid API key")
			}

			if err != nil {
				return echo.NewHTTPError(http.StatusInternalServerError, err)
			}

			if err := apiKey.Validate(); err != nil {
				return echo.NewHTTPError(http.StatusBadRequest, err)
			}

			cacheClient.Set(key, apiKey.OrganizationID)
			
			c.Set("organization", apiKey.OrganizationID)

			return next(c)
		}
	}
}
