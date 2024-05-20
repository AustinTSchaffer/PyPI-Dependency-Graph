import logging
import asyncio

import pika
import pika.adapters.blocking_connection

from pipdepgraph.entrypoints import common

from pipdepgraph.repositories import (
    known_package_name_repository,
)

from pipdepgraph.services import (
    rabbitmq_publish_service,
)

logger = logging.getLogger("pipdepgraph.entrypoints.load_top_8000_package_names")


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

            logger.info("Fetching list of top packages")
            result = await client.get(
                "https://hugovk.github.io/top-pypi-packages/top-pypi-packages-30-days.min.json"
            )
            if not result.ok:
                raise ValueError(result)

            package_list = await result.json()
            package_names = [row["project"] for row in package_list["rows"]]

            await kpnr.insert_known_package_names(package_names)

            for package_name in package_names:
                rmq_pub.publish_known_package_name(package_name, channel=channel)


if __name__ == "__main__":
    common.initialize_logger()
    asyncio.run(main())
