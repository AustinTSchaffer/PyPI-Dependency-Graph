import logging

import msgspec.json

from pipdepgraph import constants, models
from pipdepgraph.core import rabbitmq
from pipdepgraph.core import common

from pipdepgraph.services import candidate_correlation_service

from pipdepgraph.repositories import (
    versions_repository,
    requirements_repository,
    candidates_repository,
)

logger = logging.getLogger(
    "pipdepgraph.entrypoints.rmq_sub.candidate_correlation"
)


def main():
    logger.info("Initializing DB pool")
    with (common.initialize_connection_pool() as db_pool,):
        logger.info("Initializing repositories")
        vr = versions_repository.VersionsRepository(db_pool)
        rr = requirements_repository.RequirementsRepository(db_pool)
        cr = candidates_repository.CandidatesRepository(db_pool)

        logger.info(
            "Initializing candidate_correlation_service.CandidateCorrelationService"
        )

        ccs = candidate_correlation_service.CandidateCorrelationService(
            db_pool=db_pool,
            rr=rr,
            vr=vr,
            cr=cr,
        )

        logger.info("Running.")
        rabbitmq.consume_from_rabbitmq(
            rabbitmq_queue_name=constants.RABBITMQ_VERS_CAND_CORR_QNAME,
            prefetch_count=constants.RABBITMQ_VERS_CAND_CORR_SUB_PREFETCH,
            model_factory=lambda b: msgspec.json.decode(b, type=models.Version),
            on_message=ccs.process_version_record,
        )


if __name__ == "__main__":
    common.initialize_logger()
    main()
