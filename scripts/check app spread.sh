#!/bin/bash

echo "Service balancing: pypi_scraper_names_processor"
docker service ps pypi_scraper_names_processor --filter 'desired-state=Running' \
    | grep -E -o 'rpi-cluster-4b-4gb-[1234]' \
    | sort | uniq -c
echo ""

echo "Service balancing: pypi_scraper_dists_processor"
docker service ps pypi_scraper_dists_processor --filter 'desired-state=Running' \
    | grep -E -o 'rpi-cluster-4b-4gb-[1234]' \
    | sort | uniq -c
echo ""

echo "Service balancing: pypi_scraper_candidate_correlator"
docker service ps pypi_scraper_candidate_correlator --filter 'desired-state=Running' \
    | grep -E -o 'rpi-cluster-4b-4gb-[1234]' \
    | sort | uniq -c
echo ""
