import logging
import asyncio

import pika
import pika.adapters.asyncio_connection
import pika.adapters.blocking_connection
import pika.channel
import pika.delivery_mode
import pika.spec

from pipdepgraph import constants

from pipdepgraph.entrypoints import common

from pipdepgraph.repositories import (
    distributions_repository,
    package_names_repository,
)

from pipdepgraph.services import (
    rabbitmq_publish_service,
)

logger = logging.getLogger("pipdepgraph.entrypoints.unprocessed_record_loader_rmq")


async def main():
    """
    Loads unprocessed version distributions from the database into RabbitMQ.
    Loads all package names into RabbitMQ.
    """

    logger.info("Initializing DB pool")
    async with (common.initialize_async_connection_pool() as db_pool,):
        logger.info("Initializing repositories")
        pnr = package_names_repository.PackageNamesRepository(db_pool)
        dr = distributions_repository.DistributionsRepository(db_pool)

        logger.info("Initializing RabbitMQ session")
        with (
            common.initialize_rabbitmq_connection() as rabbitmq_connection,
            rabbitmq_connection.channel() as channel,
        ):
            channel: pika.adapters.blocking_connection.BlockingChannel
            common.declare_rabbitmq_infrastructure(channel)

            rmq_pub = rabbitmq_publish_service.RabbitMqPublishService(None)

            if constants.UPL_LOAD_DISTRIBUTIONS:
                logger.info(
                    "Loading all unprocessed version distributions into RabbitMQ"
                )
                async for vd in dr.iter_distributions(processed=False):
                    logger.debug(
                        "Loading unprocessed version distribution: %s",
                        vd.distribution_id,
                    )
                    rmq_pub.publish_distribution(vd, channel=channel)

            if constants.UPL_LOAD_PACKAGE_NAMES:
                logger.info("Loading all package names into RabbitMQ")
                async for kpn in pnr.iter_package_names():
                    logger.debug("Loading Package Name: %s", kpn.package_name)
                    rmq_pub.publish_package_name(kpn, channel=channel)


if __name__ == "__main__":
    common.initialize_logger()
    asyncio.run(main())
