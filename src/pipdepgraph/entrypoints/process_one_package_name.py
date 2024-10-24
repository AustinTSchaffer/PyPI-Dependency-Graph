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
    distributions_repository,
    package_names_repository,
    versions_repository,
)

from pipdepgraph.services import (
    package_name_processing_service,
    rabbitmq_publish_service,
)

logger = logging.getLogger("pipdepgraph.entrypoints.process_one_package_name")


async def main():
    logger.info("Initializing DB pool")
    async with (
        common.initialize_async_connection_pool() as db_pool,
        common.initialize_client_session() as session,
    ):
        logger.info("Initializing repositories")
        pnr = package_names_repository.PackageNamesRepository(db_pool)
        vr = versions_repository.VersionsRepository(db_pool)
        dr = distributions_repository.DistributionsRepository(db_pool)

        logger.info("Initializing pypi_api.PypiApi")
        pypi = pypi_api.PypiApi(session)

        logger.info("Initializing rabbitmq_publish_service.RabbitMqPublishService")
        rmq_pub = rabbitmq_publish_service.RabbitMqPublishService(
            common.initialize_rabbitmq_connection
        )

        logger.info(
            "Initializing package_name_processing_service.PackageNameProcessingService"
        )
        pnps = package_name_processing_service.PackageNameProcessingService(
            pnr=pnr,
            vr=vr,
            dr=dr,
            pypi=pypi,
            db_pool=db_pool,
            rmq_pub=rmq_pub,
        )

        logger.info("Running.")
        package_name = os.getenv("PACKAGE_NAME", "ardianmaliqaj")

        try:
            await pnps.process_package_name(
                package_name, ignore_date_last_checked=True
            )

        except Exception as ex:
            logger.error(
                f"Error while handling Package Name: {package_name}",
                exc_info=ex,
            )
            raise


if __name__ == "__main__":
    common.initialize_logger()
    asyncio.run(main())
