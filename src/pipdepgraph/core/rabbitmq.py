import json
import logging
import uuid
from typing import Callable, Any

import pika
import pika.spec
import pika.channel
import pika.adapters.blocking_connection
import pika.credentials

from pipdepgraph import constants

logger = logging.getLogger(__name__)


def initialize_rabbitmq_connection() -> pika.BlockingConnection:
    params = {
        k: v
        for k, v in dict(
            host=constants.RABBITMQ_HOST,
            port=constants.RABBITMQ_PORT,
            virtual_host=constants.RABBITMQ_VHOST,
            credentials=pika.credentials.PlainCredentials(
                username=constants.RABBITMQ_USERNAME,
                password=constants.RABBITMQ_PASSWORD,
            ),
        ).items()
        if v is not None
    }

    rabbitmq_connection = pika.BlockingConnection(pika.ConnectionParameters(**params))
    return rabbitmq_connection


def consume_from_rabbitmq[TModel](
    *,
    rabbitmq_queue_name: str,
    model_factory: Callable[[Any], TModel],
    on_message: Callable[[TModel], None],
    prefetch_count: int,
):
    with (
        initialize_rabbitmq_connection() as connection,
        connection.channel() as channel,
    ):
        channel: pika.adapters.blocking_connection.BlockingChannel
        declare_rabbitmq_infrastructure(channel)
        channel.basic_qos(prefetch_count=prefetch_count)

        def _callback(
            ch: pika.channel.Channel,
            basic_deliver: pika.spec.Basic.Deliver,
            properties: pika.spec.BasicProperties,
            body: bytes,
        ):
            try:
                try:
                    payload = json.loads(body)
                except json.JSONDecodeError:
                    payload = body.decode()

                model = model_factory(payload)
                on_message(model)
                ch.basic_ack(basic_deliver.delivery_tag)
            except Exception as ex:
                logger.error(
                    "Error while handling message: %s",
                    basic_deliver,
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
            queue=rabbitmq_queue_name,
            on_message_callback=_callback,
            consumer_tag=consumer_tag,
            auto_ack=False,
        )

        channel.start_consuming()


def declare_rabbitmq_infrastructure(
    channel: pika.adapters.blocking_connection.BlockingChannel,
):
    channel.exchange_declare(
        constants.RABBITMQ_EXCHANGE, exchange_type="topic", durable=True
    )
    channel.queue_declare(constants.RABBITMQ_NAMES_QNAME, durable=True)
    channel.queue_bind(
        exchange=constants.RABBITMQ_EXCHANGE,
        queue=constants.RABBITMQ_NAMES_QNAME,
        routing_key=constants.RABBITMQ_NAMES_RK,
    )

    channel.queue_declare(constants.RABBITMQ_DISTS_QNAME, durable=True)
    channel.queue_bind(
        exchange=constants.RABBITMQ_EXCHANGE,
        queue=constants.RABBITMQ_DISTS_QNAME,
        routing_key=constants.RABBITMQ_DISTS_RK,
    )

    channel.queue_declare(constants.RABBITMQ_REPROCESS_REQS_QNAME, durable=True)
    channel.queue_bind(
        exchange=constants.RABBITMQ_EXCHANGE,
        queue=constants.RABBITMQ_REPROCESS_REQS_QNAME,
        routing_key=constants.RABBITMQ_REPROCESS_REQS_RK,
    )

    channel.queue_declare(constants.RABBITMQ_REQS_CAND_CORR_QNAME, durable=True)
    channel.queue_bind(
        exchange=constants.RABBITMQ_EXCHANGE,
        queue=constants.RABBITMQ_REQS_CAND_CORR_QNAME,
        routing_key=constants.RABBITMQ_REQS_CAND_CORR_RK,
    )

    channel.queue_declare(constants.RABBITMQ_CDC_VERSIONS_QNAME, durable=True)

    channel.queue_bind(
        exchange=constants.RABBITMQ_EXCHANGE,
        queue=constants.RABBITMQ_CDC_VERSIONS_QNAME,
        routing_key=constants.RABBITMQ_CDC_VERSIONS_RK_PREFIX,
    )

    channel.queue_bind(
        exchange=constants.RABBITMQ_EXCHANGE,
        queue=constants.RABBITMQ_CDC_VERSIONS_QNAME,
        routing_key=f"{constants.RABBITMQ_CDC_VERSIONS_RK_PREFIX}.#",
    )

    channel.queue_declare(constants.RABBITMQ_CDC_REQS_QNAME, durable=True)

    channel.queue_bind(
        exchange=constants.RABBITMQ_EXCHANGE,
        queue=constants.RABBITMQ_CDC_REQS_QNAME,
        routing_key=constants.RABBITMQ_CDC_REQS_RK_PREFIX,
    )

    channel.queue_bind(
        exchange=constants.RABBITMQ_EXCHANGE,
        queue=constants.RABBITMQ_CDC_REQS_QNAME,
        routing_key=f"{constants.RABBITMQ_CDC_REQS_RK_PREFIX}.#",
    )
