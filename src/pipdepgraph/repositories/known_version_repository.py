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

        PARAMS_PER_INSERT = 13
        for known_versions in itertools.batched(
            known_versions, constants.POSTGRES_MAX_QUERY_PARAMS // PARAMS_PER_INSERT
        ):
            query = f"""
            INSERT INTO {table_names.KNOWN_VERSIONS}
            (
                package_name, package_version, date_discovered,
                epoch, package_release, pre_0, pre_1, post, dev, "local",
                is_prerelease, is_postrelease, is_devrelease
            )
            VALUES
            """

            query += ",".join(
                " ( %s, %s, coalesce(%s, now()), %s, %s, %s, %s, %s, %s, %s, %s, %s, %s ) "
                for _ in range(len(known_versions))
            )

            query += """
            on conflict do update set
                epoch = EXCLUDED.epoch,
                package_release = EXCLUDED.package_release,
                pre_0 = EXCLUDED.pre_0,
                pre_1 = EXCLUDED.pre_1,
                post = EXCLUDED.post,
                dev = EXCLUDED.dev,
                "local" = EXCLUDED."local",
                is_prerelease = EXCLUDED.is_prerelease,
                is_postrelease = EXCLUDED.is_postrelease,
                is_devrelease = EXCLUDED.is_devrelease
            ;"""

            params = [None] * PARAMS_PER_INSERT * len(known_versions)
            offset = 0
            for kv in known_versions:
                params[offset + 0] = kv.package_name
                params[offset + 1] = kv.package_version
                params[offset + 2] = kv.date_discovered
                params[offset + 3] = kv.epoch
                params[offset + 4] = format_pg_integer_array(kv.package_release)
                params[offset + 5] = kv.pre[0] if kv.pre is not None else None
                params[offset + 6] = kv.pre[1] if kv.pre is not None else None
                params[offset + 7] = kv.post
                params[offset + 8] = kv.dev
                params[offset + 9] = kv.local
                params[offset + 10] = kv.is_prerelease
                params[offset + 11] = kv.is_postrelease
                params[offset + 12] = kv.is_devrelease

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
            date_discovered = %s,

            epoch = %s,
            package_release = %s,
            pre_0 = %s,
            pre_1 = %s,
            post = %s,
            dev = %s,
            "local" = %s,
            is_prerelease = %s,
            is_postrelease = %s,
            is_devrelease = %s
        WHERE
            known_version_id = %s
        ;"""

        params = (
            known_version.package_name,
            known_version.package_version,
            known_version.date_discovered,

            known_version.epoch,
            format_pg_integer_array(known_version.package_release),
            known_version.pre[0] if known_version.pre else None,
            known_version.pre[1] if known_version.pre else None,
            known_version.post,
            known_version.dev,
            known_version.local,
            known_version.is_prerelease,
            known_version.is_postrelease,
            known_version.is_devrelease,

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
    ) -> AsyncIterable[models.KnownVersion]:
        query = textwrap.dedent(
            f"""
                select
                    kv.known_version_id,
                    kv.package_name,
                    kv.package_version,
                    kv.date_discovered,
                    kv.epoch,
                    kv.package_release,
                    kv.pre_0,
                    kv.pre_1,
                    kv.post,
                    kv.dev,
                    kv."local",
                    kv.is_prerelease,
                    kv.is_postrelease,
                    kv.is_devrelease
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
    ) -> AsyncIterable[models.KnownVersion]:
        kwargs = dict(
            package_name=package_name,
            package_version=package_version,
            has_package_release=has_package_release,
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
