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
DIST_ID_HASH_MOD_FILTER = int(os.getenv("DIST_ID_HASH_MOD_FILTER", "0")) - 1

logger = logging.getLogger("pipdepgraph.entrypoints.reprocess_requirements")


async def main():
    logger.info("Initializing DB pool")
    async with (common.initialize_async_connection_pool() as db_pool,):
        logger.info("Initializing repositories")
        rr = requirements_repository.RequirementsRepository(db_pool)

        async with (db_pool.connection() as conn, conn.cursor() as edit_cursor,):
            hashmodfilter = (DIST_ID_HASH_ALG, DIST_ID_HASH_MOD_BASE, DIST_ID_HASH_MOD_FILTER)
            logger.info(f"Iterating over requirements matching hashmod filter on distribution_id: {hashmodfilter}")
            async for requirement in rr.iter_requirements(dist_id_hash_mod_filter=hashmodfilter):
                requirement.dependency_extras_arr = []
                if requirement.dependency_extras:
                    requirement.dependency_extras_arr = requirement.dependency_extras.split(',')
                await rr.update_requirement(requirement, cursor=edit_cursor)
                await edit_cursor.execute("commit;")


if __name__ == "__main__":
    common.initialize_logger()
    asyncio.run(main())
