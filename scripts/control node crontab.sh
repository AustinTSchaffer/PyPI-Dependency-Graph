# Every day at 5am UTC, kick off the PyPI->RabbitMQ refresh
0 5 * * * docker service update --replicas 1 --force pypi_scraper_pypi_loader
