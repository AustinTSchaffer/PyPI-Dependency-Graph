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
    known_package_name_repository,
    known_version_repository,
    version_distribution_repository,
)

from pipdepgraph.services import (
    known_packages_processing_service,
    rabbitmq_publish_service,
)

logger = logging.getLogger('pipdepgraph.entrypoints.process_known_package_names_rmq')


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

        logger.info("Initializing RabbitMQ Connection")
        with (
            common.initialize_rabbitmq_connection() as rabbitmq_connection,
            rabbitmq_connection.channel() as channel,
        ):
            channel: pika.adapters.blocking_connection.BlockingChannel

            logger.info("Initializing rabbitmq_publish_service.RabbitMqPublishService")
            rmq_pub = rabbitmq_publish_service.RabbitMqPublishService(channel)

            logger.info("Initializing known_packages_processing_service.KnownPackageProcessingService")
            kpps = known_packages_processing_service.KnownPackageProcessingService(
                kpnr=kpnr,
                kvr=kvr,
                vdr=vdr,
                pypi=pypi,
                rmq_pub=rmq_pub,
            )

            logger.info("Starting RabbitMQ consumer thread")

            known_package_names_queue: queue.Queue[models.KnownPackageName | str] = queue.Queue()
            ack_queue: queue.Queue[bool] = queue.Queue()
            consume_from_rabbitmq_thread = threading.Thread(
                target=consume_from_rabbitmq_target,
                args=[known_package_names_queue, ack_queue],
            )

            consume_from_rabbitmq_thread.start()

            logger.info("Running.")
            while True:
                known_package_name = None

                try:
                    known_package_name = known_package_names_queue.get(timeout=5.0)
                    await kpps.process_package_name(known_package_name, ignore_date_last_checked=True)
                    ack_queue.put(True)

                except queue.Empty as ex:
                    if not consume_from_rabbitmq_thread.is_alive():
                        logger.error("RabbitMQ consumer thread has died.")
                        return

                except Exception as ex:
                    logger.error(
                        f"Error while handling Known Package Name message: {known_package_name}",
                        exc_info=ex,
                    )
                    ack_queue.put(False)


def consume_from_rabbitmq_target(
    known_package_names_queue: queue.Queue[models.KnownPackageName | str],
    ack_queue: queue.Queue[bool],
):
    """
    Consumes KnownPackageName record from RabbitMQ, placing it into the `out_queue`.
    Expects a response on the `in_queue` containing a single flag indicating whether
    the message should be acked or nacked.
    """

    with (
        common.initialize_rabbitmq_connection() as connection,
        connection.channel() as channel,
    ):
        channel: pika.adapters.blocking_connection.BlockingChannel
        common.declare_rabbitmq_infrastructure(channel)

        def _known_package_name_consumer(
            ch: pika.channel.Channel,
            basic_deliver: pika.spec.Basic.Deliver,
            properties: pika.spec.BasicProperties,
            body: bytes,
        ):
            try:
                package_name_json = json.loads(body)
                if isinstance(package_name_json, str):
                    known_package_names_queue.put(package_name_json)
                else:
                    package_name = models.KnownPackageName.from_dict(package_name_json)
                    known_package_names_queue.put(package_name)

                ack = ack_queue.get()
                if ack:
                    ch.basic_ack(basic_deliver.delivery_tag)
                else:
                    ch.basic_nack(basic_deliver.delivery_tag)

            except Exception as ex:
                logger.error(
                    f"Error while handling Known Package Name message: {basic_deliver}",
                    exc_info=ex,
                )
                ch.basic_nack(basic_deliver.delivery_tag)

        consumer_tag = None
        if constants.RABBITMQ_CTAG_PREFIX:
            consumer_tag = f"{constants.RABBITMQ_CTAG_PREFIX}{uuid.uuid4()}"
            logger.info("Starting RabbitMQ consumer with ctag: %s", consumer_tag)

        channel.basic_consume(
            queue=constants.RABBITMQ_KPN_QNAME,
            on_message_callback=_known_package_name_consumer,
            consumer_tag=consumer_tag,
            auto_ack=False,
        )

        channel.start_consuming()


if __name__ == "__main__":
    common.initialize_logger()
    asyncio.run(main())
