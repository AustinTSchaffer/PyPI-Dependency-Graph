import logging

import pika
import pika.adapters.blocking_connection
import pika.channel
import pika.delivery_mode
import pika.spec

from pipdepgraph import constants

from pipdepgraph.core import common, rabbitmq

from pipdepgraph.repositories import (
    distributions_repository,
    package_names_repository,
    requirements_repository,
)

from pipdepgraph.services import (
    rabbitmq_publish_service,
)

logger = logging.getLogger("pipdepgraph.entrypoints.rmq_pub.unprocessed_records")


def main():
    """
    Loads unprocessed version distributions from the database into RabbitMQ.
    Loads all package names into RabbitMQ.
    """

    logger.info("Initializing DB pool")
    with (common.initialize_connection_pool() as db_pool,):
        logger.info("Initializing repositories")
        pnr = package_names_repository.PackageNamesRepository(db_pool)
        dr = distributions_repository.DistributionsRepository(db_pool)
        rr = requirements_repository.RequirementsRepository(db_pool)

        logger.info("Initializing RabbitMQ session")
        with (
            rabbitmq.initialize_rabbitmq_connection() as rabbitmq_connection,
            rabbitmq_connection.channel() as channel,
        ):
            channel: pika.adapters.blocking_connection.BlockingChannel
            rabbitmq.declare_rabbitmq_infrastructure(channel)

            rmq_pub = rabbitmq_publish_service.RabbitMqPublishService(None)

            if constants.UPL_LOAD_DISTRIBUTIONS:
                package_type = (
                    'bdist_wheel' if constants.UPL_ONLY_LOAD_BDIST_WHEEL_DISTRIBUTIONS else None
                )

                processed = False if constants.UPL_ONLY_LOAD_UNPROCESSED_DISTRIBUTIONS else None

                logger.info(
                    "Loading distributions into RabbitMQ. (package_type=%s, processed=%s)",
                    package_type,
                    processed,
                )

                for vd in dr.iter_distributions(
                    processed=processed,
                    package_type=package_type
                ):
                    logger.debug(
                        "Loading unprocessed version distribution: %s",
                        vd.distribution_id,
                    )
                    rmq_pub.publish_distribution(vd, channel=channel)

            if constants.UPL_LOAD_PACKAGE_NAMES:
                logger.info("Loading all package names into RabbitMQ")
                for kpn in pnr.iter_package_names():
                    logger.debug("Loading Package Name: %s", kpn.package_name)
                    rmq_pub.publish_package_name(kpn, channel=channel)

            if constants.UPL_LOAD_REQUIREMENTS_FOR_CANDIDATE_CORRELATION:
                logger.info("Loading all requirements records into RabbitMQ")
                for req in rr.iter_requirements():
                    logger.debug("Loading Requirement: %s", req)
                    rmq_pub.publish_requirement_for_candidate_correlation(req, channel=channel)

if __name__ == "__main__":
    common.initialize_logger()
    main()
