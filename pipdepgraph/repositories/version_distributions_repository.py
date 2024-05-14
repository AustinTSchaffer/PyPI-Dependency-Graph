from typing import AsyncIterable
import textwrap
import itertools

from psycopg_pool import AsyncConnectionPool
from psycopg import AsyncCursor
from psycopg.rows import dict_row

from pipdepgraph import models, constants

TABLE_NAME = "pypi_packages.version_distributions"


class VersionDistributionRepository:
    def __init__(self, db_pool: AsyncConnectionPool):
        self.db_pool = db_pool

    async def _insert_version_distributions(
        self,
        version_distributions: list[models.VersionDistribution],
        cursor: AsyncCursor,
    ) -> None:
        if not version_distributions:
            return None

        PARAMS_PER_INSERT = 8
        for version_distributions in itertools.batched(
            version_distributions,
            constants.POSTGRES_MAX_QUERY_PARAMS // PARAMS_PER_INSERT,
        ):
            query = textwrap.dedent(
                f"""
                    insert into {TABLE_NAME}
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
            query += " on conflict do nothing; "

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

    async def insert_version_distributions(
        self,
        version_distributions: list[models.VersionDistribution],
        cursor: AsyncCursor | None = None,
    ):
        if cursor:
            await self._insert_version_distributions(version_distributions, cursor)
        else:
            async with self.db_pool.connection() as conn, conn.cursor() as cursor:
                await self._insert_version_distributions(version_distributions, cursor)
                await cursor.execute("commit;")

    async def _update_version_distributions(
        self,
        version_distributions: list[models.VersionDistribution],
        cursor: AsyncCursor,
    ):
        if not version_distributions:
            return

        query = textwrap.dedent(
            f"""
                update {TABLE_NAME}
                set
                    processed = %b,
                    metadata_file_size = coalesce(%d, metadata_file_size)
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
            await self._insert_version_distributions(version_distributions, cursor)
        else:
            async with self.db_pool.connection() as conn, conn.cursor() as cursor:
                await self._insert_version_distributions(version_distributions, cursor)
                await cursor.execute("commit;")

    async def iter_version_distributions(
        self, processed: bool | None = None
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
                    from {TABLE_NAME} vd
                """
            )

            params = []
            if processed is not None:
                if not params:
                    query += " where "
                else:
                    query += " and "
                query += " vd.processed = %b "
                params.append(processed)

            await cursor.execute(query, params)
            async for result in cursor:
                yield models.VersionDistribution(**result)
