#!/bin/bash

export DEBEZIUM_VERSION="0.1.0"
export APP_VERSION="0.16.1"

docker image build \
    -t pypi_scraper/debezium:latest \
    -t rpi-cluster-4b-1gb-1:5000/pypi_scraper/debezium:latest \
    -t "rpi-cluster-4b-1gb-1:5000/pypi_scraper/debezium:$DEBEZIUM_VERSION" \
    -f debezium.Dockerfile .

docker image build \
    -t pypi_scraper/app:latest \
    -t rpi-cluster-4b-1gb-1:5000/pypi_scraper/app:latest \
    -t "rpi-cluster-4b-1gb-1:5000/pypi_scraper/app:$APP_VERSION" \
    -f app.Dockerfile .

docker image push "rpi-cluster-4b-1gb-1:5000/pypi_scraper/app:$APP_VERSION"
docker image push "rpi-cluster-4b-1gb-1:5000/pypi_scraper/app:latest"
docker image push "rpi-cluster-4b-1gb-1:5000/pypi_scraper/debezium:$DEBEZIUM_VERSION"
docker image push "rpi-cluster-4b-1gb-1:5000/pypi_scraper/debezium:latest"

docker stack deploy -c swarm.rpi-cluster.local-db.docker-compose.yml pypi_scraper
