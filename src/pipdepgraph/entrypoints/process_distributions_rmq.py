import logging
import asyncio
import queue

from pipdepgraph import constants, models, pypi_api
from pipdepgraph.core import common, rabbitmq

from pipdepgraph.repositories import (
    distributions_repository,
    package_names_repository,
    requirements_repository,
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

        consume_from_rabbitmq_thread = rabbitmq.start_rabbitmq_consume_thread(
            rabbitmq_queue_name=constants.RABBITMQ_DISTS_QNAME,
            prefetch_count=constants.RABBITMQ_DISTS_SUB_PREFETCH,
            model_factory=models.Distribution.from_dict,
            model_queue=distributions_queue,
            ack_queue=ack_queue,
        )

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


if __name__ == "__main__":
    common.initialize_logger()
    asyncio.run(main())
