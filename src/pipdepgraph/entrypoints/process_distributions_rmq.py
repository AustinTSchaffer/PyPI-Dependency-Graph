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
    requirements_repository,
    versions_repository,
)

from pipdepgraph.services import (
    distribution_processing_service,
    rabbitmq_publish_service,
)

logger = logging.getLogger("pipdepgraph.entrypoints.process_distributions_rmq")


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
        rr = requirements_repository.RequirementsRepository(db_pool)

        logger.info("Initializing pypi_api.PypiApi")
        pypi = pypi_api.PypiApi(session)

        logger.info("Initializing rabbitmq_publish_service.RabbitMqPublishService")
        rmq_pub = rabbitmq_publish_service.RabbitMqPublishService(
            common.initialize_rabbitmq_connection
        )

        logger.info(
            "Initializing distribution_processing_service.DistributionProcessingService"
        )
        dps = distribution_processing_service.DistributionProcessingService(
            pnr=pnr,
            dr=dr,
            rr=rr,
            pypi=pypi,
            db_pool=db_pool,
            rmq_pub=rmq_pub,
        )

        logger.info("Starting RabbitMQ consumer thread")

        distributions_queue: queue.Queue[models.Distribution] = (
            queue.Queue()
        )
        ack_queue: queue.Queue[bool] = queue.Queue()
        consume_from_rabbitmq_thread = threading.Thread(
            target=consume_from_rabbitmq_target,
            args=[distributions_queue, ack_queue],
        )

        consume_from_rabbitmq_thread.start()

        logger.info("Running.")
        while True:
            distribution = None

            try:
                distribution = distributions_queue.get(timeout=5.0)
                await dps.process_distribution(distribution)
                ack_queue.put(True)

            except queue.Empty as ex:
                if not consume_from_rabbitmq_thread.is_alive():
                    logger.error("RabbitMQ consumer thread has died.")
                    return

            except Exception as ex:
                logger.error(
                    f"Error while handling Version Distribution message: {distribution}",
                    exc_info=ex,
                )
                ack_queue.put(False)
                raise


def consume_from_rabbitmq_target(
    distributions_queue: queue.Queue[models.Distribution],
    ack_queue: queue.Queue[bool],
):
    """
    Consumes VersionDistribution record from RabbitMQ, placing it into the `distributions_queue`.
    Expects a response on the `ack_queue` containing a single flag indicating whether
    the message should be acked or nacked.
    """

    with (
        common.initialize_rabbitmq_connection() as connection,
        connection.channel() as channel,
    ):
        channel: pika.adapters.blocking_connection.BlockingChannel
        common.declare_rabbitmq_infrastructure(channel)
        channel.basic_qos(prefetch_count=constants.RABBITMQ_DISTS_SUB_PREFETCH)

        def _distribution_consumer(
            ch: pika.channel.Channel,
            basic_deliver: pika.spec.Basic.Deliver,
            properties: pika.spec.BasicProperties,
            body: bytes,
        ):
            try:
                vd_json = json.loads(body)
                distribution = models.Distribution.from_dict(vd_json)
                distributions_queue.put(distribution)

                ack = ack_queue.get()
                if ack:
                    ch.basic_ack(basic_deliver.delivery_tag)
                else:
                    ch.basic_nack(basic_deliver.delivery_tag)
                    ch.close()

            except Exception as ex:
                logger.error(
                    f"Error while handling Distribution message: {basic_deliver}",
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
            queue=constants.RABBITMQ_DISTS_QNAME,
            on_message_callback=_distribution_consumer,
            consumer_tag=consumer_tag,
            auto_ack=False,
        )

        channel.start_consuming()


if __name__ == "__main__":
    common.initialize_logger()
    asyncio.run(main())
