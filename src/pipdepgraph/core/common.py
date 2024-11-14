import logging
import sys

import aiohttp
from psycopg_pool import AsyncConnectionPool

from pipdepgraph import constants


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
        conninfo=connection_string,
        min_size=1,
        max_size=max_pool_size,
    )


def initialize_client_session() -> aiohttp.ClientSession:
    return aiohttp.ClientSession(headers={"User-Agent": "schaffer.austin.t@gmail.com"})
