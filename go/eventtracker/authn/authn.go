package authn

import (
	"database/sql"
	"net/http"
	"time"

	"github.com/labstack/echo/v4"
)

type APIKey struct {
	ID           string    `json:"id"`
	Organization string    `json:"organization"`
	Created      time.Time `json:"created"`
	Name         string    `json:"name"`
	Revoked      bool      `json:"revoked"`
	ExpiryDate   time.Time `json:"expiry_date"`
	HashedKey    string    `json:"hashed_key"`
	Prefix       string    `json:"prefix"`
}

func Middleware() echo.MiddlewareFunc {
	return func(next echo.HandlerFunc) echo.HandlerFunc {
		return func(c echo.Context) error {
			key := c.Request().Header.Get("HTTP_X_API_KEY")

			if key == "" {
				key = c.Request().Header.Get("http_x_api_key")
			}

			if key == "" {
				return echo.NewHTTPError(http.StatusBadRequest, "No API key found in request")
			}

			db := c.Get("db").(*sql.DB)

			var apiKey APIKey

			if err := db.QueryRow("SELECT * FROM api_keys WHERE hashed_key = ?", key).Scan(&apiKey); err != nil {
				return echo.NewHTTPError(http.StatusBadRequest, "Invalid API key")
			}

			// TODO: Soham - Check if the key is revoked or expired

			return next(c)
		}
	}
}
