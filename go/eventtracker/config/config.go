package config

import (
	"github.com/spf13/viper"
)

type Config struct {
	DatabaseURL string
	Port        uint
	KafkaURL    string
	KafkaTopic  string
}

var Conf Config

func GetConfig() Config {
	v := viper.New()

	v.SetDefault("database_url", "postgres://postgres:postgrespw@localhost:5432/postgres?sslmode=disable")
	v.SetDefault("port", 8080)
	v.SetDefault("kafka_url", "localhost:9092")
	v.SetDefault("kafka_topic", "test-topic")

	v.BindEnv("database_url", "DATABASE_URL")
	v.BindEnv("port", "PORT")
	v.BindEnv("kafka_url", "KAFKA_URL")
	v.BindEnv("kafka_topic", "KAFKA_TOPIC")

	conf := Config{
		DatabaseURL: v.GetString("database_url"),
		Port:        v.GetUint("port"),
		KafkaURL:    v.GetString("kafka_url"),
		KafkaTopic:  v.GetString("kafka_topic"),
	}

	return conf
}

func init() {
	Conf = GetConfig()
}
