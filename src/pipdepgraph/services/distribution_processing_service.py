import logging

import packaging.utils
from psycopg.rows import dict_row

from psycopg_pool import AsyncConnectionPool
from pipdepgraph import models, pypi_api, constants
from pipdepgraph.repositories import (
    distributions_repository,
    package_names_repository,
    requirements_repository,
)

from pipdepgraph.services import rabbitmq_publish_service

logger = logging.getLogger(__name__)


class DistributionProcessingService:
    def __init__(
        self,
        *,
        pnr: package_names_repository.PackageNamesRepository,
        dr: distributions_repository.DistributionsRepository,
        rr: requirements_repository.RequirementsRepository,
        pypi: pypi_api.PypiApi,
        db_pool: AsyncConnectionPool,
        rmq_pub: rabbitmq_publish_service.RabbitMqPublishService = None,
    ):
        self.package_names_repo = pnr
        self.distributions_repo = dr
        self.requirements_repo = rr
        self.pypi = pypi

        self.db_pool = db_pool
        self.rabbitmq_publish_service = rmq_pub

    async def run_from_database(self):
        """
        Runs through all unprocessed distributions from the database and processes each one.
        """
        async for (
            distribution
        ) in self.distributions_repo.iter_distributions(
            processed=False
        ):
            await self.process_distribution(distribution)

    async def process_distribution(
        self,
        distribution: models.Distribution,
        ignore_processed_flag: bool = False,
    ):
        """
        Processes a single distribution.

        - Fetches the distribution's `.metadata` file from the PyPI API.
        - Parses the metadata file, extracting the package's requirements.
        - ...

        `ignore_processed_flag` can be used to force this method to reprocess a distribution that
        has already been processed.
        """

        if not ignore_processed_flag and distribution.processed:
            logger.debug(f"{distribution.distribution_id} - Already processed.")
            return

        logger.info(
            f"{distribution.distribution_id} - Getting requirements."
        )

        metadata, metadata_file_size = await self.pypi.get_distribution_metadata(
            distribution
        )

        if not metadata:
            logger.debug(
                f"{distribution.distribution_id} - No metadata information found."
            )
            distribution.metadata_file_size = 0
            distribution.processed = True
            await self.distributions_repo.update_distributions(
                [distribution]
            )
            return

        async with self.db_pool.connection() as conn, conn.cursor(
            row_factory=dict_row
        ) as cursor:
            try:
                requirements: list[models.Requirement] = []
                if metadata.requires_dist:
                    for dependency in metadata.requires_dist:
                        requirements.append(
                            models.Requirement(
                                distribution_id=distribution.distribution_id,
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
                    f"{distribution.distribution_id} - Found {len(requirements)} requirements."
                )

                await self.requirements_repo.insert_requirements(
                    requirements,
                    cursor=cursor,
                )

                if constants.DIST_PROCESSOR_DISCOVER_PACKAGE_NAMES:
                    distinct_package_names = list(
                        {dd.dependency_name for dd in requirements}
                    )

                    logger.debug(
                        f"{distribution.distribution_id} - Propagating {len(distinct_package_names)} back to Postgres."
                    )

                    result = await self.package_names_repo.insert_package_names(
                        distinct_package_names,
                        return_inserted=(self.rabbitmq_publish_service is not None),
                        cursor=cursor,
                    )

                    if self.rabbitmq_publish_service is not None and result:
                        logger.debug(
                            f"{distribution.distribution_id} - Propagating {len(result)} package names to RabbitMQ."
                        )
                        self.rabbitmq_publish_service.publish_package_names(result)

                logger.debug(
                    f"{distribution.distribution_id} - Marking processed."
                )
                distribution.metadata_file_size = metadata_file_size
                distribution.processed = True
                await self.distributions_repo.update_distributions(
                    [distribution], cursor=cursor
                )

                await cursor.execute("commit;")
            except Exception as ex:
                logger.error(
                    f"{distribution.distribution_id} - Error while retrieving/persisting requirements info.",
                    exc_info=ex,
                )
