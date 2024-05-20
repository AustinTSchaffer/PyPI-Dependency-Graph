import logging
import asyncio
import re

import pika
import pika.adapters.blocking_connection

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
        common.initialize_client_session() as client,
    ):
        logger.info("Initializing repositories")
        kpnr = known_package_name_repository.KnownPackageNameRepository(db_pool)

        logger.info("Initializing RabbitMQ session")
        with (
            common.initialize_rabbitmq_connection() as rabbitmq_connection,
            rabbitmq_connection.channel() as channel,
        ):
            channel: pika.adapters.blocking_connection.BlockingChannel
            common.declare_rabbitmq_infrastructure(channel)

            rmq_pub = rabbitmq_publish_service.RabbitMqPublishService(None)

            prefix_regex = r"[hijklmno]"

            logger.info(
                rf"Fetching list of packages from PyPI with prefix: r'{prefix_regex}'"
            )
            result = await client.get("https://pypi.org/simple/")
            if not result.ok:
                raise ValueError(result)

            processing_prefix = False
            prefix_regex = re.compile(rf"/simple/({prefix_regex}[^/]*)/")
            package_names = []
            async for line in result.content:
                try:
                    if re_result := prefix_regex.search(line.decode("utf-8")):
                        processing_prefix = True
                        package_names.append(re_result[1])
                    elif processing_prefix:
                        break
                except Exception as ex:
                    logger.error(
                        f"Error processing line from simple index: {line}", exc_info=ex
                    )
                    continue

            logger.info(f"Inserting {len(package_names)} package names into Postgres")
            await kpnr.insert_known_package_names(package_names)

            logger.info(f"Publishing {len(package_names)} package names to RabbitMQ")
            for package_name in package_names:
                rmq_pub.publish_known_package_name(package_name, channel=channel)


if __name__ == "__main__":
    common.initialize_logger()
    asyncio.run(main())
