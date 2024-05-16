#!/bin/bash

version="0.3.0"

docker image build \
    -t pypi_scraper/db:latest \
    -t rpi-cluster-4b-1gb-1:5000/pypi_scraper/db:latest \
    -t "rpi-cluster-4b-1gb-1:5000/pypi_scraper/db:$version" \
    -f db.Dockerfile .

docker image push --all-tags rpi-cluster-4b-1gb-1:5000/pypi_scraper/db

docker image build \
    -t pypi_scraper/app:latest \
    -t rpi-cluster-4b-1gb-1:5000/pypi_scraper/app:latest \
    -t "rpi-cluster-4b-1gb-1:5000/pypi_scraper/app:$version" \
    -f app.Dockerfile .

docker image push --all-tags rpi-cluster-4b-1gb-1:5000/pypi_scraper/app

docker stack deploy 
