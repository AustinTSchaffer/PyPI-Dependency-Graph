# Every day at 5am UTC, kick off the PyPI->RabbitMQ refresh
0 5 * * * docker service update --replicas 1 --force pypi_scraper_pypi_loader

# Every day at 7am UTC, kick off the DB->RabbitMQ refresh
0 7 * * * docker service update --replicas 1 --force pypi_scraper_unprocessed_record_loader
