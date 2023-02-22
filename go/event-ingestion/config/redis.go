package config

import (
	"strings"

	"github.com/spf13/viper"
)

func GetRedisURL(v *viper.Viper) string {
	if v.GetString("redis_url") != "" {
		return v.GetString("redis_url")
	}

	dockerized := strings.ToLower(v.GetString("dockerized"))

	if !(dockerized == "false" || dockerized == "0" || dockerized == "no" || dockerized == "f" || dockerized == "") {
		return "redis://redis:6379"
	}

	return ""
}
