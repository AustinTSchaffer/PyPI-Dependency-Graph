import queue
import json
import logging
import uuid
from typing import Callable, Any
import threading

import pika
import pika.spec
import pika.channel
import pika.adapters.asyncio_connection
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


def start_rabbitmq_consume_thread[
    TModel
](
    *,
    rabbitmq_queue_name: str,
    model_factory: Callable[[Any], TModel],
    model_queue: queue.Queue[TModel],
    ack_queue: queue.Queue[bool],
    prefetch_count: int,
) -> threading.Thread:
    """
    Starts a thread to run the `consume_from_rabbitmq_target` method, with the given
    arguments. Returns the thread.

    This exists so that a RabbitMQ consume loop thread can be started from a thread
    that's running an async context.
    """

    consume_from_rabbitmq_thread = threading.Thread(
        target=consume_from_rabbitmq_target,
        kwargs=dict(
            rabbitmq_queue_name=rabbitmq_queue_name,
            model_factory=model_factory,
            model_queue=model_queue,
            ack_queue=ack_queue,
            prefetch_count=prefetch_count,
        ),
    )

    consume_from_rabbitmq_thread.start()
    return consume_from_rabbitmq_thread


def consume_from_rabbitmq_target[
    TModel
](
    *,
    rabbitmq_queue_name: str,
    model_factory: Callable[[Any], TModel],
    model_queue: queue.Queue[TModel],
    ack_queue: queue.Queue[bool],
    prefetch_count: int,
):
    """
    Consumes records from RabbitMQ, converting them to the specified type, and placing
    them into the `model_queue`. Expects a response on the `ack_queue` containing a
    single boolean flag indicating whether the message should be acked or nacked.

    This exists so that a RabbitMQ consume loop thread can be started from a thread
    that's running an async context.
    """

    with (
        initialize_rabbitmq_connection() as connection,
        connection.channel() as channel,
    ):
        channel: pika.adapters.blocking_connection.BlockingChannel
        declare_rabbitmq_infrastructure(channel)
        channel.basic_qos(prefetch_count=prefetch_count)

        def _model_consumer(
            ch: pika.channel.Channel,
            basic_deliver: pika.spec.Basic.Deliver,
            properties: pika.spec.BasicProperties,
            body: bytes,
        ):
            try:
                payload = json.loads(body)
                model = model_factory(payload)
                model_queue.put(model)

                ack = ack_queue.get()

                if ack:
                    ch.basic_ack(basic_deliver.delivery_tag)
                else:
                    ch.basic_nack(basic_deliver.delivery_tag)
                    ch.close()

            except Exception as ex:
                logger.error(
                    f"Error while handling message: {basic_deliver}",
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
            on_message_callback=_model_consumer,
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
