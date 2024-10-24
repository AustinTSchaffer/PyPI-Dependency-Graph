import datetime
import logging

import packaging
import packaging.version
from psycopg_pool import AsyncConnectionPool
from psycopg.rows import dict_row

from pipdepgraph import models, pypi_api, constants
from pipdepgraph.core import parsing
from pipdepgraph.repositories import (
    distributions_repository,
    package_names_repository,
    versions_repository,
)

from pipdepgraph.services import (
    rabbitmq_publish_service,
)

RECHECK_PACKAGE_NAME_INTERVAL = datetime.timedelta(hours=1)
"""
The interval that this module uses to determine if a `package_name`
has been processed recently.
"""

logger = logging.getLogger(__name__)


class PackageNameProcessingService:
    def __init__(
        self,
        *,
        db_pool: AsyncConnectionPool,
        pnr: package_names_repository.PackageNamesRepository,
        vr: versions_repository.VersionsRepository,
        dr: distributions_repository.DistributionsRepository,
        pypi: pypi_api.PypiApi,
        rmq_pub: rabbitmq_publish_service.RabbitMqPublishService = None,
    ):
        self.db_pool = db_pool
        self.package_names_repo = pnr
        self.versions_repo = vr
        self.distributions_repo = dr
        self.pypi = pypi
        self.rabbitmq_publish_service = rmq_pub

    async def propagate_discovered_package_names(
        self,
    ):
        """
        Propagates discovered package names from `requirements` back to `package_names`.
        """

        logger.info(
            "Propagating package names from requirements back to package_names."
        )
        await self.package_names_repo.propagate_dependency_names()

    async def run_from_database(self):
        """
        Runs through all package names from the database and processes each one.
        """
        async for package in self.package_names_repo.iter_package_names(
            date_last_checked_before=datetime.datetime.now()
            - RECHECK_PACKAGE_NAME_INTERVAL
        ):
            await self.process_package_name(package, ignore_date_last_checked=True)

    async def process_package_name(
        self,
        package_name: str | models.PackageName,
        ignore_date_last_checked: bool = False,
    ):
        """
        Processes a single package name.

        - inserts/retrieves the package into/from `package_names` to ensure that it exists.
        - fetches the package's info from the PyPI API
        - inserts the package's versions into `versions`
        - inserts the package's distributions into `distributions`
        - updates the `date_last_checked` field on the `package_name` record

        `ignore_date_last_checked` can be used to force this method to process packages that
        have been processed recently.
        """

        logger.info(f"Processing package name: {package_name}")

        _package_name = await self.package_names_repo.get_package_name(
            package_name
        )

        if not _package_name:
            await self.package_names_repo.insert_package_names(
                [package_name]
            )
            _package_name = await self.package_names_repo.get_package_name(
                package_name
            )

            if not _package_name:
                raise ValueError(
                    f'Error storing/retrieving package named "{package_name}" to/from database.'
                )

        package_name = _package_name

        #
        # Check if the package has already been processed recently.
        #

        now = datetime.datetime.now()
        should_process_package_name = (
            ignore_date_last_checked
            or package_name.date_last_checked is None
            or package_name.date_last_checked < (now - RECHECK_PACKAGE_NAME_INTERVAL)
        )

        if not should_process_package_name:
            return

        logger.info(f"{package_name} - Getting version/distribution information.")

        package_vers_dists_result = await self.pypi.get_package_distributions_legacy(
            package_name
        )

        if not package_vers_dists_result:
            logger.debug(f"{package_name} - Marking package checked.")
            package_name.date_last_checked = now
            await self.package_names_repo.update_package_names(
                [package_name]
            )
            return

        versions: list[models.Version] = [
            models.Version(
                version_id=None,
                package_name=package_name.package_name,
                package_version=version_string,
                date_discovered=None,
            )
            for version_string in package_vers_dists_result.versions.keys()
        ]

        for version in versions:
            parsed_version = parsing.parse_version_string(version.package_version)
            if parsed_version is None:
                logger.warning(
                    f"{package_name.package_name} - Error parsing version {version.package_version}.",
                )
                continue

            version.epoch = parsed_version.epoch
            version.package_release = parsed_version.package_release
            version.pre = parsed_version.pre
            version.post = parsed_version.post
            version.dev = parsed_version.dev
            version.local = parsed_version.local
            version.is_prerelease = parsed_version.is_prerelease
            version.is_postrelease = parsed_version.is_postrelease
            version.is_devrelease = parsed_version.is_devrelease

        async with self.db_pool.connection() as conn, conn.cursor(
            row_factory=dict_row
        ) as cursor:
            try:
                logger.debug(f"{package_name} - Saving version information.")
                await self.versions_repo.insert_versions(
                    versions, cursor=cursor
                )

                logger.debug(f"{package_name} - Building version_id map.")
                version_id_map = {
                    version.package_version: version.version_id
                    async for version in self.versions_repo.iter_versions(
                        package_name=package_name.package_name,
                        cursor=cursor,
                    )
                }

                distributions: list[models.Distribution] = [
                    models.Distribution(
                        distribution_id=None,
                        version_id=version_id_map[version],
                        metadata_file_size=None,
                        processed=False,
                        python_version=distribution.python_version,
                        package_filename=distribution.package_filename,
                        package_type=distribution.package_type,
                        package_url=distribution.package_url,
                        requires_python=distribution.requires_python,
                        upload_time=distribution.upload_time,
                        yanked=distribution.yanked,
                    )
                    for version, distributions in package_vers_dists_result.versions.items()
                    for distribution in distributions
                ]

                logger.debug(f"{package_name} - Saving distribution information.")
                result = (
                    await self.distributions_repo.insert_distributions(
                        distributions,
                        return_inserted=(self.rabbitmq_publish_service is not None),
                        cursor=cursor,
                    )
                )

                if self.rabbitmq_publish_service is not None and result:
                    logger.debug(
                        f"{package_name} - Publishing new distributions to RabbitMQ."
                    )
                    self.rabbitmq_publish_service.publish_distributions(result)

                logger.debug(f"{package_name} - Marking package checked.")
                package_name.date_last_checked = now
                await self.package_names_repo.update_package_names(
                    [package_name], cursor=cursor
                )

                await cursor.execute("commit;")

            except Exception as ex:
                logger.error(
                    "Error while processing package %s", package_name, exc_info=ex
                )
                await cursor.execute("rollback;")
                raise
