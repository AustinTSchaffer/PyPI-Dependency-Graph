import logging
import asyncio
import queue

import pika.adapters.blocking_connection

from pipdepgraph import constants, models
from pipdepgraph.services import rabbitmq_publish_service
from pipdepgraph.core import rabbitmq
from pipdepgraph.core import common

logger = logging.getLogger("pipdepgraph.entrypoints.cdc.requirements_subscriber")


async def main():
    logger.info("Initializing RabbitMQ Connection")
    with (
        rabbitmq.initialize_rabbitmq_connection() as rabbitmq_connection,
        rabbitmq_connection.channel() as channel,
    ):
        channel: pika.adapters.blocking_connection.BlockingChannel
        rabbitmq.declare_rabbitmq_infrastructure(channel)

        logger.info("Starting RabbitMQ consumer thread")
        event_queue: queue.Queue[models.EventLogEntry] = queue.Queue()
        ack_queue: queue.Queue[bool] = queue.Queue()

        consume_from_rabbitmq_thread = rabbitmq.start_rabbitmq_consume_thread(
            rabbitmq_queue_name=constants.RABBITMQ_CDC_REQS_QNAME,
            model_factory=models.EventLogEntry.from_dict,
            model_queue=event_queue,
            ack_queue=ack_queue,
            prefetch_count=constants.RABBITMQ_CDC_REQS_SUB_PREFETCH,
        )

        rmq_pub = rabbitmq_publish_service.RabbitMqPublishService(None)

        logger.info("Running.")
        while True:
            event = None

            try:
                event = event_queue.get(timeout=5.0)
                if event.operation in ('INSERT', 'UPDATE') and event.after is not None:
                    rmq_pub.publish_requirement_dict_for_candidate_correlation(
                        event.after,
                        channel=channel,
                    )
                ack_queue.put(True)

            except queue.Empty as ex:
                if not consume_from_rabbitmq_thread.is_alive():
                    logger.error("RabbitMQ consumer thread has died.")
                    return

            except Exception as ex:
                logger.error(
                    f"Error while handling CDC Requirement message: {event}",
                    exc_info=ex,
                )
                ack_queue.put(False)
                raise


if __name__ == "__main__":
    common.initialize_logger()
    asyncio.run(main())
