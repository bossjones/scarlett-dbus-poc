#!/usr/bin/env bash

export DOCKER_TLS_VERIFY="1"
export DOCKER_HOST="tcp://127.0.0.1:2376"
export DOCKER_CERT_PATH="/Users/malcolm/.docker/machine/machines/scarlett-docker"
export DOCKER_MACHINE_NAME="scarlett-docker"
# Run this command to configure your shell:
eval "$(docker-machine env scarlett-docker)"
