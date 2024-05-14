from typing import AsyncIterable
import textwrap
import itertools

from psycopg_pool import AsyncConnectionPool
from psycopg import AsyncCursor
from psycopg.rows import dict_row

from pipdepgraph import models, constants

TABLE_NAME = "pypi_packages.known_versions"


class KnownVersionRepository:
    def __init__(self, db_pool: AsyncConnectionPool):
        self.db_pool = db_pool

    async def _insert_known_versions(
        self, known_versions: list[models.KnownVersion], cursor: AsyncCursor
    ) -> dict[tuple[str, str], str]:
        if not known_versions:
            return {}

        PARAMS_PER_INSERT = 4
        for known_versions in itertools.batched(
            known_versions, constants.POSTGRES_MAX_QUERY_PARAMS // PARAMS_PER_INSERT
        ):
            query = f"insert into {TABLE_NAME} (package_name, package_version, package_release, date_discovered) values "

            query += ",".join(
                "( %s, %s, %s, coalesce(%s, now()) ) "
                for _ in range(len(known_versions))
            )
            query += " on conflict do nothing; "

            params = [None] * PARAMS_PER_INSERT * len(known_versions)
            offset = 0
            for kv in known_versions:
                params[offset + 0] = kv.package_name
                params[offset + 1] = kv.package_version
                params[offset + 2] = (
                    f'{{{",".join(map(str, kv.package_release or []))}}}'
                )
                params[offset + 3] = kv.date_discovered
                offset += PARAMS_PER_INSERT

            await cursor.execute(query, params)

    async def insert_known_versions(
        self,
        known_versions: list[models.KnownVersion],
        cursor: AsyncCursor | None = None,
    ) -> dict[tuple[str, str], str]:
        if cursor:
            return await self._insert_known_versions(known_versions, cursor)
        else:
            async with self.db_pool.connection() as conn, conn.cursor() as cursor:
                result = await self._insert_known_versions(known_versions, cursor)
                await cursor.execute("commit;")
                return result

    async def iter_known_versions(
        self, package_name: str | None = None, package_version: str | None = None
    ) -> AsyncIterable[models.KnownVersion]:
        async with self.db_pool.connection() as conn, conn.cursor(
            row_factory=dict_row
        ) as cursor:
            query = textwrap.dedent(
                f"""
                    select
                        kv.known_version_id,
                        kv.package_name,
                        kv.package_version,
                        kv.package_release,
                        kv.date_discovered
                    from {TABLE_NAME} kv
                """
            )

            params = []

            if package_name is not None:
                if not params:
                    query += " where "
                else:
                    query += " and "

                query += " package_name = %s "
                params.append(package_name)

            if package_version is not None:
                if not params:
                    query += " where "
                else:
                    query += " and "

                query += " package_version = %s "
                params.append(package_version)

            await cursor.execute(query, params)
            async for record in cursor:
                yield models.KnownVersion(**record)
