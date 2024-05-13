#!/bin/bash

docker image build -t pypi_scraper/db -f db.Dockerfile
docker image build -t pypi_scraper/app -f app.Dockerfile
