import logging
import datetime
import dataclasses
from typing import Optional, AsyncIterable
import re
import warnings

import aiohttp
import packaging.utils
import packaging.version
import packaging.metadata

from pipdepgraph import models

PYPI_HOST = "https://pypi.org"
POPULAR_PACKAGES_URL = (
    "https://hugovk.github.io/top-pypi-packages/top-pypi-packages-30-days.min.json"
)
PACKAGE_NAME_REGEX = re.compile(r"/simple/(?P<package_name>[a-z0-9\-_\.]+)", re.I)
ACCEPT_JSON_HEADER = 'application/vnd.pypi.simple.v1+json'

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


@dataclasses.dataclass
class PopularPackagesResponse:
    @dataclasses.dataclass
    class PopularPackage:
        package_name: str
        popularity: int

    popularity_metric: str
    packages: list[PopularPackage]


class PypiApi:
    def __init__(self, session: aiohttp.ClientSession):
        self.session = session

    async def get_package_distributions_legacy(
        self, package_name: str | models.PackageName
    ) -> PackageVersionDistributionResponse | None:
        """
        Returns a dictionary mapping the package's versions to a list of distributions
        of those versions. Returns a variant of the core model which does not contain DB
        identifiers.

        Uses the "legacy JSON API": https://pypi.org/pypi/{package}/json
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
            models.Distribution
            | PackageVersionDistributionResponse.VersionDistribution
        ),
    ) -> tuple[packaging.metadata.Metadata, int]:
        """
        Downloads the distribution's metadata file in order to get the distribution's dependencies,
        and possibly other information. Currently only works for wheels and eggs.

        Returns the parsed metadata file plus the size of the file.
        """

        if distribution.package_type != 'bdist_wheel':
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

        metadata_file_content = await metadata_file_resp.content.read()
        package_metadata = packaging.metadata.Metadata.from_email(
            metadata_file_content, validate=False
        )

        return package_metadata, metadata_file_resp.content_length

    async def iter_all_package_names(self) -> AsyncIterable[str]:
        raise NotImplementedError()

    async def iter_all_package_names_regex(self) -> AsyncIterable[str]:
        """
        Async iterable over all package names from PyPI's "simple" index.
        The package names are assumed to be canonicalized and in
        alphabetical order, though neither is guaranteed.
        """

        logger.warning("iter_all_package_names_regex will be deprecated in favor of iter_all_package_names")

        response = await self.session.get(f"{PYPI_HOST}/simple/")
        if not response.ok:
            raise ValueError("Error getting list of packages from PyPI", response)

        async for line in response.content:
            if re_result := PACKAGE_NAME_REGEX.search(line.decode("utf-8")):
                package_name = re_result["package_name"]
                yield package_name

    async def get_popular_packages(self) -> PopularPackagesResponse:
        response = await self.session.get(POPULAR_PACKAGES_URL)
        if not response.ok:
            raise ValueError(f"Error getting list of popular packages from URL: {POPULAR_PACKAGES_URL}")

        json_response = await response.json()
        packages = [
            PopularPackagesResponse.PopularPackage(
                package_name=row['project'],
                popularity=row['download_count'],
            )
            for row in json_response['rows']
        ]

        result = PopularPackagesResponse(popularity_metric='downloads', packages=packages)

        return result
