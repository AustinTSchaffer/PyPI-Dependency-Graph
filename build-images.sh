#!/bin/bash

docker image build \
    -t pypi_scraper/db \
    -t rpi-cluster-4b-1gb-1:5000/pypi_scraper/db:latest \
    -f db.Dockerfile .

docker image build \
    -t pypi_scraper/app \
    -t rpi-cluster-4b-1gb-1:5000/pypi_scraper/db:latest \
    -f app.Dockerfile .
