#!/bin/bash

set -e

docker exec lotus-backend-1 /bin/sh -c "black ."
