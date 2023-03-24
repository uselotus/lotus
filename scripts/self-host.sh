#!/bin/bash
# check to see what platform

# Determine platform-specific commands
if [[ "$OSTYPE" == "win32" ]] || [[ "$OSTYPE" == "win64" ]]; then
  # Windows
  COPY_CMD="copy"
else
  # macOS or Linux
  COPY_CMD="cp"
fi

# Set Docker images and compose args
DOCKER_IMAGES=("lotus-frontend:latest" "lotus-celery:latest" "event-ingestion:latest"  "event-guidance:latest" "lotus-backend:latest" "lotus-celery-beat:latest" "svix/svix-server:latest" "redis:7-alpine" "timescale/timescaledb-ha:latest" "docker.redpanda.com/vectorized/redpanda:v22.2.2")
DOCKER_COMPOSE_ARGS="-f docker-compose.prod.yaml --env-file env/.env.prod"


# Check if environment variables file exists
ENV_FILE="env/.env.prod"
if [ -f "$ENV_FILE" ]; then
  echo "Reading prod environment variables 🚀"
else
  echo "Creating prod environment variables 🚀"
  $COPY_CMD env/.env.prod.example env/.env.prod
  echo "env file created."
  echo "Please consider replacing the .env.prod file content with custom values!"
fi

# Run Docker images
echo "Running Docker images 🚀"
docker-compose $DOCKER_COMPOSE_ARGS up --build