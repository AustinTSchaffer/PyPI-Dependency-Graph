import logging

import packaging.utils

from pipdepgraph import models, pypi_api
from pipdepgraph.repositories import (
    version_distributions_repository,
    direct_dependencies_repository,
)

logger = logging.getLogger(__name__)


class VersionDistributionProcessingService:
    def __init__(
        self,
        *,
        vdr: version_distributions_repository.VersionDistributionRepository,
        ddr: direct_dependencies_repository.DirectDependencyRepository,
        pypi: pypi_api.PypiApi,
    ):
        self.version_distributions_repo = vdr
        self.direct_dependencies_repo = ddr
        self.pypi = pypi

    async def run_from_database(self):
        """
        Runs through all unprocessed version distributions from the database and processes each one.
        """
        async for (
            version_distribution
        ) in self.version_distributions_repo.iter_version_distributions(
            processed=False
        ):
            self.process_version_distribution(version_distribution)

    async def process_version_distribution(
        self,
        distribution: models.VersionDistribution,
        ignore_processed_flag: bool = False,
    ):
        """
        Processes a single version distribution.

        - Fetches the version distribution's `.metadata` file from the PyPI API.
        - Parses the metadata file, extracting the package's direct dependencies.
        -

        `ignore_processed_flag` can be used to force this method to reprocess a distribution that
        has already been processed.
        """

        if not ignore_processed_flag and distribution.processed:
            return

        logger.info(
            f"{distribution.version_distribution_id} - Getting direct dependencies."
        )

        try:
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

            direct_dependencies: list[models.DirectDependency] = []
            if metadata.requires_dist:
                for dependency in metadata.requires_dist:
                    direct_dependencies.append(
                        models.DirectDependency(
                            version_distribution_id=distribution.version_distribution_id,
                            extras=(
                                str(dependency.marker) if dependency.marker else None
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
                direct_dependencies
            )

            logger.debug(f"{distribution.version_distribution_id} - Marking processed.")
            distribution.metadata_file_size = metadata_file_size
            distribution.processed = True
            await self.version_distributions_repo.update_version_distributions(
                [distribution]
            )

        except Exception as ex:
            logger.error(
                f"{distribution.version_distribution_id} - Error while retrieving/persisting direct dependency info.",
                exc_info=ex,
            )
