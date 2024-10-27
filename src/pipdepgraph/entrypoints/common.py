import logging
import sys

import aiohttp
import pika
import pika.adapters.asyncio_connection
import pika.adapters.blocking_connection
import pika.credentials
from psycopg_pool import AsyncConnectionPool

from pipdepgraph import constants


def initialize_async_connection_pool(
    host=constants.POSTGRES_HOST,
    port=constants.POSTGRES_PORT,
    db=constants.POSTGRES_DB,
    username=constants.POSTGRES_USERNAME,
    password=constants.POSTGRES_PASSWORD,
    max_pool_size=10,
) -> AsyncConnectionPool:

    connection_string = f"""
    dbname={db}
    user={username}
    password={password}
    host={host}
    port={port}
    """

    return AsyncConnectionPool(
        conninfo=connection_string, max_size=max_pool_size,
    )


def initialize_client_session() -> aiohttp.ClientSession:
    return aiohttp.ClientSession(headers={"User-Agent": "schaffer.austin.t@gmail.com"})


def initialize_logger() -> None:
    root = logging.getLogger()
    root.setLevel(logging.INFO)

    handler = logging.StreamHandler(sys.stdout)
    handler.setLevel(logging.DEBUG)
    formatter = logging.Formatter(
        "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )
    handler.setFormatter(formatter)
    root.addHandler(handler)


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

    channel.queue_declare(constants.RABBITMQ_REQS_QNAME, durable=True)
    channel.queue_bind(
        exchange=constants.RABBITMQ_EXCHANGE,
        queue=constants.RABBITMQ_REQS_QNAME,
        routing_key=constants.RABBITMQ_REQS_RK,
    )
