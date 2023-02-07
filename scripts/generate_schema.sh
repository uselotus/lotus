#!/bin/bash

# Change to the lotus/backend directory
cd backend

# Run the "python manage.py generate_schema" command
python manage.py generate_schema

# Change to the lotus/golang directory
cd ../golang

# Run the "oapi-codegen ../docs/openapi_full.yaml > lotus.gen.go" command
oapi-codegen ../docs/openapi_full.yaml > lotus.gen.go

# Change back to the lotus directory
cd ../