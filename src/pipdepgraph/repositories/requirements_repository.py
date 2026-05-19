from typing import Iterator
import itertools

import msgspec
from psycopg_pool import ConnectionPool
from psycopg import Cursor
from psycopg.rows import dict_row

from pipdepgraph import models, constants
from pipdepgraph.repositories import table_names


class RequirementsRepository:
    def __init__(self, db_pool: ConnectionPool):
        self.db_pool = db_pool

    def insert_requirements(
        self,
        requirements: list[models.Requirement],
        cursor: Cursor | None = None,
    ):
        """
        Inserts a list of requirement records into the database, batching them
        into chunks. Does nothing on conflict.
        """

        if not requirements:
            return

        def _insert_requirements(cursor: Cursor):
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
                    marker,
                    dependency_name,
                    version_constraint,
                    dependency_extras,
                    parsable
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
                    params[offset + 1] = req.marker
                    params[offset + 2] = req.dependency_name
                    params[offset + 3] = req.version_constraint
                    params[offset + 4] = req.dependency_extras
                    params[offset + 5] = req.parsable
                    offset += PARAMS_PER_INSERT

                cursor.execute(query, params)

        if cursor:
            _insert_requirements(cursor)
        else:
            with self.db_pool.connection() as conn, conn.cursor() as cursor:
                _insert_requirements(cursor)
                cursor.execute("commit;")


    def delete_requirements(
        self,
        *,
        distribution_id: str,
        cursor: Cursor | None = None,
    ):
        """
        Deletes requirements that have the specified `distribution_id`.
        """

        if not distribution_id:
            return

        def _delete_requirements(cursor: Cursor):
            query = f"""
            delete from {table_names.REQUIREMENTS}
            where distribution_id = %s;
            """
            cursor.execute(query, [distribution_id])

        if cursor:
            _delete_requirements(cursor)
        else:
            with self.db_pool.connection() as conn, conn.cursor() as cursor:
                _delete_requirements(cursor)
                cursor.execute("commit;")


    def iter_requirements(
        self,
        package_name: str | None = None,
        package_version: str | None = None,
        dist_package_type: str | None = None,
        dist_processed: bool | None = None,
        dist_id_hash_mod_filter: tuple[str, int, int] | None = None,
        dependency_name: str | None = None,
        dependency_extras_is_none: bool = None,
    ) -> Iterator[models.Requirement]:
        """
        Iterates over a list of requirements records, returning each
        requirement record.
        """

        with (
            self.db_pool.connection() as conn,
            conn.cursor(row_factory=dict_row, name='iter_requirements') as cursor,
        ):
            query = f"""
            select
                req.requirement_id         requirement_id,
                req.distribution_id        distribution_id,
                req.marker                 marker,
                req.dependency_name        dependency_name,
                req.dependency_extras      dependency_extras,
                req.version_constraint     version_constraint
            from {table_names.REQUIREMENTS} req {
                f" join {table_names.DISTRIBUTIONS} dist on req.distribution_id = dist.distribution_id "
                if any(filter(lambda v: v is not None, [package_name, package_version, dist_processed, dist_package_type])) else
                ""
            } {
                f" join {table_names.VERSIONS} version on version.version_id = dist.version_id "
                if any(filter(lambda v: v is not None, [package_name, package_version])) else
                ""
            } """

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
                query += " mod(get_byte(pypi_packages.digest(req.distribution_id::text, %s::text), 0), %s) = %s "
                params.extend((hash_alg, mod_base, mod_val))

            if dependency_extras_is_none is not None:
                if not has_where:
                    query += " where "
                    has_where = True
                else:
                    query += " and "
                if dependency_extras_is_none:
                    query += " req.dependency_extras is null "
                else:
                    query += " req.dependency_extras is not null "

            if dependency_name is not None:
                if not has_where:
                    query += " where "
                    has_where = True
                else:
                    query += " and "

                query += " req.dependency_name = %s "
                params.append(dependency_name)

            cursor.execute(query, params)
            records = cursor.fetchmany(size=constants.REQUIREMENTS_REPO_ITER_BATCH_SIZE)
            while records:
                for record in records:
                    yield msgspec.convert(record, models.Requirement)
                records = cursor.fetchmany(size=constants.REQUIREMENTS_REPO_ITER_BATCH_SIZE)
