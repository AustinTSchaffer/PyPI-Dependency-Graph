import asyncio
import sys
import logging

import aiohttp
from psycopg_pool import AsyncConnectionPool

from pipdepgraph import constants, pypi_api
from pipdepgraph.repositories import (
    known_package_name_repository,
    known_versions_repository,
    version_distributions_repository,
    direct_dependencies_repository,
)
from pipdepgraph.services import (
    known_packages_processing_service,
    version_distribution_processing_service,
)

logger = logging.getLogger(__name__)


def get_connection_pool() -> AsyncConnectionPool:
    return AsyncConnectionPool(conninfo=constants.POSTGRES_CONNECTION_STRING)


async def main():
    logger.info("Starting.")
    async with get_connection_pool() as db_pool, aiohttp.ClientSession(
        headers={"User-Agent": "schaffer.austin.t@gmail.com"}
    ) as session:

        logger.info("Initializing classes.")

        kpnr = known_package_name_repository.KnownPackageNameRepository(db_pool)
        kvr = known_versions_repository.KnownVersionRepository(db_pool)
        vdr = version_distributions_repository.VersionDistributionRepository(db_pool)
        ddr = direct_dependencies_repository.DirectDependencyRepository(db_pool)

        pypi = pypi_api.PypiApi(session)

        kpps = known_packages_processing_service.KnownPackageProcessingService(
            kpnr=kpnr, kvr=kvr, vdr=vdr, pypi=pypi
        )
        vdps = version_distribution_processing_service.VersionDistributionProcessingService(
            vdr=vdr, ddr=ddr, pypi=pypi
        )

        await kpps.propagate_discovered_package_names()
        await kpps.run_from_database()
        await vdps.run_from_database()


if __name__ == "__main__":
    root = logging.getLogger()
    root.setLevel(logging.INFO)

    handler = logging.StreamHandler(sys.stdout)
    handler.setLevel(logging.DEBUG)
    formatter = logging.Formatter(
        "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )
    handler.setFormatter(formatter)
    root.addHandler(handler)

    asyncio.run(main())
