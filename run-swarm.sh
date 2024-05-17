#!/bin/bash

export STACK_VERSION="0.10.2"

docker image build \
    -t pypi_scraper/db:latest \
    -t rpi-cluster-4b-1gb-1:5000/pypi_scraper/db:latest \
    -t "rpi-cluster-4b-1gb-1:5000/pypi_scraper/db:$STACK_VERSION" \
    -f db.Dockerfile .

docker image push "rpi-cluster-4b-1gb-1:5000/pypi_scraper/db:$STACK_VERSION"
docker image push "rpi-cluster-4b-1gb-1:5000/pypi_scraper/db:latest"

docker image build \
    -t pypi_scraper/app:latest \
    -t rpi-cluster-4b-1gb-1:5000/pypi_scraper/app:latest \
    -t "rpi-cluster-4b-1gb-1:5000/pypi_scraper/app:$STACK_VERSION" \
    -f app.Dockerfile .

docker image push "rpi-cluster-4b-1gb-1:5000/pypi_scraper/app:$STACK_VERSION"
docker image push "rpi-cluster-4b-1gb-1:5000/pypi_scraper/app:latest"

docker stack deploy -c swarm.rpi-cluster.docker-compose.yml pypi_scraper
