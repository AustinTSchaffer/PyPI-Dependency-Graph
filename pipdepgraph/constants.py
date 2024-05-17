import os

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

UPL_LOAD_PACKAGE_NAMES = bool(os.getenv("UPL_LOAD_PACKAGE_NAMES", "true").strip().lower() == "true")
UPL_LOAD_VERSION_DISTRIBUTIONS = bool(os.getenv("UPL_LOAD_VERSION_DISTRIBUTIONS", "true").strip().lower() == "true")
