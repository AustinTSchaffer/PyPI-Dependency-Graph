#!/bin/bash

docker image build \
    -t pypi_scraper/db \
    -t rpi-cluster-4b-1gb-1:5000/pypi_scraper/db:latest \
    -f db.Dockerfile .

docker image build \
    -t pypi_scraper/app \
    -t rpi-cluster-4b-1gb-1:5000/pypi_scraper/app:latest \
    -f app.Dockerfile .

docker image push rpi-cluster-4b-1gb-1:5000/pypi_scraper/db:latest
docker image push rpi-cluster-4b-1gb-1:5000/pypi_scraper/app:latest

docker image prune -a

docker stack deploy -c swarm.rpi-cluster.docker-compose.yml pypi_scraper
