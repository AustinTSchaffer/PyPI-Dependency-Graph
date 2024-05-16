import asyncio
import asyncio.proactor_events
import functools
import logging
import sys
import threading

import aiohttp
import pika
import pika.adapters.asyncio_connection
import pika.adapters.blocking_connection
import pika.credentials
from psycopg_pool import AsyncConnectionPool

from pipdepgraph import constants


def initialize_async_connection_pool() -> AsyncConnectionPool:
    return AsyncConnectionPool(conninfo=constants.POSTGRES_CONNECTION_STRING, max_size=10)


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

def declare_rabbitmq_infrastructure(channel: pika.adapters.blocking_connection.BlockingChannel):
    channel.exchange_declare(
        constants.RABBITMQ_EXCHANGE, exchange_type="topic", durable=True
    )
    channel.queue_declare(constants.RABBITMQ_KPN_QNAME, durable=True)
    channel.queue_bind(
        exchange=constants.RABBITMQ_EXCHANGE,
        queue=constants.RABBITMQ_KPN_QNAME,
        routing_key=constants.RABBITMQ_KPN_RK,
    )

    channel.queue_declare(constants.RABBITMQ_VD_QNAME, durable=True)
    channel.queue_bind(
        exchange=constants.RABBITMQ_EXCHANGE,
        queue=constants.RABBITMQ_VD_QNAME,
        routing_key=constants.RABBITMQ_VD_RK,
    )
