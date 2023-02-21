package authn

import (
	"database/sql"
	"net/http"
	"strings"

	"github.com/labstack/echo/v4"
	"github.com/uselotus/lotus/go/eventtracker/types"
)

func Middleware() echo.MiddlewareFunc {
	return func(next echo.HandlerFunc) echo.HandlerFunc {
		return func(c echo.Context) error {
			key := c.Request().Header.Get("X-API-KEY")
			if key == "" {
				for k, v := range c.Request().Header {
					if strings.ToLower(k) == "x-api-key" {
						key = v[0]
						break
					}
				}
			}

			if key == "" {
				return echo.NewHTTPError(http.StatusBadRequest, "No API key found in request")
			}

			prefix, _, _ := strings.Cut(key, ".")

			db := c.Get("db").(*sql.DB)

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
				if err == sql.ErrNoRows {
					return echo.NewHTTPError(http.StatusBadRequest, "Invalid API key")
				}

				return echo.NewHTTPError(http.StatusInternalServerError, err)
			}

			if err := apiKey.Validate(); err != nil {
				return echo.NewHTTPError(http.StatusBadRequest, err)
			}

			c.Set("apiKey", apiKey)

			return next(c)
		}
	}
}
