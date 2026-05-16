import logging

from pipdepgraph import constants, models
from pipdepgraph.core import common, rabbitmq

from pipdepgraph.repositories import (
    requirements_repository,
)

logger = logging.getLogger("pipdepgraph.entrypoints.rmq_sub.requirements_reprocessor")


def main():
    logger.info("Initializing DB pool")
    with (
        common.initialize_connection_pool() as db_pool,
        db_pool.connection() as conn,
        conn.cursor() as edit_cursor,
    ):
        logger.info("Initializing repositories")
        rr = requirements_repository.RequirementsRepository(db_pool)

        def process(requirement: models.Requirement) -> None:
            if requirement.extras is None:
                requirement.extras = ""

            requirement.dependency_extras_arr = []
            if requirement.dependency_extras:
                requirement.dependency_extras_arr = (
                    requirement.dependency_extras.split(",")
                )

            logger.info("Updating requirement: %s", requirement)
            rr.update_requirement(requirement, cursor=edit_cursor)
            edit_cursor.execute("commit;")

        logger.info("Running.")
        rabbitmq.consume_from_rabbitmq(
            rabbitmq_queue_name=constants.RABBITMQ_REPROCESS_REQS_QNAME,
            prefetch_count=constants.RABBITMQ_REPROCESS_REQS_SUB_PREFETCH,
            model_factory=models.Requirement.from_dict,
            on_message=process,
        )


if __name__ == "__main__":
    common.initialize_logger()
    main()
