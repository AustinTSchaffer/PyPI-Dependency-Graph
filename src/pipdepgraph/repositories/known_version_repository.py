from typing import AsyncIterable
import textwrap
import itertools

from psycopg_pool import AsyncConnectionPool
from psycopg import AsyncCursor
from psycopg.rows import dict_row

from pipdepgraph import models, constants
from pipdepgraph.repositories import table_names


def format_pg_integer_array(array: tuple[int, ...] | None) -> str:
    """
    Formats a postgres-compatible array of bigints. If empty array or None, returns
    `"{}"`.
    """
    return "{" + ",".join(map(str, array or [])) + "}"


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
            query = f"""
            INSERT INTO {table_names.KNOWN_VERSIONS}
            (package_name, package_version, package_release, package_release_numeric, date_discovered)
            VALUES
            """

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
                params[offset + 2] = format_pg_integer_array(kv.package_release)
                params[offset + 3] = (
                    format_pg_integer_array(kv.package_release_numeric)
                    if kv.package_release_numeric
                    else None
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

    async def _update_known_version(
        self, known_version: models.KnownVersion, cursor: AsyncCursor
    ) -> None:

        if not known_version.known_version_id:
            raise ValueError("Missing known_version_id")

        query = f"""
        UPDATE {table_names.KNOWN_VERSIONS}
        SET
            package_name = %s,
            package_version = %s,
            package_release = %s,
            package_release_numeric = %s,
            date_discovered = %s
        WHERE
            known_version_id = %s
        ;"""

        params = (
            known_version.package_name,
            known_version.package_version,
            format_pg_integer_array(known_version.package_release),
            format_pg_integer_array(known_version.package_release_numeric),
            known_version.date_discovered,
            known_version.known_version_id,
        )

        await cursor.execute(query, params)

    async def update_known_version(
        self,
        known_version: models.KnownVersion,
        cursor: AsyncCursor | None = None,
    ) -> None:
        if cursor:
            return await self._update_known_version(known_version, cursor)
        else:
            async with self.db_pool.connection() as conn, conn.cursor() as cursor:
                result = await self._update_known_version(known_version, cursor)
                await cursor.execute("commit;")
                return result

    async def _iter_known_versions(
        self,
        cursor: AsyncCursor,
        package_name: str | None = None,
        package_version: str | None = None,
        has_package_release: bool | None = None,
        has_package_release_numeric: bool | None = None,
    ) -> AsyncIterable[models.KnownVersion]:
        query = textwrap.dedent(
            f"""
                select
                    kv.known_version_id,
                    kv.package_name,
                    kv.package_version,
                    kv.package_release,
                    kv.package_release_numeric,
                    kv.date_discovered
                from {table_names.KNOWN_VERSIONS} kv
            """
        )

        has_where = False
        params = []

        if package_name is not None:
            if not has_where:
                query += " where "
                has_where = True
            else:
                query += " and "

            query += " kv.package_name = %s "
            params.append(package_name)

        if package_version is not None:
            if not has_where:
                query += " where "
                has_where = True
            else:
                query += " and "

            query += " kv.package_version = %s "
            params.append(package_version)

        if has_package_release is not None:
            if not has_where:
                query += " where "
                has_where = True
            else:
                query += " and "

            if has_package_release:
                query += " kv.package_release != '{}' "
            else:
                query += " kv.package_release = '{}' "

        if has_package_release_numeric is not None:
            if not has_where:
                query += " where "
                has_where = True
            else:
                query += " and "

            if has_package_release_numeric:
                query += " kv.package_release_numeric is not null "
            else:
                query += " kv.package_release_numeric is null "

        await cursor.execute(query, params)
        async for record in cursor:
            yield models.KnownVersion.from_dict(record)

    async def iter_known_versions(
        self,
        *,
        cursor: AsyncCursor | None = None,
        package_name: str | None = None,
        package_version: str | None = None,
        has_package_release: bool | None = None,
        has_package_release_numeric: bool | None = None,
    ) -> AsyncIterable[models.KnownVersion]:
        kwargs = dict(
            package_name=package_name,
            package_version=package_version,
            has_package_release=has_package_release,
            has_package_release_numeric=has_package_release_numeric,
        )

        if cursor:
            async for record in self._iter_known_versions(
                cursor=cursor,
                **kwargs,
            ):
                yield record
        else:
            async with (
                self.db_pool.connection() as conn,
                conn.cursor(row_factory=dict_row) as local_cursor,
            ):
                async for record in self._iter_known_versions(
                    cursor=local_cursor,
                    **kwargs,
                ):
                    yield record
