import logging
import asyncio
import re

import pika
import pika.adapters.blocking_connection

from pipdepgraph import pypi_api
from pipdepgraph.entrypoints import common

from pipdepgraph.repositories import (
    known_package_name_repository,
)

from pipdepgraph.services import (
    rabbitmq_publish_service,
)

logger = logging.getLogger("pipdepgraph.entrypoints.load_from_pypi_simple_index")


async def main():
    logger.info("Initializing DB pool")
    async with (
        common.initialize_async_connection_pool() as db_pool,
        common.initialize_client_session() as session,
    ):
        logger.info("Initializing repositories")
        kpnr = known_package_name_repository.KnownPackageNameRepository(db_pool)
        pypi = pypi_api.PypiApi(session)

        logger.info("Initializing RabbitMQ session")
        with (
            common.initialize_rabbitmq_connection() as rabbitmq_connection,
            rabbitmq_connection.channel() as channel,
        ):
            channel: pika.adapters.blocking_connection.BlockingChannel
            common.declare_rabbitmq_infrastructure(channel)

            rmq_pub = rabbitmq_publish_service.RabbitMqPublishService(None)

            prefix_regex = r"^"

            logger.info(
                rf"Fetching list of packages from PyPI with prefix: r'{prefix_regex}'"
            )

            prefix_regex = re.compile(prefix_regex)

            processing_prefix = False
            package_names = []
            async for package_name in pypi.iter_all_package_names():
                if prefix_regex.match(package_name):
                    processing_prefix = True
                    package_names.append(package_name)
                elif processing_prefix:
                    break

            logger.info(f"Inserting {len(package_names)} package names into Postgres")
            await kpnr.insert_known_package_names(package_names)

            logger.info(f"Publishing {len(package_names)} package names to RabbitMQ")
            for package_name in package_names:
                rmq_pub.publish_known_package_name(package_name, channel=channel)


if __name__ == "__main__":
    common.initialize_logger()
    asyncio.run(main())
