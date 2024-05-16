#!/bin/bash

export STACK_VERSION="0.8.0"

docker image build \
    -t pypi_scraper/db:latest \
    -t rpi-cluster-4b-1gb-1:5000/pypi_scraper/db:latest \
    -t "rpi-cluster-4b-1gb-1:5000/pypi_scraper/db:$STACK_VERSION" \
    -f db.Dockerfile .

docker image push --all-tags rpi-cluster-4b-1gb-1:5000/pypi_scraper/db

docker image build \
    -t pypi_scraper/app:latest \
    -t rpi-cluster-4b-1gb-1:5000/pypi_scraper/app:latest \
    -t "rpi-cluster-4b-1gb-1:5000/pypi_scraper/app:$STACK_VERSION" \
    -f app.Dockerfile .

docker image push --all-tags rpi-cluster-4b-1gb-1:5000/pypi_scraper/app

docker stack deploy -c swarm.rpi-cluster.docker-compose.yml pypi_scraper
