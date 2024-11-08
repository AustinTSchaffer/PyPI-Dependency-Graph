import logging
import asyncio
import json
import queue
import threading
import uuid

import pika
import pika.adapters.asyncio_connection
import pika.adapters.blocking_connection
import pika.channel
import pika.delivery_mode
import pika.spec

from pipdepgraph import constants, models
from pipdepgraph.entrypoints import common

from pipdepgraph.services import candidate_correlation_service

from pipdepgraph.repositories import (
    versions_repository,
    requirements_repository,
    candidates_repository,
)

logger = logging.getLogger("pipdepgraph.entrypoints.correlate_candidates_for_requirements_rmq")


async def main():
    logger.info("Initializing DB pool")
    async with (
        common.initialize_async_connection_pool() as db_pool,
    ):
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
        requirements_queue: queue.Queue[models.Requirement] = (
            queue.Queue()
        )
        ack_queue: queue.Queue[bool] = queue.Queue()
        consume_from_rabbitmq_thread = threading.Thread(
            target=consume_from_rabbitmq_target,
            args=[requirements_queue, ack_queue],
        )

        consume_from_rabbitmq_thread.start()

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


def consume_from_rabbitmq_target(
    requirements_queue: queue.Queue[models.Requirement],
    ack_queue: queue.Queue[bool],
):
    """
    Consumes Requirement records from RabbitMQ, placing it into the `out_queue`.
    Expects a response on the `in_queue` containing a single flag indicating whether
    the message should be acked or nacked.
    """

    with (
        common.initialize_rabbitmq_connection() as connection,
        connection.channel() as channel,
    ):
        channel: pika.adapters.blocking_connection.BlockingChannel
        common.declare_rabbitmq_infrastructure(channel)
        channel.basic_qos(prefetch_count=constants.RABBITMQ_REPROCESS_REQS_SUB_PREFETCH)

        def _requirement_consumer(
            ch: pika.channel.Channel,
            basic_deliver: pika.spec.Basic.Deliver,
            properties: pika.spec.BasicProperties,
            body: bytes,
        ):
            try:
                requirement_json = json.loads(body)
                requirement = models.Requirement.from_dict(requirement_json)
                requirements_queue.put(requirement)

                ack = ack_queue.get()

                if ack:
                    ch.basic_ack(basic_deliver.delivery_tag)
                else:
                    ch.basic_nack(basic_deliver.delivery_tag)
                    ch.close()

            except Exception as ex:
                logger.error(
                    f"Error while handling Requirement message: {basic_deliver}",
                    exc_info=ex,
                )
                ch.basic_nack(basic_deliver.delivery_tag)
                ch.close()
                raise

        consumer_tag = None
        if constants.RABBITMQ_CTAG_PREFIX:
            consumer_tag = f"{constants.RABBITMQ_CTAG_PREFIX}{uuid.uuid4()}"
            logger.info("Starting RabbitMQ consumer with ctag: %s", consumer_tag)

        channel.basic_consume(
            queue=constants.RABBITMQ_REQS_CAND_CORR_QNAME,
            on_message_callback=_requirement_consumer,
            consumer_tag=consumer_tag,
            auto_ack=False,
        )

        channel.start_consuming()


if __name__ == "__main__":
    common.initialize_logger()
    asyncio.run(main())
