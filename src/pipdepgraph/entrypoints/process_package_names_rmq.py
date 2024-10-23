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

logger = logging.getLogger("pipdepgraph.entrypoints.process_package_names_rmq")


async def main():
    logger.info("Initializing DB pool")
    async with (
        common.initialize_async_connection_pool() as db_pool,
        common.initialize_client_session() as session,
    ):
        logger.info("Initializing repositories")
        kpnr = package_names_repository.PackageNamesRepository(db_pool)
        kvr = versions_repository.VersionsRepository(db_pool)
        vdr = distributions_repository.DistributionsRepository(db_pool)

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
            kpnr=kpnr,
            kvr=kvr,
            vdr=vdr,
            pypi=pypi,
            db_pool=db_pool,
            rmq_pub=rmq_pub,
        )

        logger.info("Starting RabbitMQ consumer thread")

        package_names_queue: queue.Queue[models.PackageName | str] = (
            queue.Queue()
        )
        ack_queue: queue.Queue[bool] = queue.Queue()
        consume_from_rabbitmq_thread = threading.Thread(
            target=consume_from_rabbitmq_target,
            args=[package_names_queue, ack_queue],
        )

        consume_from_rabbitmq_thread.start()

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


def consume_from_rabbitmq_target(
    package_names_queue: queue.Queue[models.PackageName | str],
    ack_queue: queue.Queue[bool],
):
    """
    Consumes PackageName records from RabbitMQ, placing it into the `out_queue`.
    Expects a response on the `in_queue` containing a single flag indicating whether
    the message should be acked or nacked.
    """

    with (
        common.initialize_rabbitmq_connection() as connection,
        connection.channel() as channel,
    ):
        channel: pika.adapters.blocking_connection.BlockingChannel
        common.declare_rabbitmq_infrastructure(channel)
        channel.basic_qos(prefetch_count=constants.RABBITMQ_NAMES_SUB_PREFETCH)

        def _package_name_consumer(
            ch: pika.channel.Channel,
            basic_deliver: pika.spec.Basic.Deliver,
            properties: pika.spec.BasicProperties,
            body: bytes,
        ):
            try:
                package_name_json = json.loads(body)
                if isinstance(package_name_json, str):
                    package_names_queue.put(package_name_json)
                else:
                    package_name = models.PackageName.from_dict(package_name_json)
                    package_names_queue.put(package_name)

                ack = ack_queue.get()

                if ack:
                    ch.basic_ack(basic_deliver.delivery_tag)
                else:
                    ch.basic_nack(basic_deliver.delivery_tag)
                    ch.close()

            except Exception as ex:
                logger.error(
                    f"Error while handling Package Name message: {basic_deliver}",
                    exc_info=ex,
                )
                ch.basic_nack(basic_deliver.delivery_tag)
                ch.close()
                raise

        consumer_tag = None
        if constants.RABBITMQ_CTAG_PREFIX:
            consumer_tag = f"{constants.RABBITMQ_CTAG_PREFIX}{uuid.uuid4()}"
            logger.info("Starting RabbitMQ consumer with ctag: %s", consumer_tag)

        channel.basic_consume(
            queue=constants.RABBITMQ_NAMES_QNAME,
            on_message_callback=_package_name_consumer,
            consumer_tag=consumer_tag,
            auto_ack=False,
        )

        channel.start_consuming()


if __name__ == "__main__":
    common.initialize_logger()
    asyncio.run(main())
