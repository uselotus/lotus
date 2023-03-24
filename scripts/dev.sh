#!/bin/bash

# Determine platform-specific command for copying environment variables file
if [[ "$OSTYPE" == "win32" ]] || [[ "$OSTYPE" == "win64" ]]; then
  COPY_CMD="copy"
else
  COPY_CMD="cp"
fi

# Set Docker images and compose args
DOCKER_IMAGES=("lotus-frontend:latest" "lotus-celery:latest" "lotus-backend:latest" "redis:7-alpine" "timescale/timescaledb-ha:latest")
SERVICES=("frontend" "celery" "backend" "redis" "db")
DOCKER_COMPOSE_ARGS="-f docker-compose.dev.yaml --env-file env/.env.dev"



# Check if environment variables file exists
ENV_FILE="env/.env.dev"
if [ -f "$ENV_FILE" ]; then
  echo "Reading dev environment variables 🚀"
else
  echo "Creating dev environment variables 🚀"
  $COPY_CMD env/.env.dev.example env/.env.dev
  echo "env file created."
  echo "Please consider replacing the .env.dev file content with custom values!"
fi

# Check if --no-events flag was passed
if [[ "$*" == *"--no-events"* ]]; then
  echo "Skipping event ingestion, event guidance and redpanda images/containers 🚀"
  echo "NO_EVENTS=true" >> "$ENV_FILE"
else
  DOCKER_IMAGES+=("event-ingestion:latest" "event-guidance:latest" "docker.redpanda.com/vectorized/redpanda:v22.2.2")
  SERVICES+=("event-ingestion" "event-guidance" "redpanda")
fi

# Check if --no-beat flag was passed
if [[ "$*" == *"--no-beat"* ]]; then
  echo "Skipping celery beat images/containers 🚀"
  echo "NO_BEAT=true" >> "$ENV_FILE"
else
  DOCKER_IMAGES+=("lotus-celery-beat:latest")
  SERVICES+=("celery-beat")
fi

# Check if --no-webhooks flag was passed
if [[ "$*" == *"--no-webhooks"* ]]; then
  echo "Skipping svix images/containers 🚀"
  echo "NO_WEBHOOKS=true" >> "$ENV_FILE"
else
  DOCKER_IMAGES+=("svix/svix-server:latest")
  SERVICES+=("svix-server")
fi



# Build missing Docker images
for image in "${DOCKER_IMAGES[@]}"; do
  if [[ "$(docker image inspect "$image" 2>/dev/null)" == "" ]]; then
    echo "Building Docker image $image 🚀"
    docker-compose $DOCKER_COMPOSE_ARGS build "$image"
  fi
done

# Run Docker images
echo "Running Docker images 🚀"

# Determine the appropriate options for `docker-compose up`
DOCKER_COMPOSE_UP_OPTIONS=()
if [[ "$*" == *"--force-recreate"* ]]; then
  DOCKER_COMPOSE_UP_OPTIONS+=("--force-recreate")
fi
if [[ "$*" == *"--no-build"* ]]; then
  :
else
  DOCKER_COMPOSE_UP_OPTIONS+=("--build")
fi

# Run Docker images
echo "Running Docker images 🚀"
docker-compose $DOCKER_COMPOSE_ARGS up $DOCKER_COMPOSE_UP_OPTION "${SERVICES[@]}"
