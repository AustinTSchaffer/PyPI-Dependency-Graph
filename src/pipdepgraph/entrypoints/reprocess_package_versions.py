import logging
import asyncio

from pipdepgraph import core
from pipdepgraph.entrypoints import common

from pipdepgraph.repositories import (
    known_version_repository,
)

logger = logging.getLogger("pipdepgraph.entrypoints.reprocess_package_versions")


async def main():
    logger.info("Initializing DB pool")
    async with (common.initialize_async_connection_pool() as db_pool,):
        logger.info("Initializing repositories")
        kpvr = known_version_repository.KnownVersionRepository(db_pool)

        async with (db_pool.connection() as conn, conn.cursor() as edit_cursor,):
            async for known_version in kpvr.iter_known_versions(has_package_release=False, has_package_release_numeric=False):
                parsed_version = core.parse_version_string(known_version.package_version)
                if parsed_version.package_release is None and parsed_version.package_release_numeric is None:
                    continue

                known_version.package_release = parsed_version.package_release
                known_version.package_release_numeric = parsed_version.package_release_numeric

                await kpvr.update_known_version(known_version, edit_cursor)

                logger.info(
                    f"{known_version.package_name} - Unpacked package version string {known_version.package_version}: {parsed_version}.",
                )

            await edit_cursor.execute("commit;")


if __name__ == "__main__":
    common.initialize_logger()
    asyncio.run(main())
