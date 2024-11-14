import logging
import asyncio
import json
import queue
import threading
import uuid

import pika
import pika.adapters.asyncio_connection
import pika.adapters.blocking_connection
import pika.channel
import pika.delivery_mode
import pika.spec

from pipdepgraph import constants, models, pypi_api
from pipdepgraph.core import common, rabbitmq

from pipdepgraph.repositories import (
    distributions_repository,
    package_names_repository,
    versions_repository,
)

from pipdepgraph.services import (
    package_name_processing_service,
    rabbitmq_publish_service,
)

logger = logging.getLogger("pipdepgraph.entrypoints.rmq_sub.package_name_processor")


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
            rabbitmq.initialize_rabbitmq_connection
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

        logger.info("Starting RabbitMQ consumer thread")

        package_names_queue: queue.Queue[models.PackageName | str] = queue.Queue()
        ack_queue: queue.Queue[bool] = queue.Queue()

        consume_from_rabbitmq_thread = rabbitmq.start_rabbitmq_consume_thread(
            rabbitmq_queue_name=constants.RABBITMQ_NAMES_QNAME,
            prefetch_count=constants.RABBITMQ_NAMES_SUB_PREFETCH,
            model_factory=lambda _json: (
                _json if isinstance(_json, str) else models.PackageName.from_dict(_json)
            ),
            model_queue=package_names_queue,
            ack_queue=ack_queue,
        )

        logger.info("Running.")
        while True:
            package_name = None

            try:
                package_name = package_names_queue.get(timeout=5.0)
                await pnps.process_package_name(
                    package_name, ignore_date_last_checked=True
                )
                ack_queue.put(True)

            except queue.Empty as ex:
                if not consume_from_rabbitmq_thread.is_alive():
                    logger.error("RabbitMQ consumer thread has died.")
                    return

            except Exception as ex:
                logger.error(
                    f"Error while handling Package Name message: {package_name}",
                    exc_info=ex,
                )
                ack_queue.put(False)
                raise


if __name__ == "__main__":
    common.initialize_logger()
    asyncio.run(main())
