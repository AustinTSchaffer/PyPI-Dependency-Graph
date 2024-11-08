import logging

import packaging.utils
import packaging.requirements
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
    """
    The distribution processing service processes a single distribution record
    at a time, performing the following actions in sequence.

    - Deletes all requirement records linked to the distribution in postgres.
    - Fetches the distribution's `.metadata` file from the PyPI API (if it's a wheel).
    - Parses the metadata file, extracting the package's requirements (best effort).
    - Persists the package's requirements to postgres.
    - (optional) Propagates newly discovered package names back to postgres/rabbitmq.
    - Marks the distribution as "processed" in postgres.
    """

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


    @staticmethod
    def convert_requirement(
        distribution_id: str,
        requirement: str | packaging.requirements.Requirement,
    ) -> models.Requirement:
        if isinstance(requirement, str):
            requirement = packaging.requirements.Requirement(requirement)

        return models.Requirement(
            requirement_id=None,
            distribution_id=distribution_id,
            extras=(
                str(requirement.marker)
                if requirement.marker
                else ""
            ),
            dependency_extras=",".join(requirement.extras),
            dependency_name=packaging.utils.canonicalize_name(
                requirement.name, validate=True
            ),
            version_constraint=str(requirement.specifier),
            dependency_extras_arr=list(requirement.extras),
            parsable=True,
        )


    async def process_distribution(
        self,
        distribution: models.Distribution,
        ignore_processed_flag: bool = constants.DIST_PROCESSOR_IGNORE_PROCESSED_FLAG,
        discover_package_names: bool = constants.DIST_PROCESSOR_DISCOVER_PACKAGE_NAMES,
    ):
        """
        Processes a single distribution. See the class's docs for more info.

        `ignore_processed_flag` can be used to force this service to reprocess distributions
        that have their `processed` flag set to `false`.

        `discover_package_names` can be used to propagate newly discovered package names back
        into the database and rabbitmq, creating a feedback loop.
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
            requirements: list[models.Requirement] = []
            try:
                logger.debug(
                    f"{distribution.distribution_id} - Deleting existing requirements."
                )

                await self.requirements_repo.delete_requirements(
                    distribution_id=distribution.distribution_id,
                    cursor=cursor,
                )

                try:
                    if metadata.requires_dist:
                        for requirement in metadata.requires_dist:
                            requirements.append(DistributionProcessingService.convert_requirement(
                                distribution_id=distribution.distribution_id,
                                requirement=requirement,
                            ))

                except Exception as ex:
                    logger.warning("Error while iterating through metadata.requires_dist", exc_info=True)
                    raw_req_dist = metadata._raw["requires_dist"]
                    for req_idx in range(len(raw_req_dist)):
                        try:
                            requirement_text = raw_req_dist[req_idx]
                            requirements.append(DistributionProcessingService.convert_requirement(
                                distribution_id=distribution.distribution_id,
                                requirement=requirement_text,
                            ))

                        except Exception as ex:
                            logger.warning("Unable to parse requirement: %s", requirement_text)
                            requirements.append(
                                models.Requirement(
                                    requirement_id=None,
                                    distribution_id=distribution.distribution_id,
                                    dependency_name=requirement_text,
                                    parsable=False,
                                    # TODO: Can any of these be refined?
                                    extras="",
                                    dependency_extras="",
                                    version_constraint="",
                                    dependency_extras_arr=[],
                                )
                            )

                logger.info(
                    f"{distribution.distribution_id} - Found {len(requirements)} requirements."
                )

                await self.requirements_repo.insert_requirements(
                    requirements,
                    cursor=cursor,
                )

                if discover_package_names:
                    distinct_package_names = list(
                        {dd.dependency_name for dd in requirements}
                    )

                    logger.debug(
                        f"{distribution.distribution_id} - Propagating {len(distinct_package_names)} package names back to Postgres."
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
                await cursor.execute("rollback;")
                raise
