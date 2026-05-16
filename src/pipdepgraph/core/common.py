import logging
import sys

import requests
from psycopg_pool import ConnectionPool

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


def initialize_connection_pool(
    host=constants.POSTGRES_HOST,
    port=constants.POSTGRES_PORT,
    db=constants.POSTGRES_DB,
    username=constants.POSTGRES_USERNAME,
    password=constants.POSTGRES_PASSWORD,
    max_pool_size=10,
) -> ConnectionPool:

    connection_string = f"""
    dbname={db}
    user={username}
    password={password}
    host={host}
    port={port}
    """

    return ConnectionPool(
        conninfo=connection_string,
        min_size=1,
        max_size=max_pool_size,
    )


def initialize_client_session() -> requests.Session:
    session = requests.Session()
    session.headers.update({"User-Agent": "schaffer.austin.t@gmail.com"})
    return session
