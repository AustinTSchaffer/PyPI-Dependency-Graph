import logging
import asyncio
import json
import queue
import uuid
import os

import pika
import pika.adapters.asyncio_connection
import pika.adapters.blocking_connection
import pika.channel
import pika.delivery_mode
import pika.spec

from pipdepgraph import constants, models, pypi_api
from pipdepgraph.entrypoints import common

from pipdepgraph.repositories import (
    known_package_name_repository,
    known_version_repository,
    version_distribution_repository,
)

from pipdepgraph.services import (
    known_packages_processing_service,
    rabbitmq_publish_service,
)

logger = logging.getLogger("pipdepgraph.entrypoints.process_one_known_package_name")


async def main():
    logger.info("Initializing DB pool")
    async with (
        common.initialize_async_connection_pool() as db_pool,
        common.initialize_client_session() as session,
    ):
        logger.info("Initializing repositories")
        kpnr = known_package_name_repository.KnownPackageNameRepository(db_pool)
        kvr = known_version_repository.KnownVersionRepository(db_pool)
        vdr = version_distribution_repository.VersionDistributionRepository(db_pool)

        logger.info("Initializing pypi_api.PypiApi")
        pypi = pypi_api.PypiApi(session)

        logger.info("Initializing rabbitmq_publish_service.RabbitMqPublishService")
        rmq_pub = rabbitmq_publish_service.RabbitMqPublishService(
            common.initialize_rabbitmq_connection
        )

        logger.info(
            "Initializing known_packages_processing_service.KnownPackageProcessingService"
        )
        kpps = known_packages_processing_service.KnownPackageProcessingService(
            kpnr=kpnr,
            kvr=kvr,
            vdr=vdr,
            pypi=pypi,
            db_pool=db_pool,
            rmq_pub=rmq_pub,
        )

        logger.info("Running.")
        known_package_name = os.getenv("KNOWN_PACKAGE_NAME", "ardianmaliqaj")

        try:
            await kpps.process_package_name(
                known_package_name, ignore_date_last_checked=True
            )

        except Exception as ex:
            logger.error(
                f"Error while handling Known Package Name: {known_package_name}",
                exc_info=ex,
            )
            raise


if __name__ == "__main__":
    common.initialize_logger()
    asyncio.run(main())
