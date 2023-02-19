package database

import (
	"database/sql"

	"github.com/labstack/echo/v4"
	_ "github.com/lib/pq"
)

func Middleware(db *sql.DB) echo.MiddlewareFunc {
	return func(next echo.HandlerFunc) echo.HandlerFunc {
		return func(c echo.Context) error {
			c.Set("db", db)

			return next(c)
		}
	}
}

func New() (*sql.DB, error) {
	db, err := sql.Open("postgres", "postgres://postgres:postgrespw@localhost:5432/postgres?sslmode=disable")

	if err != nil {
		return nil, err
	}

	return db, nil
}
