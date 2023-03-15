#!/bin/bash
# check to see what plarform
if [[ "$OSTYPE" == "win32" ]] || [[ "$OSTYPE" == "win64" ]]; then
  # debian or Windows
  FILE=env/.env.prod
  if [ -f "$FILE" ]; then
    echo "Reading prod environment variables 🚀"

    if [[ "$(docker image inspect lotus-frontend:latest 2>/dev/null)" == "" ]] && [[ "$(docker image inspect lotus-celery:latest 2>/dev/null)" == "" ]] && [[ "$(docker image inspect lotus-event_consumer:latest 2>/dev/null)" == "" ]] && [[ "$(docker image inspect lotus-backend:latest 2>/dev/null)" == "" ]] && [[ "$(docker image inspect lotus-celery-beat:latest 2>/dev/null)" == "" ]] && [[ "$(docker image inspect svix/svix-server:latest 2>/dev/null)" == "" ]] && [[ "$(docker image inspect redis:7-alpine 2>/dev/null)" == "" ]] && [[ "$(docker image inspect timescale/timescaledb-ha:latest 2>/dev/null)" == "" ]]; then

      echo "Building and running Docker image! 🚀"
      docker-compose -f docker-compose.prod.yaml --env-file env/.env.prod up --build

    else
      echo "Running Docker image! 🚀"
      docker-compose -f docker-compose.prod.yaml --env-file env/.env.prod up --build
    fi

  else

    echo "Creating prod environment variables 🚀"
    copy env/.env.prod.example env/.env.prod
    echo "env file created."
    echo "Please consider replacing the .env.prod file content with custom values!"
    if [[ "$(docker image inspect lotus-frontend:latest 2>/dev/null)" == "" ]] && [[ "$(docker image inspect lotus-celery:latest 2>/dev/null)" == "" ]] && [[ "$(docker image inspect lotus-event_consumer:latest 2>/dev/null)" == "" ]] && [[ "$(docker image inspect lotus-backend:latest 2>/dev/null)" == "" ]] && [[ "$(docker image inspect lotus-celery-beat:latest 2>/dev/null)" == "" ]] && [[ "$(docker image inspect svix/svix-server:latest 2>/dev/null)" == "" ]] && [[ "$(docker image inspect redis:7-alpine 2>/dev/null)" == "" ]] && [[ "$(docker image inspect timescale/timescaledb-ha:latest 2>/dev/null)" == "" ]]; then

      echo "Building and running Docker image! 🚀"
      docker-compose -f docker-compose.prod.yaml --env-file env/.env.prod up --build

    else
      echo "Running Docker image! 🚀"
      docker-compose -f docker-compose.prod.yaml --env-file env/.env.prod up --build

    fi
  fi
else
  # macOS OSX or Linux
  FILE=env/.env.prod
  if [ -f "$FILE" ]; then
    echo "Reading prod environment variables 🚀"

    if [[ "$(docker image inspect lotus-frontend:latest 2>/dev/null)" == "" ]] && [[ "$(docker image inspect lotus-celery:latest 2>/dev/null)" == "" ]] && [[ "$(docker image inspect lotus-event_consumer:latest 2>/dev/null)" == "" ]] && [[ "$(docker image inspect lotus-backend:latest 2>/dev/null)" == "" ]] && [[ "$(docker image inspect lotus-celery-beat:latest 2>/dev/null)" == "" ]] && [[ "$(docker image inspect svix/svix-server:latest 2>/dev/null)" == "" ]] && [[ "$(docker image inspect redis:7-alpine 2>/dev/null)" == "" ]] && [[ "$(docker image inspect timescale/timescaledb-ha:latest 2>/dev/null)" == "" ]] && [[ "$(docker image inspect docker.redpanda.com/vectorized/redpanda:v22.2.2 2>/dev/null)" == "" ]]; then
      echo "I do not get na"
      echo "Building and running Docker image! 🚀"
      docker-compose -f docker-compose.prod.yaml --env-file env/.env.prod up --build

    else
      echo "Running Docker image! 🚀"
      docker-compose -f docker-compose.prod.yaml --env-file env/.env.prod up --build
    fi

  else

    echo "Creating prod environment variables 🚀"
    cp env/.env.prod.example env/.env.prod
    echo "env file created."
    echo "Please consider replacing the .env.prod file content with custom values!"

    if [[ "$(docker image inspect lotus-frontend:latest 2>/dev/null)" == "" ]] && [[ "$(docker image inspect lotus-celery:latest 2>/dev/null)" == "" ]] && [[ "$(docker image inspect lotus-event_consumer:latest 2>/dev/null)" == "" ]] && [[ "$(docker image inspect lotus-backend:latest 2>/dev/null)" == "" ]] && [[ "$(docker image inspect lotus-celery-beat:latest 2>/dev/null)" == "" ]] && [[ "$(docker image inspect svix/svix-server:latest 2>/dev/null)" == "" ]] && [[ "$(docker image inspect redis:7-alpine 2>/dev/null)" == "" ]] && [[ "$(docker image inspect timescale/timescaledb-ha:latest 2>/dev/null)" == "" ]]; then

      echo "Building and running Docker image! 🚀"
      docker-compose -f docker-compose.prod.yaml --env-file env/.env.prod up --build

    else
      echo "Running Docker image! 🚀"
      docker-compose -f docker-compose.prod.yaml --env-file env/.env.prod up --build
    fi

  fi
fi
