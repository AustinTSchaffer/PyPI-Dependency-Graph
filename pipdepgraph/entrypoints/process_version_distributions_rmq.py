import logging
import asyncio
import json
import queue
import threading
import time

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

logger = logging.getLogger(__name__)


async def main():
    async with (
        common.initialize_async_connection_pool() as db_pool,
        common.initialize_client_session() as session,
    ):
        kpnr = known_package_name_repository.KnownPackageNameRepository(db_pool)
        kvr = known_version_repository.KnownVersionRepository(db_pool)
        vdr = version_distribution_repository.VersionDistributionRepository(db_pool)
        ddr = direct_dependency_repository.DirectDependencyRepository(db_pool)

        rabbitmq_connection = common.initialize_rabbitmq_connection()

        pypi = pypi_api.PypiApi(session)

        with (
            common.initialize_rabbitmq_connection() as rabbitmq_connection,
            rabbitmq_connection.channel() as channel,
        ):
            channel: pika.adapters.blocking_connection.BlockingChannel

            rmq_pub = rabbitmq_publish_service.RabbitMqPublishService(channel)

            vdps = version_distribution_processing_service.VersionDistributionProcessingService(
                kpnr=kpnr,
                vdr=vdr,
                ddr=ddr,
                pypi=pypi,
                rmq_pub=rmq_pub,
            )

            version_distributions_queue: queue.Queue[models.VersionDistribution] = queue.Queue()
            ack_queue: queue.Queue[bool] = queue.Queue()

            consume_from_rabbitmq_thread = threading.Thread(
                target=consume_from_rabbitmq_target,
                args=[version_distributions_queue, ack_queue],
            )

            consume_from_rabbitmq_thread.start()

            while True:
                version_distribution = None
                basic_deliver = None

                try:
                    version_distribution = version_distributions_queue.get(timeout=5.0)
                    await vdps.process_version_distribution(version_distribution)
                    ack_queue.put(True)

                except queue.Empty as ex:
                    if not consume_from_rabbitmq_thread.is_alive():
                        logger.error("RabbitMQ consumer thread has died.")
                        break

                except Exception as ex:
                    logger.error(
                        f"Error while handling Version Distribution message: {version_distribution} {basic_deliver}",
                        exc_info=ex,
                    )
                    ack_queue.put(False)


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

            except Exception as ex:
                logger.error(
                    f"Error while handling Version Distribution message: {basic_deliver}",
                    exc_info=ex,
                )
                ch.basic_nack(basic_deliver.delivery_tag)

        channel.basic_consume(
            queue=constants.RABBITMQ_VD_QNAME,
            on_message_callback=_version_distribution_consumer,
            auto_ack=False,
        )

        channel.start_consuming()


if __name__ == "__main__":
    common.initialize_logger()
    asyncio.run(main())
