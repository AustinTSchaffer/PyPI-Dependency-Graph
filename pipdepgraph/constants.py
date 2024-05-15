import os
import re

POSTGRES_HOST = os.getenv("POSTGRES_HOST", "localhost")
POSTGRES_PORT = int(os.getenv("POSTGRES_PORT", "5432"))
POSTGRES_DB = os.getenv("POSTGRES_DB", "defaultdb")
POSTGRES_USERNAME = os.getenv("POSTGRES_USERNAME", "pypi_scraper")
POSTGRES_PASSWORD = os.getenv("POSTGRES_PASSWORD", "password")

POSTGRES_CONNECTION_STRING = f"""
dbname={POSTGRES_DB}
user={POSTGRES_USERNAME}
password={POSTGRES_PASSWORD}
host={POSTGRES_HOST}
port={POSTGRES_PORT}
"""

POSTGRES_MAX_QUERY_PARAMS = 65535
