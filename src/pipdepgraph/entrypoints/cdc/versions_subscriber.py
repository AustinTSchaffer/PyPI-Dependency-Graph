import logging

from pipdepgraph import constants, models
from pipdepgraph.services import rabbitmq_publish_service
from pipdepgraph.core import rabbitmq
from pipdepgraph.core import common

logger = logging.getLogger("pipdepgraph.entrypoints.cdc.requirements_subscriber")


def main():
    with (
        rabbitmq.initialize_rabbitmq_connection() as connection,
        connection.channel() as channel,
    ):
        rmq_pub = rabbitmq_publish_service.RabbitMqPublishService(channel)

        def process(event: models.EventLogEntry) -> None:
            if event.operation in ('INSERT', 'UPDATE') and event.after is not None:
                rmq_pub.publish_requirement_dict_for_candidate_correlation(event.after)

        logger.info("Running.")
        rabbitmq.consume_from_rabbitmq(
            rabbitmq_queue_name=constants.RABBITMQ_CDC_REQS_QNAME,
            prefetch_count=constants.RABBITMQ_CDC_REQS_SUB_PREFETCH,
            model_factory=models.EventLogEntry.from_dict,
            on_message=process,
        )


if __name__ == "__main__":
    common.initialize_logger()
    main()
