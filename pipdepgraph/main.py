import asyncio
import textwrap
import traceback
import sys
import logging
import datetime

import aiohttp
import packaging.metadata
import packaging.specifiers
import packaging.utils
import packaging.version
from psycopg.rows import dict_row
from psycopg_pool import AsyncConnectionPool
import packaging

from pipdepgraph import constants, pypi_api, models
from pipdepgraph.repositories import (
    known_package_name_repository,
    known_versions_repository,
    version_distributions_repository,
    direct_dependencies_repository,
)

logger = logging.getLogger(__name__)


def get_connection_pool() -> AsyncConnectionPool:
    return AsyncConnectionPool(conninfo=constants.POSTGRES_CONNECTION_STRING)


async def populate_direct_deps_for_known_version(
    session: aiohttp.ClientSession, db_pool: AsyncConnectionPool, known_version: dict
) -> None:
    async with db_pool.connection() as conn:
        known_version_id = known_version["known_version_id"]
        package_name = known_version["package_name"]
        package_version = known_version["package_version"]
        package_url = known_version["package_url"]

        try:
            print(
                f"Fetching dependency information for package {package_name} version {package_version} (kvid: {known_version_id})"
            )

            package_name = packaging.utils.canonicalize_name(package_name)

            # TODO: If the url doesn't have an associated `.metadata` link, download the package and analyze it.
            # https://stackoverflow.com/questions/30188158/how-to-read-python-package-metadata-without-installation
            metadata_file_resp = await session.get(f"{package_url}.metadata")

            # TODO: Write this metric to Postgres.
            print(
                f"Metadata file size for {package_name}: {metadata_file_resp.content_length} (kvid: {known_version_id})"
            )

            # TODO: is it possible to parse only the header?
            metadata_file_text = await metadata_file_resp.text()
            package_metadata = packaging.metadata.Metadata.from_email(
                metadata_file_text, validate=False
            )

        except Exception:
            print(
                f"Error processing dependency metadata for package {package_name} version {package_version} (kvid: {known_version_id})"
            )
            traceback.print_exc()
            return

        async with conn.cursor() as update_cur:
            try:
                if dependencies:
                    print(
                        f"Writing dependency information for package {package_name} version {package_version} (kvid: {known_version_id})"
                    )
                    await update_cur.executemany(
                        textwrap.dedent(
                            """
                            insert into pypi_packages.direct_dependencies
                                (
                                    known_version_id,
                                    extras,
                                    dependency_name,
                                    dependency_extras,
                                    version_constraint
                                )
                            values
                                (%s, %s, %s, %s, %s)
                            on conflict do nothing;
                            """
                        ),
                        dependencies,
                    )

                await update_cur.execute(
                    textwrap.dedent(
                        """
                        update pypi_packages.known_versions
                        set processed = true
                        where known_version_id = %s;
                        """
                    ),
                    [known_version_id],
                )

                await update_cur.execute("commit;")
            except Exception:
                print(
                    f"Error writing dependency information for package {package_name} version {package_version} (kvid: {known_version_id})"
                )
                traceback.print_exc()
                await update_cur.execute("rollback;")


async def main():
    async with get_connection_pool() as db_pool, aiohttp.ClientSession(
        headers={"User-Agent": "schaffer.austin.t@gmail.com"}
    ) as session:
        pypi = pypi_api.PypiApi(session)
        kpnr = known_package_name_repository.KnownPackageNameRepository(db_pool)
        kvr = known_versions_repository.KnownVersionRepository(db_pool)
        vdr = version_distributions_repository.VersionDistributionRepository(db_pool)
        ddr = direct_dependencies_repository.DirectDependencyRepository(db_pool)

        async for package in kpnr.iter_known_package_names(
            date_last_checked_before=datetime.datetime.now()
            - datetime.timedelta(hours=1)
        ):
            logger.info(f"{package} - Getting version/distribution information.")

            package_vers_dists_result = await pypi.get_package_version_distributions(
                package
            )
            if not package_vers_dists_result:
                continue

            known_versions: list[models.KnownVersion] = [
                models.KnownVersion(
                    known_version_id=None,
                    package_name=package.package_name,
                    package_version=version_string,
                    package_release=None,
                    date_discovered=None,
                )
                for version_string in package_vers_dists_result.versions.keys()
            ]

            for known_version in known_versions:
                try:
                    parsed_version = packaging.version.parse(
                        known_version.package_version
                    )
                    known_version.package_release = parsed_version.release
                except Exception as ex:
                    logger.error(
                        f"Error parsing version {known_version.package_version} of package {package.package_name}.",
                        exc_info=ex,
                    )

            logger.debug(f"{package} - Saving version information")
            await kvr.insert_known_versions(known_versions)

            logger.debug(f"{package} - Building known_version_id map")
            known_version_id_map = {
                known_version.package_version: known_version.known_version_id
                async for known_version in kvr.iter_known_versions(
                    package_name=package.package_name
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

            logger.debug(f"{package} - Saving distribution information")
            await vdr.insert_version_distributions(version_distributions)

            package.date_last_checked = datetime.datetime.now()
            await kpnr.update_known_package_names([package])

        async for unprocessed_distribution in vdr.iter_version_distributions(
            processed=False
        ):
            logger.info(
                f"{unprocessed_distribution.version_distribution_id} - Getting direct dependencies."
            )

            try:
                metadata, metadata_file_size = await pypi.get_distribution_metadata(
                    unprocessed_distribution
                )

                if not metadata:
                    unprocessed_distribution.metadata_file_size = 0
                    unprocessed_distribution.processed = True
                    await vdr.update_version_distributions([unprocessed_distribution])
                    continue

                direct_dependencies: list[models.DirectDependency] = []
                if metadata.requires_dist:
                    for dependency in metadata.requires_dist:
                        direct_dependencies.append(
                            models.DirectDependency(
                                version_distribution_id=unprocessed_distribution.version_distribution_id,
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

                await ddr.insert_direct_dependencies(direct_dependencies)

                unprocessed_distribution.metadata_file_size = metadata_file_size
                unprocessed_distribution.processed = True
                await vdr.update_version_distributions([unprocessed_distribution])

            except Exception as ex:
                logger.error(f"{unprocessed_distribution.version_distribution_id} - Error while retrieving/persisting direct dependency info.", exc_info=ex)


if __name__ == "__main__":
    root = logging.getLogger()
    root.setLevel(logging.INFO)

    handler = logging.StreamHandler(sys.stdout)
    handler.setLevel(logging.DEBUG)
    formatter = logging.Formatter(
        "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )
    handler.setFormatter(formatter)
    root.addHandler(handler)

    asyncio.run(main())
