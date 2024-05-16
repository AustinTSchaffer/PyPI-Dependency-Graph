from typing import AsyncIterable
import textwrap
import itertools

from psycopg_pool import AsyncConnectionPool
from psycopg import AsyncCursor

from pipdepgraph import models, constants
from pipdepgraph.repositories import table_names


class DirectDependencyRepository:
    def __init__(self, db_pool: AsyncConnectionPool):
        self.db_pool = db_pool

    async def _insert_direct_dependencies(
        self,
        direct_dependencies: list[models.DirectDependency],
        cursor: AsyncCursor,
    ):
        if not direct_dependencies:
            return

        PARAMS_PER_INSERT = 5
        for direct_dependencies in itertools.batched(
            direct_dependencies,
            constants.POSTGRES_MAX_QUERY_PARAMS // PARAMS_PER_INSERT,
        ):
            query = textwrap.dedent(
                f"""
                    insert into {table_names.DIRECT_DEPENDENCIES}
                    (
                        version_distribution_id,
                        extras,
                        dependency_name,
                        dependency_extras,
                        version_constraint
                    )
                    values
                """
            )

            query += ",".join(
                " ( %s, %s, %s, %s, %s ) " for _ in range(len(direct_dependencies))
            )
            query += " on conflict do nothing; "

            params = [None] * PARAMS_PER_INSERT * len(direct_dependencies)
            offset = 0
            for dd in direct_dependencies:
                params[offset + 0] = dd.version_distribution_id
                params[offset + 1] = dd.extras
                params[offset + 2] = dd.dependency_name
                params[offset + 3] = dd.dependency_extras
                params[offset + 4] = dd.version_constraint
                offset += PARAMS_PER_INSERT

            await cursor.execute(query, params)

    async def insert_direct_dependencies(
        self,
        direct_dependencies: list[models.DirectDependency],
        cursor: AsyncCursor | None = None,
    ):
        if cursor:
            await self._insert_direct_dependencies(direct_dependencies, cursor)
        else:
            async with self.db_pool.connection() as conn, conn.cursor() as cursor:
                await self._insert_direct_dependencies(direct_dependencies, cursor)
                await cursor.execute("commit;")
