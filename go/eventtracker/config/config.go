package config

import (
	"fmt"
	"strings"

	"github.com/spf13/viper"
)

type Config struct {
	DatabaseURL string
	Port        uint
	KafkaURL    string
	KafkaTopic  string
}

var Conf Config

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

func GetConfig() Config {
	v := viper.New()

	v.SetDefault("port", 7998)
	v.SetDefault("kafka_url", "localhost:9092")
	v.SetDefault("kafka_topic", "test-topic")
	v.SetDefault("dockerized", "true")
	v.SetDefault("postgres_user", "lotus")
	v.SetDefault("postgres_password", "lotus")
	v.SetDefault("postgres_db", "lotus")

	v.BindEnv("database_url", "DATABASE_URL")
	v.BindEnv("dockerized", "DOCKERIZED")
	v.BindEnv("postgres_user", "POSTGRES_USER")
	v.BindEnv("postgres_password", "POSTGRES_PASSWORD")
	v.BindEnv("postgres_db", "POSTGRES_DB")
	v.BindEnv("port", "PORT")
	v.BindEnv("kafka_url", "KAFKA_URL")
	v.BindEnv("kafka_topic", "EVENTS_TOPIC")

	conf := Config{
		DatabaseURL: GetDatabaseURL(v),
		Port:        v.GetUint("port"),
		KafkaURL:    v.GetString("kafka_url"),
		KafkaTopic:  v.GetString("kafka_topic"),
	}

	return conf
}

func init() {
	Conf = GetConfig()
}
