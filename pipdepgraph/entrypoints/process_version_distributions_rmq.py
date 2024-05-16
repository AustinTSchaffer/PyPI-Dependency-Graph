import logging
import asyncio
import json

import pika
import pika.channel
import pika.delivery_mode
import pika.spec

from pipdepgraph import constants, models, pypi_api
from pipdepgraph.entrypoints import common

from pipdepgraph.repositories import (
    direct_dependency_repository,
    known_package_name_repository,
    known_version_repository,
    version_distribution_repository,
)

from pipdepgraph.services import (
    known_packages_processing_service,
    version_distribution_processing_service,
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

        vdps = version_distribution_processing_service.VersionDistributionProcessingService(
            vdr=vdr, ddr=ddr, pypi=pypi
        )

        channel = None

        try:
            channel = rabbitmq_connection.channel()

            channel.exchange_declare(
                constants.RABBITMQ_EXCHANGE, exchange_type="topic", durable=True
            )
            channel.queue_declare(constants.RABBITMQ_VD_QNAME, durable=True)

            @common.synchronous
            def _version_distribution_consumer(
                ch: pika.channel.Channel,
                method: pika.spec.Basic.Deliver,
                properties: pika.spec.BasicProperties,
                body: bytes,
            ):
                try:
                    vd_json = json.loads(body)
                    vd = models.VersionDistribution.from_dict(vd_json)
                    asyncio.get_event_loop().run_until_complete(
                        vdps.process_version_distribution(vd)
                    )
                except Exception as ex:
                    logger.error(
                        f"Error while handling Version Distribution message: {method}",
                        exc_info=ex,
                    )
                    ch.basic_nack(method.delivery_tag)
                    return

                ch.basic_ack(method.delivery_tag)

            channel.queue_bind(
                exchange=constants.RABBITMQ_EXCHANGE,
                queue=constants.RABBITMQ_VD_QNAME,
                routing_key=constants.RABBITMQ_VD_RK,
            )

            channel.basic_consume(
                queue=constants.RABBITMQ_VD_QNAME,
                on_message_callback=_version_distribution_consumer,
                auto_ack=False,
            )

            channel.start_consuming()

        finally:
            if channel and channel.is_open:
                channel.close()
            if rabbitmq_connection and rabbitmq_connection.is_open:
                rabbitmq_connection.close()


if __name__ == "__main__":
    common.initialize_logger()
    asyncio.run(main())
