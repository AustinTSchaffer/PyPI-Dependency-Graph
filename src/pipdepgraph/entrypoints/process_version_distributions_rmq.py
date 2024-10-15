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
    direct_dependency_repository,
)

from pipdepgraph.services import (
    version_distribution_processing_service,
    rabbitmq_publish_service,
)

logger = logging.getLogger("pipdepgraph.entrypoints.process_version_distributions_rmq")


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
        ddr = direct_dependency_repository.DirectDependencyRepository(db_pool)

        logger.info("Initializing pypi_api.PypiApi")
        pypi = pypi_api.PypiApi(session)

        logger.info("Initializing rabbitmq_publish_service.RabbitMqPublishService")
        rmq_pub = rabbitmq_publish_service.RabbitMqPublishService(
            common.initialize_rabbitmq_connection
        )

        logger.info(
            "Initializing version_distribution_processing_service.VersionDistributionProcessingService"
        )
        vdps = version_distribution_processing_service.VersionDistributionProcessingService(
            kpnr=kpnr,
            vdr=vdr,
            ddr=ddr,
            pypi=pypi,
            db_pool=db_pool,
            rmq_pub=rmq_pub,
        )

        logger.info("Starting RabbitMQ consumer thread")

        version_distributions_queue: queue.Queue[models.VersionDistribution] = (
            queue.Queue()
        )
        ack_queue: queue.Queue[bool] = queue.Queue()
        consume_from_rabbitmq_thread = threading.Thread(
            target=consume_from_rabbitmq_target,
            args=[version_distributions_queue, ack_queue],
        )

        consume_from_rabbitmq_thread.start()

        logger.info("Running.")
        while True:
            version_distribution = None

            try:
                version_distribution = version_distributions_queue.get(timeout=5.0)
                await vdps.process_version_distribution(version_distribution)
                ack_queue.put(True)

            except queue.Empty as ex:
                if not consume_from_rabbitmq_thread.is_alive():
                    logger.error("RabbitMQ consumer thread has died.")
                    return

            except Exception as ex:
                logger.error(
                    f"Error while handling Version Distribution message: {version_distribution}",
                    exc_info=ex,
                )
                ack_queue.put(False)
                raise


def consume_from_rabbitmq_target(
    version_distributions_queue: queue.Queue[models.VersionDistribution],
    ack_queue: queue.Queue[bool],
):
    """
    Consumes VersionDistribution record from RabbitMQ, placing it into the `version_distributions_queue`.
    Expects a response on the `ack_queue` containing a single flag indicating whether
    the message should be acked or nacked.
    """

    with (
        common.initialize_rabbitmq_connection() as connection,
        connection.channel() as channel,
    ):
        channel: pika.adapters.blocking_connection.BlockingChannel
        common.declare_rabbitmq_infrastructure(channel)
        channel.basic_qos(prefetch_count=constants.RABBITMQ_VD_SUB_PREFETCH)

        def _version_distribution_consumer(
            ch: pika.channel.Channel,
            basic_deliver: pika.spec.Basic.Deliver,
            properties: pika.spec.BasicProperties,
            body: bytes,
        ):
            try:
                vd_json = json.loads(body)
                version_distribution = models.VersionDistribution.from_dict(vd_json)
                version_distributions_queue.put(version_distribution)

                ack = ack_queue.get()
                if ack:
                    ch.basic_ack(basic_deliver.delivery_tag)
                else:
                    ch.basic_nack(basic_deliver.delivery_tag)
                    ch.close()

            except Exception as ex:
                logger.error(
                    f"Error while handling Version Distribution message: {basic_deliver}",
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
            queue=constants.RABBITMQ_VD_QNAME,
            on_message_callback=_version_distribution_consumer,
            consumer_tag=consumer_tag,
            auto_ack=False,
        )

        channel.start_consuming()


if __name__ == "__main__":
    common.initialize_logger()
    asyncio.run(main())
