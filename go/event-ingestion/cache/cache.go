package cache

import (
	"context"
	"errors"
	"time"

	"github.com/redis/go-redis/v9"
	"github.com/uselotus/lotus/go/event-ingestion/config"
)

type Cache interface {
	Get(key string) (string, error)
	Set(key string, value interface{}) error
}

type RedisCache struct {
	rdb               *redis.Client
	defaultExpiration time.Duration
}

var ctx = context.Background()

func (c *RedisCache) Get(key string) (string, error) {
	val, err := c.rdb.Get(ctx, key).Result()
	if err == redis.Nil {
		return "", nil
	}

	if err != nil {
		return "", err
	}

	return val, nil
}

func (c *RedisCache) Set(key string, value interface{}) error {
	return c.rdb.Set(ctx, key, value, c.defaultExpiration).Err()
}

func New(config config.Config) (Cache, error) {

	address := config.RedisURL

	if address == "" {
		return nil, errors.New("redis url is empty")
	}

	opt, err := redis.ParseURL(address)
	if err != nil {
		return nil, err
	}

	rdb := redis.NewClient(opt)

	cache := &RedisCache{
		rdb:               rdb,
		defaultExpiration: 5 * time.Hour,
	}

	return cache, nil
}
