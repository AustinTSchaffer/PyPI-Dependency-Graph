import logging
import asyncio

from pipdepgraph import constants, pypi_api
from pipdepgraph.entrypoints import common

from pipdepgraph.services import (
    known_packages_processing_service,
    version_distribution_processing_service,
)

from pipdepgraph.repositories import (
    direct_dependency_repository,
    known_package_name_repository,
    known_version_repository,
    version_distribution_repository,
)

logger = logging.getLogger(__name__)


async def main():
    async with (
        common.initialize_async_connection_pool() as db_pool,
        common.initialize_client_session() as session,
    ):
        kpnr = known_package_name_repository.KnownPackageNameRepository(db_pool)
        kvr = known_version_repository.KnownVersionRepository(db_pool)
        vdr = version_distribution_repository.VersionDistributionRepository(db_pool)
        ddr = direct_dependency_repository.DirectDependencyRepository(db_pool)

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
    common.initialize_logger()
    asyncio.run(main())
