#!/bin/bash
# check to see what plarform
if [[ "$OSTYPE" == "win32" ]] || [[ "$OSTYPE" == "msys" ]] || [[ "$OSTYPE" == "cygwin" ]];
then
    # debian or Windows
   FILE=env/.env.prod
if [ -f "$FILE" ]; then
    echo "Reading prod environment variables 🚀"
    echo "Building and running Docker image! 🚀"
    docker-compose -f docker-compose.prod.yaml --env-file env/.env.prod up --build
else
echo "Creating prod environment variables 🚀"
 copy env/.env.prod.example env/.env.prod
 echo "env file created."
 echo "Please consider replacing the .env.prod file content with custom values!"
 echo "Building and running Docker image! 🚀"
 docker-compose -f docker-compose.prod.yaml --env-file env/.env.prod up --build
 fi
else
  # macOS OSX or Linux
  FILE=env/.env.prod
if [ -f "$FILE" ]; then
    echo "Reading prod environment variables 🚀"
    echo "Building and running Docker image! 🚀"
    docker-compose -f docker-compose.prod.yaml --env-file env/.env.prod up --build
else
echo "Creating prod environment variables 🚀"
 cp env/.env.prod.example env/.env.prod
 echo "env file created."
 echo "Please consider replacing the .env.prod file content with custom values!"
 echo "Building and running Docker image! 🚀"
 docker-compose -f docker-compose.prod.yaml --env-file env/.env.prod up --build
fi
fi
