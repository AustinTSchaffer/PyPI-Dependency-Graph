from typing import AsyncIterable, List
import datetime
import itertools

import packaging.utils
from psycopg_pool import AsyncConnectionPool
from psycopg import AsyncCursor
from psycopg.rows import dict_row

from pipdepgraph import models, constants
from pipdepgraph.repositories import table_names


class PackageNamesRepository:
    def __init__(self, db_pool: AsyncConnectionPool):
        self.db_pool = db_pool

    async def insert_package_names(
        self,
        package_names: list[models.PackageName] | list[str],
        cursor: AsyncCursor | None = None,
        return_inserted: bool = False,
    ) -> list[models.PackageName]:
        """
        Inserts a list of package names into the database, with the setting
        "on conflict do nothing". If `return_inserted` is specified, returns
        the list of package names that were actually inserted.
        """

        if not package_names:
            return []

        async def _insert_package_names(cursor: AsyncCursor) -> list[models.PackageName]:
            output = []
            MAX_PARAMS_PER_INSERT = 3

            for package_name_batch in itertools.batched(
                package_names, constants.POSTGRES_MAX_QUERY_PARAMS // MAX_PARAMS_PER_INSERT
            ):
                query = f"insert into {table_names.PACKAGE_NAMES} "
                params = []

                if isinstance(package_name_batch[0], models.PackageName):
                    query += " (package_name, date_discovered, date_last_checked) values "
                    query += ",".join(
                        "(%s, coalesce(%s, now()), %s)" for _ in range(len(package_name_batch))
                    )

                    params = [None] * MAX_PARAMS_PER_INSERT * len(package_name_batch)
                    offset = 0
                    for package_name in package_name_batch:
                        params[offset + 0] = package_name.package_name
                        params[offset + 1] = package_name.date_discovered
                        params[offset + 2] = package_name.date_last_checked
                        offset += 3
                elif isinstance(package_name_batch[0], str):
                    query += " (package_name) values "
                    query += ",".join("(%s)" for _ in range(len(package_name_batch)))
                    params = package_name_batch
                else:
                    raise ValueError(f"invalid type for package_names: {package_name_batch[0]}")

                query += " on conflict do nothing "
                if return_inserted:
                    query += " returning package_name, date_discovered, date_last_checked "

                await cursor.execute(query, params)

                if return_inserted:
                    rows = await cursor.fetchall()
                    output.extend(map(models.PackageName.from_dict, rows))

            return output

        if cursor:
            return await _insert_package_names(cursor)
        else:
            async with (
                self.db_pool.connection() as conn,
                conn.cursor(row_factory=dict_row) as cursor,
            ):
                result = await _insert_package_names(cursor)
                await cursor.execute("commit;")
                return result


    async def update_package_names(
        self,
        package_names: list[models.PackageName],
        cursor: AsyncCursor | None = None,
    ):
        """
        Updates the list of package names in the database. This is essentially just a
        "touch" command, only supports updating the "date_last_checked" property.
        """

        if not package_names:
            return

        async def _update_package_names(cursor: AsyncCursor):
            query = f"update {table_names.PACKAGE_NAMES} set date_last_checked = %s where package_name = %s;"
            params_seq = [(pn.date_last_checked, pn.package_name) for pn in package_names]
            await cursor.executemany(query, params_seq)

        if cursor:
            await _update_package_names(cursor)
        else:
            async with self.db_pool.connection() as conn, conn.cursor() as cursor:
                await _update_package_names(cursor)
                await cursor.execute("commit;")

    async def get_package_name(
        self, package_name: str | models.PackageName
    ) -> models.PackageName | None:
        """
        Retrieves a package name record from the database if it exists.
        Canonicalizes the name before retrieval.
        """

        _package_name = (
            package_name if isinstance(package_name, str) else package_name.package_name
        )
        _package_name = packaging.utils.canonicalize_name(_package_name)

        params = [_package_name]
        query = f"""
        select
            kpn.package_name,
            kpn.date_discovered,
            kpn.date_last_checked
        from {table_names.PACKAGE_NAMES} kpn
        where kpn.package_name = %s
        """

        async with (
            self.db_pool.connection() as conn,
            conn.cursor(row_factory=dict_row) as cursor,
        ):
            await cursor.execute(query, params)
            results = await cursor.fetchall()
            return (
                None
                if not results
                else models.PackageName(
                    package_name=results[0]["package_name"],
                    date_discovered=results[0]["date_discovered"],
                    date_last_checked=results[0]["date_last_checked"],
                )
            )

    async def iter_package_names(
        self, date_last_checked_before: datetime.datetime | None = None
    ) -> AsyncIterable[models.PackageName]:
        async with (
            self.db_pool.connection() as conn,
            conn.cursor(row_factory=dict_row, name='iter_package_names') as cursor,
        ):
            query = f"select kpn.package_name, kpn.date_discovered, kpn.date_last_checked from {table_names.PACKAGE_NAMES} kpn"

            has_where = False
            params = []

            if date_last_checked_before is not None:
                if not has_where:
                    query += " where "
                    has_where = True
                else:
                    query += " and "
                query += (
                    " (kpn.date_last_checked is null or kpn.date_last_checked < %s) "
                )
                params.append(date_last_checked_before)

            await cursor.execute(query, params)
            async for record in cursor:
                yield models.PackageName.from_dict(record)

    async def _propagate_dependency_names(self, cursor: AsyncCursor):
        query = f"""
            insert into {table_names.PACKAGE_NAMES} (package_name)
            select distinct dependency_name from {table_names.REQUIREMENTS}
            on conflict do nothing;
        """

        await cursor.execute(query)

    async def propagate_dependency_names(self, cursor: AsyncCursor | None = None):
        if cursor:
            await self._propagate_dependency_names(cursor)
        else:
            async with self.db_pool.connection() as conn, conn.cursor() as cursor:
                await self._propagate_dependency_names(cursor)
                await cursor.execute("commit;")
