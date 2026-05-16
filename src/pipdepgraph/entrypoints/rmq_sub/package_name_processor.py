import logging

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


def main():
    logger.info("Initializing DB pool")
    with (
        common.initialize_connection_pool() as db_pool,
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

        logger.info("Running.")
        rabbitmq.consume_from_rabbitmq(
            rabbitmq_queue_name=constants.RABBITMQ_NAMES_QNAME,
            prefetch_count=constants.RABBITMQ_NAMES_SUB_PREFETCH,
            model_factory=lambda _json: (
                _json if isinstance(_json, str) else models.PackageName.from_dict(_json)
            ),
            on_message=lambda model: pnps.process_package_name(
                model, ignore_date_last_checked=True
            ),
        )


if __name__ == "__main__":
    common.initialize_logger()
    main()
