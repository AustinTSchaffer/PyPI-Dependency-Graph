import logging

import packaging.utils
from psycopg.rows import dict_row

from psycopg_pool import AsyncConnectionPool
from pipdepgraph import models, pypi_api, constants
from pipdepgraph.repositories import (
    direct_dependency_repository,
    known_package_name_repository,
    version_distribution_repository,
)

from pipdepgraph.services import rabbitmq_publish_service

logger = logging.getLogger(__name__)


class VersionDistributionProcessingService:
    def __init__(
        self,
        *,
        kpnr: known_package_name_repository.KnownPackageNameRepository,
        vdr: version_distribution_repository.VersionDistributionRepository,
        ddr: direct_dependency_repository.DirectDependencyRepository,
        pypi: pypi_api.PypiApi,
        db_pool: AsyncConnectionPool,
        rmq_pub: rabbitmq_publish_service.RabbitMqPublishService = None,
    ):
        self.known_package_names_repo = kpnr
        self.version_distributions_repo = vdr
        self.direct_dependencies_repo = ddr
        self.pypi = pypi

        self.db_pool = db_pool
        self.rabbitmq_publish_service = rmq_pub

    async def run_from_database(self):
        """
        Runs through all unprocessed version distributions from the database and processes each one.
        """
        async for (
            version_distribution
        ) in self.version_distributions_repo.iter_version_distributions(
            processed=False
        ):
            await self.process_version_distribution(version_distribution)

    async def process_version_distribution(
        self,
        distribution: models.VersionDistribution,
        ignore_processed_flag: bool = False,
    ):
        """
        Processes a single version distribution.

        - Fetches the version distribution's `.metadata` file from the PyPI API.
        - Parses the metadata file, extracting the package's direct dependencies.
        - ...

        `ignore_processed_flag` can be used to force this method to reprocess a distribution that
        has already been processed.
        """

        if not ignore_processed_flag and distribution.processed:
            logger.debug(f"{distribution.version_distribution_id} - Already processed.")
            return

        logger.info(
            f"{distribution.version_distribution_id} - Getting direct dependencies."
        )

        metadata, metadata_file_size = await self.pypi.get_distribution_metadata(
            distribution
        )

        if not metadata:
            logger.debug(
                f"{distribution.version_distribution_id} - No metadata information found."
            )
            distribution.metadata_file_size = 0
            distribution.processed = True
            await self.version_distributions_repo.update_version_distributions(
                [distribution]
            )
            return

        async with self.db_pool.connection() as conn, conn.cursor(
            row_factory=dict_row
        ) as cursor:
            try:
                direct_dependencies: list[models.DirectDependency] = []
                if metadata.requires_dist:
                    for dependency in metadata.requires_dist:
                        direct_dependencies.append(
                            models.DirectDependency(
                                version_distribution_id=distribution.version_distribution_id,
                                extras=(
                                    str(dependency.marker)
                                    if dependency.marker
                                    else None
                                ),
                                dependency_extras=",".join(dependency.extras),
                                dependency_name=packaging.utils.canonicalize_name(
                                    dependency.name, validate=True
                                ),
                                version_constraint=str(dependency.specifier),
                            )
                        )

                logger.info(
                    f"{distribution.version_distribution_id} - Found {len(direct_dependencies)} direct dependencies."
                )

                await self.direct_dependencies_repo.insert_direct_dependencies(
                    direct_dependencies,
                    cursor=cursor,
                )

                if constants.VDP_DISCOVER_PACKAGE_NAMES:
                    distinct_package_names = list(
                        {dd.dependency_name for dd in direct_dependencies}
                    )

                    logger.debug(
                        f"{distribution.version_distribution_id} - Propagating {len(distinct_package_names)} back to Postgres."
                    )

                    result = await self.known_package_names_repo.insert_known_package_names(
                        distinct_package_names,
                        return_inserted=(self.rabbitmq_publish_service is not None),
                        cursor=cursor,
                    )

                    if self.rabbitmq_publish_service is not None and result:
                        logger.debug(
                            f"{distribution.version_distribution_id} - Propagating {len(result)} package names to RabbitMQ."
                        )
                        self.rabbitmq_publish_service.publish_known_package_names(result)

                logger.debug(
                    f"{distribution.version_distribution_id} - Marking processed."
                )
                distribution.metadata_file_size = metadata_file_size
                distribution.processed = True
                await self.version_distributions_repo.update_version_distributions(
                    [distribution], cursor=cursor
                )

                await cursor.execute("commit;")
            except Exception as ex:
                logger.error(
                    f"{distribution.version_distribution_id} - Error while retrieving/persisting direct dependency info.",
                    exc_info=ex,
                )
