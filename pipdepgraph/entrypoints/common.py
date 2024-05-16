import asyncio
import asyncio.proactor_events
import functools
import logging
import sys
import threading

import aiohttp
import pika
import pika.adapters.asyncio_connection
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

_loop = asyncio.new_event_loop()

_thr = threading.Thread(target=_loop.run_forever, name="Async Runner",
                        daemon=True)

def synchronous(f):
    """
    Decorator for running `f`, an asynchronous method, within a synchronous
    function call, using a separate private daemon thread.
    """

    @functools.wraps(f)
    def wrapper(*args, **kwargs):
        if not _thr.is_alive():
            _thr.start()
        future = asyncio.run_coroutine_threadsafe(f(*args, **kwargs), _loop)
        return future.result()

    return wrapper
