#!/bin/bash

set -e

export APP_VERSION="1.0.1"

docker image build \
    -t pypi_scraper/app:latest \
    -t rpi-cluster-4b-1gb-1:5000/pypi_scraper/app:latest \
    -t "rpi-cluster-4b-1gb-1:5000/pypi_scraper/app:$APP_VERSION" \
    -f app.Dockerfile .

docker image push "rpi-cluster-4b-1gb-1:5000/pypi_scraper/app:$APP_VERSION"
docker image push "rpi-cluster-4b-1gb-1:5000/pypi_scraper/app:latest"

docker stack deploy -c swarm.rpi-cluster.local-db.docker-compose.yml pypi_scraper
