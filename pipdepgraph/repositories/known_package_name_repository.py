from typing import AsyncIterable
import datetime
import itertools

from psycopg_pool import AsyncConnectionPool
from psycopg import AsyncCursor
from psycopg.rows import dict_row

from pipdepgraph import models, constants

TABLE_NAME = "pypi_packages.known_package_names"
DEFAULT_SELECT_BATCH_SIZE = 64


class KnownPackageNameRepository:
    def __init__(self, db_pool: AsyncConnectionPool):
        self.db_pool = db_pool

    async def _insert_known_package_names(
        self,
        package_names: list[models.KnownPackageName] | list[str],
        cursor: AsyncCursor,
    ):
        if not package_names:
            return

        MAX_PARAMS_PER_INSERT = 3

        for package_names in itertools.batched(
            package_names, constants.POSTGRES_MAX_QUERY_PARAMS // MAX_PARAMS_PER_INSERT
        ):
            query = f"insert into {TABLE_NAME} "
            params = []

            match type(package_names[0]):
                case models.KnownPackageName:
                    query += (
                        "(package_name, date_discovered, date_last_checked) values "
                    )
                    query += ",".join(
                        "(%s, coalesce(%s, now()), %s)"
                        for _ in range(len(package_names))
                    )

                    params = [None] * MAX_PARAMS_PER_INSERT * len(package_names)
                    offset = 0
                    for package_name in package_names:
                        params[offset + 0] = package_name.package_name
                        params[offset + 1] = package_name.date_discovered
                        params[offset + 2] = package_name.date_last_checked
                        offset += 3
                case str():
                    query += "(package_name) values "
                    query += ",".join("(%s)" for _ in range(len(package_names)))
                    params = package_names
                case t:
                    raise ValueError(f"invalid type for package_names: {t}")

            query += "on conflict do nothing;"
            await cursor.execute(query, params)

    async def insert_known_package_names(
        self,
        package_names: list[models.KnownPackageName | str],
        cursor: AsyncCursor | None = None,
    ):
        if cursor:
            await self._insert_known_package_names(package_names, cursor)
        else:
            async with self.db_pool.connection() as conn, conn.cursor() as cursor:
                await self._insert_known_package_names(package_names, cursor)
                await cursor.execute("commit;")

    async def _update_known_package_names(
        self, package_names: list[models.KnownPackageName], cursor: AsyncCursor
    ):
        if not package_names:
            return

        query = (
            f"update {TABLE_NAME} set date_last_checked = %s where package_name = %s;"
        )
        params_seq = [(pn.date_last_checked, pn.package_name) for pn in package_names]

        await cursor.executemany(query, params_seq)

    async def update_known_package_names(
        self,
        package_names: list[models.KnownPackageName],
        cursor: AsyncCursor | None = None,
    ):
        if cursor:
            await self._update_known_package_names(package_names, cursor)
        else:
            async with self.db_pool.connection() as conn, conn.cursor() as cursor:
                await self._update_known_package_names(package_names, cursor)
                await cursor.execute("commit;")

    async def iter_known_package_names(
        self, date_last_checked_before: datetime.datetime | None = None
    ) -> AsyncIterable[models.KnownPackageName]:
        async with (
            self.db_pool.connection() as conn,
            conn.cursor(row_factory=dict_row) as cursor,
        ):
            query = f"select kpn.package_name, kpn.date_discovered, kpn.date_last_checked from {TABLE_NAME} kpn"

            params = []
            if date_last_checked_before is not None:
                if not params:
                    query += " where "
                else:
                    query += " and "
                query += " kpn.date_last_checked < %s "
                params.append(date_last_checked_before)

            await cursor.execute(query, params)
            async for record in cursor:
                yield models.KnownPackageName(**record)
