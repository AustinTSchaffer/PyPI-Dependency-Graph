import datetime
import logging

import packaging
import packaging.version

from pipdepgraph import models, pypi_api
from pipdepgraph.repositories import (
    known_package_name_repository,
    known_versions_repository,
    version_distributions_repository,
)

RECHECK_PACKAGE_NAME_INTERVAL = datetime.timedelta(hours=1)
"""
The interval that this module uses to determine if a `known_package_name`
has been processed recently.
"""

logger = logging.getLogger(__name__)


class KnownPackageProcessingService:
    def __init__(
        self,
        *,
        kpnr: known_package_name_repository.KnownPackageNameRepository,
        kvr: known_versions_repository.KnownVersionRepository,
        vdr: version_distributions_repository.VersionDistributionRepository,
        pypi: pypi_api.PypiApi,
    ):
        self.known_package_names_repo = kpnr
        self.known_versions_repo = kvr
        self.version_distributions_repo = vdr
        self.pypi = pypi

    async def propagate_discovered_package_names(
        self,
    ):
        """
        Propagates discovered package names from `direct_dependencies` back to `known_package_names`.
        """

        logger.info(
            "Propagating package names from direct_dependencies back to known_package_names."
        )
        await self.known_package_names_repo.propagate_dependency_names()

    async def run_from_database(self):
        """
        Runs through all known package names from the database and processes each one.
        """
        async for package in self.known_package_names_repo.iter_known_package_names(
            date_last_checked_before=datetime.datetime.now()
            - RECHECK_PACKAGE_NAME_INTERVAL
        ):
            self.process_package_name(package, ignore_date_last_checked=True)

    async def process_package_name(
        self,
        package_name: str | models.KnownPackageName,
        ignore_date_last_checked: bool = False,
    ):
        """
        Processes a single package name.

        - inserts/retrieves the package into/from `known_package_names` to ensure that it exists.
        - fetches the package's info from the PyPI API
        - inserts the package's versions into `known_versions`
        - inserts the package's distributions into `version_distributions`
        - updates the `date_last_checked` field on the `known_package_name` record

        `ignore_date_last_checked` can be used to force this method to process packages that
        have been processed recently.
        """

        await self.known_package_names_repo.insert_known_package_names([package_name])
        _package_name = await self.known_package_names_repo.get_known_package_name(
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
        process_package_name = ignore_date_last_checked or (
            package_name.date_last_checked is not None
            and package_name.date_last_checked < (now - RECHECK_PACKAGE_NAME_INTERVAL)
        )

        if not process_package_name:
            return

        logger.info(f"{package_name} - Getting version/distribution information.")

        package_vers_dists_result = await self.pypi.get_package_version_distributions(
            package_name
        )

        if not package_vers_dists_result:
            return

        known_versions: list[models.KnownVersion] = [
            models.KnownVersion(
                known_version_id=None,
                package_name=package_name.package_name,
                package_version=version_string,
                package_release=None,
                date_discovered=None,
            )
            for version_string in package_vers_dists_result.versions.keys()
        ]

        for known_version in known_versions:
            try:
                parsed_version = packaging.version.parse(known_version.package_version)
                known_version.package_release = parsed_version.release
            except Exception as ex:
                logger.error(
                    f"Error parsing version {known_version.package_version} of package {package_name.package_name}.",
                    exc_info=ex,
                )

        logger.debug(f"{package_name} - Saving version information.")
        await self.known_versions_repo.insert_known_versions(known_versions)

        logger.debug(f"{package_name} - Building known_version_id map.")
        known_version_id_map = {
            known_version.package_version: known_version.known_version_id
            async for known_version in self.known_versions_repo.iter_known_versions(
                package_name=package_name.package_name
            )
        }

        version_distributions: list[models.VersionDistribution] = [
            models.VersionDistribution(
                version_distribution_id=None,
                known_version_id=known_version_id_map[version],
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
        await self.version_distributions_repo.insert_version_distributions(
            version_distributions
        )

        logger.debug(f"{package_name} - Marking package checked.")
        package_name.date_last_checked = now
        await self.known_package_names_repo.update_known_package_names([package_name])
