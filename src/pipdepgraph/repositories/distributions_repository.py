from typing import AsyncIterable
import itertools

from psycopg_pool import AsyncConnectionPool
from psycopg import AsyncCursor
from psycopg.rows import dict_row

from pipdepgraph import models, constants
from pipdepgraph.repositories import table_names


class DistributionsRepository:
    def __init__(self, db_pool: AsyncConnectionPool):
        self.db_pool = db_pool


    async def insert_distributions(
        self,
        distributions: list[models.Distribution],
        cursor: AsyncCursor | None = None,
        return_inserted: bool = False,
    ) -> list[models.Distribution]:
        """
        Inserts the list of distrubutions into the database. Inserts the records with
        "on conflict do nothing". If `return_inserted` is specified, returns the list
        of distributions that were actually inserted.
        """

        if not distributions:
            return []

        async def _insert_distributions(cursor: AsyncCursor) -> list[models.Distribution]:
            PARAMS_PER_INSERT = 8
            for distribution_batch in itertools.batched(
                distributions,
                constants.POSTGRES_MAX_QUERY_PARAMS // PARAMS_PER_INSERT,
            ):
                query = f"""
                insert into {table_names.DISTRIBUTIONS}
                (
                    version_id,
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

                query += ",".join(
                    "( %s, %s, %s, %s, %s, %s, %s, %s ) "
                    for _ in range(len(distribution_batch))
                )
                query += " on conflict do nothing "

                if return_inserted:
                    query += """
                    returning
                        distribution_id,
                        version_id,
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

                params = [None] * PARAMS_PER_INSERT * len(distribution_batch)

                offset = 0
                for dist in distribution_batch:
                    params[offset + 0] = dist.version_id
                    params[offset + 1] = dist.package_type
                    params[offset + 2] = dist.python_version
                    params[offset + 3] = dist.requires_python
                    params[offset + 4] = dist.upload_time
                    params[offset + 5] = dist.yanked
                    params[offset + 6] = dist.package_filename
                    params[offset + 7] = dist.package_url
                    offset += PARAMS_PER_INSERT

                await cursor.execute(query, params)
                if return_inserted:
                    rows = await cursor.fetchall()
                    return [models.Distribution(**row) for row in rows]
                else:
                    return []

        if cursor:
            return await _insert_distributions(cursor)
        else:
            async with self.db_pool.connection() as conn, conn.cursor(
                row_factory=dict_row
            ) as cursor:
                result = await _insert_distributions(cursor)
                await cursor.execute("commit;")
                return result


    async def update_distributions(
        self,
        distributions: list[models.Distribution],
        cursor: AsyncCursor | None = None,
    ):
        """
        Updates the list of distrubutions in the database. Currently
        only supports updating the "processed" and "metadata_file_size"
        properties.
        """

        if not distributions:
            return

        async def _update_distributions(cursor: AsyncCursor):

            query = f"""
            update {table_names.DISTRIBUTIONS}
            set
                processed = %s,
                metadata_file_size = coalesce(%s, metadata_file_size)
            where
                distribution_id = %s
            """

            params_seq = [
                (dist.processed, dist.metadata_file_size, dist.distribution_id)
                for dist in distributions
            ]

            await cursor.executemany(query, params_seq)

        if cursor:
            await _update_distributions(cursor)
        else:
            async with self.db_pool.connection() as conn, conn.cursor() as cursor:
                await _update_distributions(cursor)
                await cursor.execute("commit;")

    async def iter_distributions(
        self,
        processed: bool | None = None,
        package_type: str | None = None,
        package_name: str | models.PackageName | None = None,
    ) -> AsyncIterable[models.Distribution]:
        async with self.db_pool.connection() as conn, conn.cursor(
            row_factory=dict_row, name='iter_distributions'
        ) as cursor:
            query = f"""
            select
                dist.distribution_id,
                dist.version_id,
                dist.package_type,
                dist.python_version,
                dist.requires_python,
                dist.upload_time,
                dist.yanked,
                dist.package_filename,
                dist.package_url,
                dist.metadata_file_size,
                dist.processed
            from {table_names.DISTRIBUTIONS} dist
            {"" if package_name is None else f" left join {table_names.VERSIONS} version on version.version_id = dist.version_id "}
            {"" if package_name is None else f" left join {table_names.PACKAGE_NAMES} name on name.package_name = version.package_name "}
            """

            has_where = False
            params = []

            if package_name is not None:
                _package_name = (
                    package_name
                    if isinstance(package_name, str)
                    else package_name.package_name
                )
                if not has_where:
                    query += " where "
                    has_where = True
                else:
                    query += " and "
                query += " name.package_name = %s "
                params.append(_package_name)

            if processed is not None:
                if not has_where:
                    query += " where "
                    has_where = True
                else:
                    query += " and "
                query += " dist.processed = %s "
                params.append(processed)

            if package_type is not None:
                if not has_where:
                    query += " where "
                    has_where = True
                else:
                    query += " and "
                query += " dist.package_type = %s "
                params.append(package_type)

            await cursor.execute(query, params)
            async for record in cursor:
                yield models.Distribution.from_dict(record)
