import logging
import datetime
import dataclasses
from typing import Optional

import aiohttp
import packaging.utils
import packaging.version
import packaging.metadata

from pipdepgraph import models

PYPI_HOST = "https://pypi.org"

logger = logging.getLogger(__name__)


@dataclasses.dataclass
class PackageVersionDistributionResponse:
    @dataclasses.dataclass
    class VersionDistribution:
        package_type: str
        python_version: str
        requires_python: Optional[str]
        upload_time: datetime.datetime
        yanked: bool
        package_filename: str
        package_url: str
        processed: bool

    versions: dict[str, list[VersionDistribution]]


class PypiApi:
    def __init__(self, session: aiohttp.ClientSession):
        self.session = session

    async def get_package_version_distributions(
        self, package_name: str | models.KnownPackageName
    ) -> PackageVersionDistributionResponse | None:
        """
        Returns a dictionary mapping the package's known versions to a list of distributions
        of those versions. Returns a variant of the core model which does not contain DB identifiers.
        """

        _package_name = (
            package_name if isinstance(package_name, str) else package_name.package_name
        )
        _package_name = packaging.utils.canonicalize_name(_package_name)

        logger.info(
            f"Fetching version/distribution information for package: {_package_name}"
        )

        package_info_resp = await self.session.get(
            f"{PYPI_HOST}/pypi/{_package_name}/json"
        )

        if package_info_resp.status == 404:
            logger.warning(f"Package {_package_name} does not exist on PyPI")
            return None
        elif not package_info_resp.ok:
            message = f"Error fetching package info for package {_package_name}. Code {package_info_resp.status}. Message: {await package_info_resp.text()}"
            logger.error(message)
            raise ValueError(message)

        package_info = await package_info_resp.json()

        result = PackageVersionDistributionResponse(versions={})

        for version, distributions in package_info["releases"].items():
            _distributions: list[
                PackageVersionDistributionResponse.VersionDistribution
            ] = []
            result.versions[version] = _distributions

            for distribution in distributions:
                _distributions.append(
                    PackageVersionDistributionResponse.VersionDistribution(
                        package_type=distribution["packagetype"],
                        package_filename=distribution["filename"],
                        package_url=distribution["url"],
                        processed=False,
                        python_version=distribution["python_version"],
                        requires_python=distribution["requires_python"],
                        upload_time=datetime.datetime.fromisoformat(
                            distribution["upload_time_iso_8601"]
                        ),
                        yanked=distribution["yanked"],
                    )
                )

        return result

    async def get_distribution_metadata(
        self,
        distribution: (
            models.VersionDistribution
            | PackageVersionDistributionResponse.VersionDistribution
        ),
    ) -> tuple[packaging.metadata.Metadata, int]:
        """
        Downloads the distribution's metadata file in order to get the distribution's dependencies,
        and possibly other information. Currently only works for wheels and eggs.

        Returns the parsed metadata file plus the size of the file.
        """

        if distribution.package_type in ("sdist", "bdist_wininst"):
            logger.warning(
                f"Cannot retrieve metadata file for distribution without downloading entire package. Distribution: {distribution}"
            )
            return None, 0

        metadata_file_resp = await self.session.get(
            f"{distribution.package_url}.metadata"
        )

        if metadata_file_resp.status == 404:
            logger.warning(f"Metadata file not found. Distribution: {distribution}")
            return None, 0
        elif not metadata_file_resp.ok:
            message = f"Error fetching metadata file for distribution {distribution}. Code {metadata_file_resp.status}. Message: {await metadata_file_resp.text()}"
            logger.error(message)
            raise ValueError(message)

        metadata_file_text = await metadata_file_resp.text()
        package_metadata = packaging.metadata.Metadata.from_email(
            metadata_file_text, validate=False
        )

        return package_metadata, metadata_file_resp.content_length


# TODO: Persist this somehow.
# Supports "in" operator. `'3.5.2' in python_version_specs`
# python_version_specs = (
#     packaging.specifiers.SpecifierSet(distribution['requires_python'])
#     if distribution['requires_python'] is not None else
#     None
# )

# TODO: Use this for persisting platform info.
# _, _, _, version_tag_info = packaging.utils.parse_wheel_filename(distribution['filename'])
#
# Doesn't support .egg files. Need to figure that out.
