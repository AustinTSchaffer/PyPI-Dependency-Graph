import os
import re

POSTGRES_HOST = os.getenv("POSTGRES_HOST", "localhost")
POSTGRES_PORT = int(os.getenv("POSTGRES_PORT", "5432"))
POSTGRES_DB = os.getenv("POSTGRES_DB", "defaultdb")
POSTGRES_USERNAME = os.getenv("POSTGRES_USERNAME", "pypi_scraper")
POSTGRES_PASSWORD = os.getenv("POSTGRES_PASSWORD", "password")

POSTGRES_MAX_QUERY_PARAMS = 65535

RABBITMQ_HOST = os.getenv("RABBITMQ_HOST", "localhost")
RABBITMQ_PORT = os.getenv("RABBITMQ_PORT", "5672")
RABBITMQ_USERNAME = os.getenv("RABBITMQ_USERNAME", "pypi_scraper")
RABBITMQ_PASSWORD = os.getenv("RABBITMQ_PASSWORD", "password")
RABBITMQ_VHOST = os.getenv("RABBITMQ_VHOST", "pypi_scraper")
RABBITMQ_EXCHANGE = os.getenv("RABBITMQ_EXCHANGE", "pypi_scraper")

RABBITMQ_KPN_QNAME = "known_package_names"
RABBITMQ_KPN_RK_PREFIX = "known_package_name."
RABBITMQ_KPN_RK = f"{RABBITMQ_KPN_RK_PREFIX}#"
RABBITMQ_KPN_SUB_PREFETCH = int(os.getenv("RABBITMQ_KPN_SUB_PREFETCH", 50))

RABBITMQ_VD_QNAME = "version_distributions"
RABBITMQ_VD_RK_PREFIX = "version_distribution."
RABBITMQ_VD_RK = f"{RABBITMQ_VD_RK_PREFIX}#"
RABBITMQ_VD_SUB_PREFETCH = int(os.getenv("RABBITMQ_VD_SUB_PREFETCH", 100))

RABBITMQ_CTAG_PREFIX = os.getenv("RABBITMQ_CTAG_PREFIX", None)

VDP_DISCOVER_PACKAGE_NAMES = bool(
    os.getenv("VDP_DISCOVER_PACKAGE_NAMES", "false").strip().lower() == "true"
)

UPL_LOAD_PACKAGE_NAMES = bool(
    os.getenv("UPL_LOAD_PACKAGE_NAMES", "true").strip().lower() == "true"
)
UPL_LOAD_VERSION_DISTRIBUTIONS = bool(
    os.getenv("UPL_LOAD_VERSION_DISTRIBUTIONS", "true").strip().lower() == "true"
)

PACKAGE_RELEASE_TERM_MAX_SIZE = 9_223_372_036_854_775_807  # Postgres bigint max size
"""
This is based on Postgres's max value for bigint. There are a few package version
terms in the quintillions, and around 50 package versions that have a version term
greater than this. Those 50 versions do not warrant using numeric[] as the data-
type for package_release.
"""

POPULAR_PACKAGE_LOADER_COUNT_INSERTED = (
    os.getenv("TOP_8000_LOADER_COUNT_INSERTED", "true").strip().lower() == "true"
)
POPULAR_PACKAGE_LOADER_PREFIX_REGEX = re.compile(
    os.getenv("TOP_8000_LOADER_COUNT_INSERTED", "^")
)
