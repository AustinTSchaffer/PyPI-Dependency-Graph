import logging
import os
import asyncio

from pipdepgraph.core import parsing
from pipdepgraph.entrypoints import common

from pipdepgraph.repositories import (
    versions_repository,
    requirements_repository,
)

DIST_ID_HASH_ALG = os.getenv("DIST_ID_HASH_ALG", "md5")
DIST_ID_HASH_MOD_BASE = int(os.getenv("DIST_ID_HASH_MOD_BASE", "16"))
DIST_ID_HASH_MOD_FILTER = int(os.getenv("DIST_ID_HASH_MOD_FILTER", "1")) - 1
COMMIT_BATCH_SIZE = int(os.getenv("COMMIT_FREQUENCY", 1000))

logger = logging.getLogger("pipdepgraph.entrypoints.reprocess_requirements")


async def main():
    logger.info("Initializing DB pool")
    async with (common.initialize_async_connection_pool() as db_pool,):
        logger.info("Initializing repositories")
        rr = requirements_repository.RequirementsRepository(db_pool)

        async with (db_pool.connection() as conn, conn.cursor() as edit_cursor,):
            hashmodfilter = (DIST_ID_HASH_ALG, DIST_ID_HASH_MOD_BASE, DIST_ID_HASH_MOD_FILTER)
            logger.info(f"Iterating over requirements matching hashmod filter on distribution_id: {hashmodfilter}")
            records_updated = 0
            async for requirement in rr.iter_requirements(dist_id_hash_mod_filter=hashmodfilter, dependency_extras_arr_is_none=True):
                requirement.dependency_extras_arr = []
                if requirement.dependency_extras:
                    requirement.dependency_extras_arr = requirement.dependency_extras.split(',')
                logger.info(f"Updating requirement: {requirement}")
                await rr.update_requirement(requirement, cursor=edit_cursor)
                records_updated = (records_updated + 1) % COMMIT_BATCH_SIZE
                if records_updated == 0:
                    logger.info(f"Committing batch of size: {COMMIT_BATCH_SIZE}")
                    await edit_cursor.execute("commit;")
                    logger.info(f"Commit completed.")

            await edit_cursor.execute("commit;")


if __name__ == "__main__":
    common.initialize_logger()
    asyncio.run(main())
