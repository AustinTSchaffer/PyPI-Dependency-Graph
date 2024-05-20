from typing import AsyncIterable
import textwrap
import itertools

from psycopg_pool import AsyncConnectionPool
from psycopg import AsyncCursor
from psycopg.rows import dict_row

from pipdepgraph import models, constants
from pipdepgraph.repositories import table_names


class VersionDistributionRepository:
    def __init__(self, db_pool: AsyncConnectionPool):
        self.db_pool = db_pool

    async def _insert_version_distributions(
        self,
        version_distributions: list[models.VersionDistribution],
        cursor: AsyncCursor,
        return_inserted: bool = False,
    ) -> list[models.VersionDistribution]:
        if not version_distributions:
            return []

        PARAMS_PER_INSERT = 8
        for version_distributions in itertools.batched(
            version_distributions,
            constants.POSTGRES_MAX_QUERY_PARAMS // PARAMS_PER_INSERT,
        ):
            query = textwrap.dedent(
                f"""
                    insert into {table_names.VERSION_DISTRIBUTIONS}
                    (
                        known_version_id,
                        package_type,
                        python_version,
                        requires_python,
                        upload_time,
                        yanked,
                        package_filename,
                        package_url
                    )
                    values
                """
            )

            query += ",".join(
                "( %s, %s, %s, %s, %s, %s, %s, %s ) "
                for _ in range(len(version_distributions))
            )
            query += " on conflict do nothing "

            if return_inserted:
                query += textwrap.dedent(
                    """
                        returning
                            version_distribution_id,
                            known_version_id,
                            package_type,
                            python_version,
                            requires_python,
                            upload_time,
                            yanked,
                            package_filename,
                            package_url,
                            processed,
                            metadata_file_size
                    """
                )

            params = [None] * PARAMS_PER_INSERT * len(version_distributions)

            offset = 0
            for vd in version_distributions:
                params[offset + 0] = vd.known_version_id
                params[offset + 1] = vd.package_type
                params[offset + 2] = vd.python_version
                params[offset + 3] = vd.requires_python
                params[offset + 4] = vd.upload_time
                params[offset + 5] = vd.yanked
                params[offset + 6] = vd.package_filename
                params[offset + 7] = vd.package_url
                offset += PARAMS_PER_INSERT

            await cursor.execute(query, params)
            if return_inserted:
                rows = await cursor.fetchall()
                return [models.VersionDistribution(**row) for row in rows]
            else:
                return []

    async def insert_version_distributions(
        self,
        version_distributions: list[models.VersionDistribution],
        cursor: AsyncCursor | None = None,
        return_inserted: bool = False,
    ) -> list[models.VersionDistribution]:
        if cursor:
            return await self._insert_version_distributions(
                version_distributions, cursor, return_inserted=return_inserted
            )
        else:
            async with self.db_pool.connection() as conn, conn.cursor(
                row_factory=dict_row
            ) as cursor:
                result = await self._insert_version_distributions(
                    version_distributions, cursor, return_inserted=return_inserted
                )
                await cursor.execute("commit;")
                return result

    async def _update_version_distributions(
        self,
        version_distributions: list[models.VersionDistribution],
        cursor: AsyncCursor,
    ):
        if not version_distributions:
            return

        query = textwrap.dedent(
            f"""
                update {table_names.VERSION_DISTRIBUTIONS}
                set
                    processed = %s,
                    metadata_file_size = coalesce(%s, metadata_file_size)
                where
                    version_distribution_id = %s
            """
        )

        params_seq = [
            (vd.processed, vd.metadata_file_size, vd.version_distribution_id)
            for vd in version_distributions
        ]

        await cursor.executemany(query, params_seq)

    async def update_version_distributions(
        self,
        version_distributions: list[models.VersionDistribution],
        cursor: AsyncCursor | None = None,
    ):
        if cursor:
            await self._update_version_distributions(version_distributions, cursor)
        else:
            async with self.db_pool.connection() as conn, conn.cursor() as cursor:
                await self._update_version_distributions(version_distributions, cursor)
                await cursor.execute("commit;")

    async def iter_version_distributions(
        self,
        processed: bool | None = None,
        package_name: str | models.KnownPackageName | None = None,
    ) -> AsyncIterable[models.VersionDistribution]:
        async with self.db_pool.connection() as conn, conn.cursor(
            row_factory=dict_row
        ) as cursor:
            query = textwrap.dedent(
                f"""
                    select
                        vd.version_distribution_id,
                        vd.known_version_id,
                        vd.package_type,
                        vd.python_version,
                        vd.requires_python,
                        vd.upload_time,
                        vd.yanked,
                        vd.package_filename,
                        vd.package_url,
                        vd.metadata_file_size,
                        vd.processed
                    from {table_names.VERSION_DISTRIBUTIONS} vd
                    {"" if package_name is None else f" left join {table_names.KNOWN_VERSIONS} kv on kv.known_version_id = vd.known_version_id "}
                    {"" if package_name is None else f" left join {table_names.KNOWN_PACKAGE_NAMES} kpn on kpn.package_name = kv.package_name "}
                """
            )

            params = []
            if package_name is not None:
                _package_name = (
                    package_name
                    if isinstance(package_name, str)
                    else package_name.package_name
                )
                if not params:
                    query += " where "
                else:
                    query += " and "
                query += " kpn.package_name = %s "
                params.append(_package_name)

            if processed is not None:
                if not params:
                    query += " where "
                else:
                    query += " and "
                query += " vd.processed = %s "
                params.append(processed)

            await cursor.execute(query, params)
            async for result in cursor:
                yield models.VersionDistribution(**result)
