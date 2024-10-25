from typing import AsyncIterable
import itertools

from psycopg_pool import AsyncConnectionPool
from psycopg import AsyncCursor
from psycopg.rows import dict_row

from pipdepgraph import models, constants
from pipdepgraph.repositories import table_names


def format_pg_integer_array(array: tuple[int | None, ...]) -> str:
    """
    Formats a postgres-compatible array of bigints. If empty array or None, returns
    `"{}"`.
    """

    vals = [
        "null" if val is None else str(val)
        for val in array
    ]

    return "{" + ",".join(vals) + "}"


class VersionsRepository:
    def __init__(self, db_pool: AsyncConnectionPool):
        self.db_pool = db_pool

    async def insert_versions(
        self,
        versions: list[models.Version],
        cursor: AsyncCursor | None = None,
    ) -> None:
        """
        Inserts the specified version records into the database, using
        all of the fields from `versions` except for the `version_id`. Performs an
        "on conflict do update" if the version record already exists based on the
        table's name/version unique constraint.
        """

        if not versions:
            return None

        async def _insert_versions(cursor: AsyncCursor) -> None:
            PARAMS_PER_INSERT = 13
            for version_batch in itertools.batched(
                versions, constants.POSTGRES_MAX_QUERY_PARAMS // PARAMS_PER_INSERT
            ):
                query = f"""
                INSERT INTO {table_names.VERSIONS}
                (
                    package_name, package_version, date_discovered,
                    epoch, package_release, pre_0, pre_1, post, dev, "local",
                    is_prerelease, is_postrelease, is_devrelease
                )
                VALUES
                """

                query += ",".join(
                    " ( %s, %s, coalesce(%s, now()), %s, %s, %s, %s, %s, %s, %s, %s, %s, %s ) "
                    for _ in range(len(version_batch))
                )

                query += """
                on conflict (package_name, package_version) do update set
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

                params = [None] * PARAMS_PER_INSERT * len(version_batch)
                offset = 0
                for version in version_batch:
                    params[offset + 0] = version.package_name
                    params[offset + 1] = version.package_version
                    params[offset + 2] = version.date_discovered
                    params[offset + 3] = version.epoch
                    params[offset + 4] = (
                        format_pg_integer_array(version.package_release)
                        if version.package_release is not None
                        else None
                    )
                    params[offset + 5] = version.pre[0] if version.pre is not None else None
                    params[offset + 6] = version.pre[1] if version.pre is not None else None
                    params[offset + 7] = version.post
                    params[offset + 8] = version.dev
                    params[offset + 9] = version.local
                    params[offset + 10] = version.is_prerelease
                    params[offset + 11] = version.is_postrelease
                    params[offset + 12] = version.is_devrelease

                    offset += PARAMS_PER_INSERT

                await cursor.execute(query, params)

        if cursor:
            return await _insert_versions(cursor)
        else:
            async with self.db_pool.connection() as conn, conn.cursor() as cursor:
                result = await _insert_versions(cursor)
                await cursor.execute("commit;")
                return result


    async def update_version(
        self,
        version: models.Version,
        cursor: AsyncCursor | None = None,
    ) -> None:
        """
        Updates the specified version record in the database, using
        all of the fields from `version`. Raises an error if the
        `version` object doesn't have a `version_id`.
        """

        if not version.version_id:
            raise ValueError("Missing version_id")

        async def _update_version(cursor: AsyncCursor) -> None:
            query = f"""
            UPDATE {table_names.VERSIONS}
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
                version_id = %s
            ;"""

            params = (
                version.package_name,
                version.package_version,
                version.date_discovered,
                version.epoch,
                (
                    format_pg_integer_array(version.package_release)
                    if version.package_release is not None
                    else None
                ),
                version.pre[0] if version.pre else None,
                version.pre[1] if version.pre else None,
                version.post,
                version.dev,
                version.local,
                version.is_prerelease,
                version.is_postrelease,
                version.is_devrelease,
                version.version_id,
            )

            await cursor.execute(query, params)

        if cursor:
            return await _update_version(cursor)
        else:
            async with self.db_pool.connection() as conn, conn.cursor() as cursor:
                result = await _update_version(cursor)
                await cursor.execute("commit;")
                return result

    async def iter_versions(
        self,
        *,
        cursor: AsyncCursor | None = None,
        package_name: str | None = None,
        package_version: str | None = None,
    ) -> AsyncIterable[models.Version]:
        """
        Iterates over all version records matching the specified optional parameters.
        By default, iterates over all version records.

        - `package_name`: Filter version records by an exact package name match. Does not
          canonicalize the package name.
        - `package_version`: Filter version records by an exact version string match. Does
          not attempt to validate/parse the version string.
        - `hasn_null_package_release`: Filter version records by whether they have a package
          release          
        """

        async def _iter_versions(cursor: AsyncCursor) -> AsyncIterable[models.Version]:
            query = f"""
            select
                kv.version_id,
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
            from {table_names.VERSIONS} kv
            """

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

            await cursor.execute(query, params)
            async for record in cursor:
                yield models.Version.from_dict(record)

        if cursor:
            async for record in _iter_versions(cursor):
                yield record
        else:
            async with (
                self.db_pool.connection() as conn,
                conn.cursor(row_factory=dict_row) as local_cursor,
            ):
                async for record in _iter_versions(local_cursor):
                    yield record
