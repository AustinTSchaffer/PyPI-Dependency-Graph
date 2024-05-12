import asyncio
import textwrap
import traceback

import aiohttp
import packaging.metadata
import packaging.specifiers
import packaging.utils
import packaging.version
from psycopg import AsyncConnection
from psycopg.rows import dict_row
from psycopg_pool import AsyncConnectionPool
import packaging

import constants

def get_connection_pool() -> AsyncConnectionPool:
    return AsyncConnectionPool(conninfo=constants.POSTGRES_CONNECTION_STRING)

async def populate_known_versions_for_package_name(session: aiohttp.ClientSession, db_pool: AsyncConnectionPool, package_name: str) -> None:
    async with db_pool.connection() as conn:
        known_versions = []

        try:
            print(f'Fetching version information for package: {package_name}')
            package_name = packaging.utils.canonicalize_name(package_name)

            package_info_resp = await session.get(f'https://pypi.org/pypi/{package_name}/json')

            if not package_info_resp.ok:
                print(f'Bad status code from fetching version information for package {package_name}. Code {package_info_resp.status}. Response:', await package_info_resp.text())
                return

            package_info = await package_info_resp.json()

            for version, distributions in package_info['releases'].items():
                for version_metadata in distributions:
                    if version_metadata['packagetype'] in ('sdist', 'bdist_wininst'):
                        # We don't care about source distributions nor Windows EXEs.
                        continue

                    release: list[int] = None
                    try:
                        parsed_version = packaging.version.parse(version)
                        release = parsed_version.release
                    except Exception:
                        print(f"Error parsing version {version} of package {package_name}")
                        traceback.print_exc()

                    # TODO: Persist this somehow.
                    # Supports "in" operator. `'3.5.2' in python_version_specs`
                    # python_version_specs = (
                    #     packaging.specifiers.SpecifierSet(version_metadata['requires_python'])
                    #     if version_metadata['requires_python'] is not None else
                    #     None
                    # )

                    # TODO: Use this for persisting platform info.
                    # _, _, _, version_tag_info = packaging.utils.parse_wheel_filename(version_metadata['filename'])
                    # 
                    # Doesn't support .egg files. Need to figure that out.

                    known_versions.append((
                        package_name,
                        version,
                        f"{{{','.join(map(str, release or []))}}}",
                        version_metadata['python_version'],
                        version_metadata['requires_python'],
                        version_metadata['upload_time_iso_8601'],
                        version_metadata['yanked'],
                        version_metadata['filename'],
                        version_metadata['url'],
                    ))
        except Exception:
            print(f"Error while fetching version information for package: {package_name}")
            traceback.print_exc()
            return

        if not known_versions:
            return

        try:
            print(f'Writing version information for package: {package_name}')
            async with conn.cursor() as insert_cur:
                await insert_cur.executemany(
                    textwrap.dedent(
                        """
                        insert into pypi_packages.known_versions
                            (
                                package_name, package_version, package_release,
                                python_version, requires_python,
                                upload_time, yanked,
                                package_filename, package_url
                            )
                        values
                            (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                        on conflict do nothing;
                        """
                    ),
                    known_versions,
                )

                await insert_cur.execute('commit;')

        except Exception as e:
            print(f"Error while writing version information for package: {package_name}")
            traceback.print_exc()
            return

async def populate_direct_deps_for_known_version(session: aiohttp.ClientSession, db_pool: AsyncConnectionPool, known_version: dict) -> None:
    async with db_pool.connection() as conn:
        known_version_id = known_version['known_version_id']
        package_name = known_version['package_name']
        package_version = known_version['package_version']
        package_url = known_version['package_url']

        try:
            print(f'Fetching dependency information for package {package_name} version {package_version} (kvid: {known_version_id})')

            package_name = packaging.utils.canonicalize_name(package_name)

            # TODO: If the url doesn't have an associated `.metadata` link, download the package and analyze it.
            # https://stackoverflow.com/questions/30188158/how-to-read-python-package-metadata-without-installation
            metadata_file_resp = await session.get(f"{package_url}.metadata")

            # TODO: Write this metric to Postgres.
            print(f"Metadata file size for {package_name}: {metadata_file_resp.content_length} (kvid: {known_version_id})")

            # TODO: is it possible to parse only the header?
            metadata_file_text = await metadata_file_resp.text()
            package_metadata = packaging.metadata.Metadata.from_email(metadata_file_text, validate=False)
            dependencies = []
            if package_metadata.requires_dist:
                for dependency in package_metadata.requires_dist:
                    dependencies.append((
                        known_version_id,
                        str(dependency.marker) if dependency.marker else None,
                        packaging.utils.canonicalize_name(dependency.name, validate=True),
                        ','.join(dependency.extras),
                        str(dependency.specifier),
                    ))

        except Exception:
            print(f"Error processing dependency metadata for package {package_name} version {package_version} (kvid: {known_version_id})")
            traceback.print_exc()
            return

        async with conn.cursor() as update_cur:
            try:
                if dependencies:
                    print(f'Writing dependency information for package {package_name} version {package_version} (kvid: {known_version_id})')
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
                    [known_version_id]
                )

                await update_cur.execute("commit;")
            except Exception:
                print(f"Error writing dependency information for package {package_name} version {package_version} (kvid: {known_version_id})")
                traceback.print_exc()
                await update_cur.execute("rollback;")


async def main():
    async with get_connection_pool() as db_pool, aiohttp.ClientSession(headers={ 'User-Agent': 'schaffer.austin.t@gmail.com' }) as session:
        async with db_pool.connection() as conn:
            async with aiohttp.ClientSession() as session:
                async with conn.cursor(row_factory=dict_row) as select_cur:
                    await select_cur.execute('select package_name from pypi_packages.known_package_names order by date_discovered desc;')

                    while (known_packages := await select_cur.fetchmany(16)):
                        promises = [
                            populate_known_versions_for_package_name(session, db_pool, known_package['package_name'])
                            for known_package in known_packages
                        ]
                        await asyncio.gather(*promises)

                async with conn.cursor(row_factory=dict_row) as select_cur:
                    await select_cur.execute(
                        textwrap.dedent(
                            """
                            select
                                kv.known_version_id,
                                kv.package_name,
                                kv.package_version,
                                kv.package_url
                            from pypi_packages.known_versions kv
                            where not processed
                            order by upload_time desc;
                            """
                        )
                    )

                    while (known_versions := await select_cur.fetchmany(16)):
                        promises = [
                            populate_direct_deps_for_known_version(session, db_pool, kv)
                            for kv in known_versions
                        ]

                        await asyncio.gather(*promises)


if __name__ == '__main__':
    asyncio.run(main())
