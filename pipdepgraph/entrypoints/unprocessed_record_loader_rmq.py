import logging
import asyncio

import pika
import pika.adapters.asyncio_connection
import pika.adapters.blocking_connection
import pika.channel
import pika.delivery_mode
import pika.spec

from pipdepgraph.entrypoints import common

from pipdepgraph.repositories import (
    known_package_name_repository,
    version_distribution_repository,
)

from pipdepgraph.services import (
    rabbitmq_publish_service,
)

logger = logging.getLogger('pipdepgraph.entrypoints.unprocessed_record_loader_rmq')


async def main():
    """
    Loads unprocessed version distributions from the database into RabbitMQ.
    Loads all known package names into RabbitMQ.
    """

    logger.info("Initializing DB pool")
    async with (
        common.initialize_async_connection_pool() as db_pool,
    ):
        logger.info("Initializing repositories")
        kpnr = known_package_name_repository.KnownPackageNameRepository(db_pool)
        vdr = version_distribution_repository.VersionDistributionRepository(db_pool)

        logger.info("Initializing RabbitMQ session")
        with (
            common.initialize_rabbitmq_connection() as rabbitmq_connection,
            rabbitmq_connection.channel() as channel,
        ):
            channel: pika.adapters.blocking_connection.BlockingChannel
            rmq_pub = rabbitmq_publish_service.RabbitMqPublishService(channel)

            # We're doing the downstream process first, since it takes way longer
            # to run compared to the upstream process.

            logger.info("Loading all unprocessed version distributions into RabbitMQ")
            async for vd in vdr.iter_version_distributions(processed=False):
                logger.debug("Loading unprocessed version distribution: %s", vd.version_distribution_id)
                rmq_pub.publish_version_distribution(vd)

            logger.info("Loading all known package names into RabbitMQ")
            async for kpn in kpnr.iter_known_package_names():
                logger.debug("Loading KnownPackageName: %s", kpn.package_name)
                rmq_pub.publish_known_package_name(kpn)

if __name__ == "__main__":
    common.initialize_logger()
    asyncio.run(main())
