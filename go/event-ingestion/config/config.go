package config

import (
	"github.com/spf13/viper"
)

type Config struct {
	DatabaseURL       string
	Port              uint
	KafkaURL          string
	KafkaTopic        string
	KafkaSASLUsername string
	KafkaSASLPassword string
	RedisURL          string
}

var Conf Config

func GetConfig() Config {
	v := viper.New()

	v.SetDefault("port", 7998)
	v.SetDefault("dockerized", "true")

	// Kafka defaults
	v.SetDefault("kafka_url", "localhost:9092")
	v.SetDefault("kafka_topic", "test-topic")
	v.SetDefault("kafka_sasl_username", "")
	v.SetDefault("kafka_sasl_password", "")

	// Postgres defaults
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
	v.BindEnv("kafka_sasl_username", "KAFKA_SASL_USERNAME")
	v.BindEnv("kafka_sasl_password", "KAFKA_SASL_PASSWORD")
	v.BindEnv("redis_url", "REDIS_TLS_URL", "REDIS_URL")

	conf := Config{
		DatabaseURL:       GetDatabaseURL(v),
		Port:              v.GetUint("port"),
		KafkaURL:          v.GetString("kafka_url"),
		KafkaTopic:        v.GetString("kafka_topic"),
		KafkaSASLUsername: v.GetString("kafka_sasl_username"),
		KafkaSASLPassword: v.GetString("kafka_sasl_password"),
		RedisURL:          GetRedisURL(v),
	}

	return conf
}

func init() {
	Conf = GetConfig()
}
