import logging

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

        def process(requirement: models.Requirement) -> None:
            logger.debug("Correlating candidates for requirement: %s", requirement)
            ccs.process_requirement_record(requirement)

        logger.info("Running.")
        rabbitmq.consume_from_rabbitmq(
            rabbitmq_queue_name=constants.RABBITMQ_REQS_CAND_CORR_QNAME,
            prefetch_count=constants.RABBITMQ_REQS_CAND_CORR_SUB_PREFETCH,
            model_factory=models.Requirement.from_dict,
            on_message=process,
        )


if __name__ == "__main__":
    common.initialize_logger()
    main()
