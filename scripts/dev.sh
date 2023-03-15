#!/bin/bash
# check to see what plarform
if [[ "$OSTYPE" == "win32" ]] || [[ "$OSTYPE" == "win64" ]]; then
  # debian or Windows
  FILE=env/.env.dev
  if [ -f "$FILE" ]; then
    echo "Reading dev environment variables 🚀"
    echo "Building and running Docker image! 🚀"
    docker-compose -f docker-compose.dev.yaml --env-file env/.env.dev up --build
  else
    echo "Creating dev environment variables 🚀"
    copy env/.env.dev.example env/.env.dev
    echo "env file created."
    echo "Please consider replacing the .env.dev file content with custom values!"
    echo "Building and running Docker image! 🚀"
    docker-compose -f docker-compose.dev.yaml --env-file env/.env.dev up --build
  fi
else
  # macOS OSX or Linux
  FILE=env/.env.dev
  if [ -f "$FILE" ]; then
    echo "Reading dev environment variables 🚀"
    echo "Building and running Docker image! 🚀"
    docker-compose -f docker-compose.dev.yaml --env-file env/.env.dev up --build
  else
    echo "Creating dev environment variables 🚀"
    cp env/.env.dev.example env/.env.dev
    echo "env file created."
    echo "Please consider replacing the .env.dev file content with custom values!"
    echo "Building and running Docker image! 🚀"
    docker-compose -f docker-compose.dev.yaml --env-file env/.env.dev up --build
  fi
fi
