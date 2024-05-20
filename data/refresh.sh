#!/bin/bash

curl https://pypi.org/simple/ > data/pypi-simple-index.html

mv data/pypi-simple-index-prefixes.csv data/pypi-simple-index-prefixes.csv.backup

echo "prefix,count" | tee -a data/pypi-simple-index-prefixes.csv
echo ",$(cat data/pypi-simple-index.html | grep "/simple/" | wc -l)" | tee -a data/pypi-simple-index-prefixes.csv

for c in {0..9}
do
    echo "$c,$(cat data/pypi-simple-index.html | grep "/simple/$c" | wc -l)" | tee -a data/pypi-simple-index-prefixes.csv
done

for c in {a..z}
do
    echo "$c,$(cat data/pypi-simple-index.html | grep "/simple/$c" | wc -l)" | tee -a data/pypi-simple-index-prefixes.csv
done

