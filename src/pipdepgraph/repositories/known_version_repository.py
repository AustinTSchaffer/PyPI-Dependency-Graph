from typing import AsyncIterable
import textwrap
import itertools

from psycopg_pool import AsyncConnectionPool
from psycopg import AsyncCursor
from psycopg.rows import dict_row

from pipdepgraph import models, constants
from pipdepgraph.repositories import table_names


class KnownVersionRepository:
    def __init__(self, db_pool: AsyncConnectionPool):
        self.db_pool = db_pool

    async def _insert_known_versions(
        self, known_versions: list[models.KnownVersion], cursor: AsyncCursor
    ) -> None:
        if not known_versions:
            return None

        PARAMS_PER_INSERT = 5
        for known_versions in itertools.batched(
            known_versions, constants.POSTGRES_MAX_QUERY_PARAMS // PARAMS_PER_INSERT
        ):
            query = f"insert into {table_names.KNOWN_VERSIONS} (package_name, package_version, package_release, date_discovered) values "

            query += ",".join(
                " ( %s, %s, %s, %s, coalesce(%s, now()) ) "
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
                params[offset + 3] = (
                    f'{{{",".join(map(str, kv.package_release_numeric or []))}}}'
                    if kv.package_release_numeric else None
                )
                params[offset + 4] = kv.date_discovered
                offset += PARAMS_PER_INSERT

            await cursor.execute(query, params)

    async def insert_known_versions(
        self,
        known_versions: list[models.KnownVersion],
        cursor: AsyncCursor | None = None,
    ) -> None:
        if cursor:
            return await self._insert_known_versions(known_versions, cursor)
        else:
            async with self.db_pool.connection() as conn, conn.cursor() as cursor:
                result = await self._insert_known_versions(known_versions, cursor)
                await cursor.execute("commit;")
                return result

    async def _iter_known_versions(
        self,
        cursor: AsyncCursor,
        package_name: str | None = None,
        package_version: str | None = None,
    ) -> AsyncIterable[models.KnownVersion]:
        query = textwrap.dedent(
            f"""
                select
                    kv.known_version_id,
                    kv.package_name,
                    kv.package_version,
                    kv.package_release,
                    kv.date_discovered
                from {table_names.KNOWN_VERSIONS} kv
            """
        )

        params = []

        if package_name is not None:
            if not params:
                query += " where "
            else:
                query += " and "

            query += " kv.package_name = %s "
            params.append(package_name)

        if package_version is not None:
            if not params:
                query += " where "
            else:
                query += " and "

            query += " kv.package_version = %s "
            params.append(package_version)

        await cursor.execute(query, params)
        async for record in cursor:
            yield models.KnownVersion.from_dict(record)

    async def iter_known_versions(
        self,
        package_name: str | None = None,
        package_version: str | None = None,
        cursor: AsyncCursor | None = None,
    ) -> AsyncIterable[models.KnownVersion]:
        if cursor:
            async for record in self._iter_known_versions(
                cursor=cursor,
                package_name=package_name,
                package_version=package_version,
            ):
                yield record
        else:
            async with self.db_pool.connection() as conn, conn.cursor(
                row_factory=dict_row
            ) as cursor:
                async for record in self._iter_known_versions(
                    cursor=cursor,
                    package_name=package_name,
                    package_version=package_version,
                ):
                    yield record
