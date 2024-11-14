import logging
import asyncio
import re

import pika
import pika.adapters.blocking_connection

from pipdepgraph import pypi_api, constants
from pipdepgraph.core import common, rabbitmq

from pipdepgraph.repositories import (
    package_names_repository,
)

from pipdepgraph.services import (
    rabbitmq_publish_service,
)

logger = logging.getLogger("pipdepgraph.entrypoints.rmq_pub.pypi_package_names")


async def main():
    logger.info("Initializing DB pool")
    async with (
        common.initialize_async_connection_pool() as db_pool,
        common.initialize_client_session() as session,
    ):
        logger.info("Initializing repositories")
        pnr = package_names_repository.PackageNamesRepository(db_pool)
        pypi = pypi_api.PypiApi(session)

        logger.info("Initializing RabbitMQ session")
        with (
            rabbitmq.initialize_rabbitmq_connection() as rabbitmq_connection,
            rabbitmq_connection.channel() as channel,
        ):
            channel: pika.adapters.blocking_connection.BlockingChannel
            rabbitmq.declare_rabbitmq_infrastructure(channel)

            rmq_pub = rabbitmq_publish_service.RabbitMqPublishService(None)

            prefix_regex = constants.POPULAR_PACKAGE_LOADER_PREFIX_REGEX

            logger.info(
                f"Fetching list of packages from PyPI with prefix: r'{prefix_regex.pattern}'"
            )

            prefix_regex = re.compile(prefix_regex)

            processing_prefix = False
            package_names = []
            async for package_name in pypi.iter_all_package_names_regex():
                if prefix_regex.match(package_name):
                    processing_prefix = True
                    package_names.append(package_name)
                elif processing_prefix:
                    break

            logger.info(f"Inserting {len(package_names)} package names into Postgres")
            packages_inserted = await pnr.insert_package_names(
                package_names,
                return_inserted=constants.POPULAR_PACKAGE_LOADER_COUNT_INSERTED,
            )

            if constants.POPULAR_PACKAGE_LOADER_COUNT_INSERTED:
                logger.info(f"{len(packages_inserted)} new packages found.")
                if packages_inserted:
                    logger.info(
                        f"Publishing {len(packages_inserted)} new packages to RabbitMQ"
                    )
                    for new_package in packages_inserted:
                        rmq_pub.publish_package_name(new_package, channel=channel)

            logger.info(f"Publishing {len(package_names)} package names to RabbitMQ")
            for package_name in package_names:
                rmq_pub.publish_package_name(package_name, channel=channel)


if __name__ == "__main__":
    common.initialize_logger()
    asyncio.run(main())
