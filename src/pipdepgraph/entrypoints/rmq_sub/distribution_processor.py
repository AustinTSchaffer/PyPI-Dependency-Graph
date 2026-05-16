import logging

import msgspec.json

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

logger = logging.getLogger("pipdepgraph.entrypoints.rmq_sub.distribution_processor")


def main():
    logger.info("Initializing DB pool")
    with (
        common.initialize_connection_pool() as db_pool,
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
            rabbitmq.initialize_rabbitmq_connection
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

        logger.info("Running.")
        rabbitmq.consume_from_rabbitmq(
            rabbitmq_queue_name=constants.RABBITMQ_DISTS_QNAME,
            prefetch_count=constants.RABBITMQ_DISTS_SUB_PREFETCH,
            model_factory=lambda b: msgspec.json.decode(b, type=models.Distribution),
            on_message=dps.process_distribution,
        )


if __name__ == "__main__":
    common.initialize_logger()
    main()
