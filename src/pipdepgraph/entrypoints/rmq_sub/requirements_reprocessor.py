import logging
import asyncio
import queue

from pipdepgraph import constants, models
from pipdepgraph.core import common, rabbitmq

from pipdepgraph.repositories import (
    requirements_repository,
)

logger = logging.getLogger("pipdepgraph.entrypoints.rmq_sub.requirements_reprocessor")


async def main():
    logger.info("Initializing DB pool")
    async with (
        common.initialize_async_connection_pool() as db_pool,
        db_pool.connection() as conn,
        conn.cursor() as edit_cursor,
    ):
        logger.info("Initializing repositories")
        rr = requirements_repository.RequirementsRepository(db_pool)

        logger.info("Starting RabbitMQ consumer thread")

        requirements_queue: queue.Queue[models.Requirement] = queue.Queue()
        ack_queue: queue.Queue[bool] = queue.Queue()

        consume_from_rabbitmq_thread = rabbitmq.start_rabbitmq_consume_thread(
            rabbitmq_queue_name=constants.RABBITMQ_REPROCESS_REQS_QNAME,
            prefetch_count=constants.RABBITMQ_REPROCESS_REQS_SUB_PREFETCH,
            model_factory=models.Requirement.from_dict,
            model_queue=requirements_queue,
            ack_queue=ack_queue,
        )

        logger.info("Running.")
        while True:
            requirement = None

            try:
                requirement = requirements_queue.get(timeout=5.0)

                if requirement.extras is None:
                    requirement.extras = ""

                requirement.dependency_extras_arr = []
                if requirement.dependency_extras:
                    requirement.dependency_extras_arr = (
                        requirement.dependency_extras.split(",")
                    )

                logger.info(f"Updating requirement: {requirement}")
                await rr.update_requirement(requirement, cursor=edit_cursor)
                await edit_cursor.execute("commit;")

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
