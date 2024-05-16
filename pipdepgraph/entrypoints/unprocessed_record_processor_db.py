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

logger = logging.getLogger('pipdepgraph.entrypoints.unprocessed_record_processor')


async def main():
    logger.info("Initializing DB pool")
    async with (
        common.initialize_async_connection_pool() as db_pool,
        common.initialize_client_session() as session,
    ):
        logger.info("Initializing repositories")
        kpnr = known_package_name_repository.KnownPackageNameRepository(db_pool)
        kvr = known_version_repository.KnownVersionRepository(db_pool)
        vdr = version_distribution_repository.VersionDistributionRepository(db_pool)
        ddr = direct_dependency_repository.DirectDependencyRepository(db_pool)

        logger.info("Initializing pypi_api.PypiApi")
        pypi = pypi_api.PypiApi(session)

        logger.info("Initializing known_packages_processing_service.KnownPackageProcessingService")
        kpps = known_packages_processing_service.KnownPackageProcessingService(
            kpnr=kpnr, kvr=kvr, vdr=vdr, pypi=pypi
        )

        logger.info("Initializing version_distribution_processing_service.VersionDistributionProcessingService")
        vdps = version_distribution_processing_service.VersionDistributionProcessingService(
            vdr=vdr, ddr=ddr, pypi=pypi
        )

        logger.info("Running.")

        await kpps.propagate_discovered_package_names()
        await kpps.run_from_database()
        await vdps.run_from_database()


if __name__ == "__main__":
    common.initialize_logger()
    asyncio.run(main())
