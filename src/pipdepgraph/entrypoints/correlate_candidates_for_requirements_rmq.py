import logging
import asyncio
import queue

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
    "pipdepgraph.entrypoints.correlate_candidates_for_requirements_rmq"
)


async def main():
    logger.info("Initializing DB pool")
    async with (common.initialize_async_connection_pool() as db_pool,):
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

        logger.info("Starting RabbitMQ consumer thread")
        requirements_queue: queue.Queue[models.Requirement] = queue.Queue()
        ack_queue: queue.Queue[bool] = queue.Queue()

        consume_from_rabbitmq_thread = rabbitmq.start_rabbitmq_consume_thread(
            rabbitmq_queue_name=constants.RABBITMQ_REQS_CAND_CORR_QNAME,
            model_factory=models.Requirement.from_dict,
            model_queue=requirements_queue,
            ack_queue=ack_queue,
            prefetch_count=constants.RABBITMQ_REQS_CAND_CORR_SUB_PREFETCH,
        )

        logger.info("Running.")
        while True:
            requirement = None

            try:
                requirement = requirements_queue.get(timeout=5.0)
                logger.debug("Correlating candidates for requirement: %s", requirement)
                await ccs.process_requirement_record(requirement)
                ack_queue.put(True)

            except queue.Empty as ex:
                if not consume_from_rabbitmq_thread.is_alive():
                    logger.error("RabbitMQ consumer thread has died.")
                    return

            except Exception as ex:
                logger.error(
                    f"Error while handling Requirement message: {requirement}",
                    exc_info=ex,
                )
                ack_queue.put(False)
                raise


if __name__ == "__main__":
    common.initialize_logger()
    asyncio.run(main())
