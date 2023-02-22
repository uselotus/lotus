package config

import (
	"fmt"
	"strings"

	"github.com/spf13/viper"
)

func GetDatabaseURL(v *viper.Viper) string {
	if v.GetString("database_url") != "" {
		return v.GetString("database_url")
	}

	host := "localhost"
	dockerized := strings.ToLower(v.GetString("dockerized"))

	if !(dockerized == "false" || dockerized == "0" || dockerized == "no" || dockerized == "f" || dockerized == "") {
		host = "db"
	}

	postgresUser := v.GetString("postgres_user")
	postgresPassword := v.GetString("postgres_password")
	postgresDB := v.GetString("postgres_db")

	return fmt.Sprintf("postgres://%s:%s@%s:5432/%s?sslmode=disable", postgresUser, postgresPassword, host, postgresDB)
}
