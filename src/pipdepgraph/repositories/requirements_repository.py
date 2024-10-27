from typing import AsyncIterable
import itertools
import dataclasses

from psycopg_pool import AsyncConnectionPool
from psycopg import AsyncCursor
from psycopg.rows import dict_row

from pipdepgraph import models, constants
from pipdepgraph.repositories import table_names


class RequirementsRepository:
    def __init__(self, db_pool: AsyncConnectionPool):
        self.db_pool = db_pool

    async def insert_requirements(
        self,
        requirements: list[models.Requirement],
        cursor: AsyncCursor | None = None,
    ):
        """
        Inserts a list of requirement records into the database, batching them
        into chunks. Does nothing on conflict.
        """

        if not requirements:
            return

        async def _insert_requirements(cursor: AsyncCursor):
            PARAMS_PER_INSERT = 6
            for requirement_batch in itertools.batched(
                requirements,
                constants.POSTGRES_MAX_QUERY_PARAMS // PARAMS_PER_INSERT,
            ):
                query = f"""
                insert into {table_names.REQUIREMENTS}
                (
                    requirement_id,
                    distribution_id,
                    extras,
                    dependency_name,
                    dependency_extras,
                    version_constraint,
                    dependency_extras_arr
                )
                values
                """

                query += ",".join(
                    " ( gen_random_uuid(), %s, %s, %s, %s, %s, %s ) " for _ in range(len(requirement_batch))
                )
                query += " on conflict do nothing; "

                params = [None] * PARAMS_PER_INSERT * len(requirement_batch)
                offset = 0
                for req in requirement_batch:
                    params[offset + 0] = req.distribution_id
                    params[offset + 1] = req.extras
                    params[offset + 2] = req.dependency_name
                    params[offset + 3] = req.dependency_extras
                    params[offset + 4] = req.version_constraint
                    params[offset + 5] = req.dependency_extras_arr
                    offset += PARAMS_PER_INSERT

                await cursor.execute(query, params)

        if cursor:
            await _insert_requirements(cursor)
        else:
            async with self.db_pool.connection() as conn, conn.cursor() as cursor:
                await _insert_requirements(cursor)
                await cursor.execute("commit;")

    async def update_requirement(
        self,
        requirement: models.Requirement,
        cursor: AsyncCursor | None = None,
    ) -> None:
        async def _update_requirement(cursor: AsyncCursor):
            if requirement.requirement_id:
                sql = f"""
                update {table_names.REQUIREMENTS} set
                    dependency_extras_arr = %s
                where
                    requirement_id = %s
                ;"""

                params = (
                    requirement.dependency_extras_arr,
                    requirement.requirement_id,
                )

                await cursor.execute(sql, params)
            else:
                sql = f"""
                update {table_names.REQUIREMENTS} set
                    requirement_id = gen_random_uuid(),
                    dependency_extras_arr = %s,
                    extras = %s
                where
                    distribution_id = %s and
                    (extras = %s or (%s = '' and extras is null)) and
                    dependency_name = %s and
                    dependency_extras = %s
                ;"""

                params = (
                    requirement.dependency_extras_arr,
                    requirement.extras,
                    requirement.distribution_id,
                    requirement.extras, requirement.extras,
                    requirement.dependency_name,
                    requirement.dependency_extras,
                )

                await cursor.execute(sql, params)

        if cursor:
            await _update_requirement(cursor)
        else:
            async with self.db_pool.connection() as conn, conn.cursor() as cursor:
                await _update_requirement(cursor)
                await cursor.execute("commit;")

    async def iter_requirements(
        self,
        package_name: str | None = None,
        package_version: str | None = None,
        dist_package_type: str | None = None,
        dist_processed: bool | None = None,
        dist_id_hash_mod_filter: tuple[str, int, int] | None = None,
        dependency_extras_arr_is_none: bool = None,
    ) -> AsyncIterable[models.Requirement]:
        """
        Iterates over a list of requirements records, returning each
        requirement record.
        """

        async with (
            self.db_pool.connection() as conn,
            conn.cursor(row_factory=dict_row, name='iter_requirements') as cursor,
        ):
            query = f"""
            select
                req.requirement_id         requirement_id,
                req.distribution_id        distribution_id,
                req.extras                 extras,
                req.dependency_name        dependency_name,
                req.dependency_extras      dependency_extras,
                req.version_constraint     version_constraint,
                req.dependency_extras_arr  dependency_extras_arr
            FROM {table_names.REQUIREMENTS} req
            """

            has_where = False
            params = []

            if package_name is not None:
                if not has_where:
                    query += " where "
                    has_where = True
                else:
                    query += " and "
                query += " (version.package_name = %s) "
                params.append(package_name)

            if package_version is not None:
                if not has_where:
                    query += " where "
                    has_where = True
                else:
                    query += " and "
                query += " (version.package_version = %s) "
                params.append(package_version)

            if dist_package_type is not None:
                if not has_where:
                    query += " where "
                    has_where = True
                else:
                    query += " and "
                query += " (dist.package_type = %s) "
                params.append(dist_package_type)

            if dist_processed is not None:
                if not has_where:
                    query += " where "
                    has_where = True
                else:
                    query += " and "
                query += " (dist.processed = %s) "
                params.append(dist_processed)

            if dist_id_hash_mod_filter is not None:
                hash_alg, mod_base, mod_val = dist_id_hash_mod_filter
                if not has_where:
                    query += " where "
                    has_where = True
                else:
                    query += " and "
                query += " mod(get_byte(pypi_packages.digest(distribution_id::text, %s::text), 0), %s) = %s "
                params.extend((hash_alg, mod_base, mod_val))

            if dependency_extras_arr_is_none is not None:
                if not has_where:
                    query += " where "
                    has_where = True
                else:
                    query += " and "
                if dependency_extras_arr_is_none:
                    query += " dependency_extras_arr is null "
                else:
                    query += " dependency_extras_arr is not null "

            await cursor.execute(query, params)
            records = await cursor.fetchmany(size=50_000)
            while records:
                for record in records:
                    yield models.Requirement.from_dict(record)
                records = await cursor.fetchmany(size=50_000)
