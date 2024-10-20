import logging
import asyncio

from pipdepgraph.core import parsing
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
            async for known_version in kpvr.iter_known_versions():
                parsed_version = parsing.parse_version_string(known_version.package_version)
                if parsed_version is None:
                    continue

                known_version.epoch = parsed_version.epoch
                known_version.package_release = parsed_version.package_release
                known_version.pre = parsed_version.pre
                known_version.post = parsed_version.post
                known_version.dev = parsed_version.dev
                known_version.local = parsed_version.local
                known_version.is_devrelease = parsed_version.is_devrelease
                known_version.is_postrelease = parsed_version.is_postrelease
                known_version.is_prerelease = parsed_version.is_prerelease

                try:
                    await kpvr.update_known_version(known_version, edit_cursor)
                    await edit_cursor.execute("commit;")
                except Exception as e:
                    logger.error(f"Error reprocessing known version: {known_version}", exc_info=e)



if __name__ == "__main__":
    common.initialize_logger()
    asyncio.run(main())
