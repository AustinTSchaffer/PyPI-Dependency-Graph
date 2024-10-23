import logging
import asyncio

from pipdepgraph.core import parsing
from pipdepgraph.entrypoints import common

from pipdepgraph.repositories import (
    versions_repository,
)

logger = logging.getLogger("pipdepgraph.entrypoints.reprocess_package_versions")


async def main():
    logger.info("Initializing DB pool")
    async with (common.initialize_async_connection_pool() as db_pool,):
        logger.info("Initializing repositories")
        vr = versions_repository.VersionsRepository(db_pool)

        async with (db_pool.connection() as conn, conn.cursor() as edit_cursor,):
            async for version in vr.iter_versions():
                parsed_version = parsing.parse_version_string(version.package_version)
                if parsed_version is None:
                    continue

                version.epoch = parsed_version.epoch
                version.package_release = parsed_version.package_release
                version.pre = parsed_version.pre
                version.post = parsed_version.post
                version.dev = parsed_version.dev
                version.local = parsed_version.local
                version.is_devrelease = parsed_version.is_devrelease
                version.is_postrelease = parsed_version.is_postrelease
                version.is_prerelease = parsed_version.is_prerelease

                try:
                    await vr.update_version(version, edit_cursor)
                    await edit_cursor.execute("commit;")
                except Exception as e:
                    logger.error(f"Error reprocessing version: {version}", exc_info=e)



if __name__ == "__main__":
    common.initialize_logger()
    asyncio.run(main())
