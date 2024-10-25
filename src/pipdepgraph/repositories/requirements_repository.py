from typing import AsyncIterable
import itertools
import dataclasses

from psycopg_pool import AsyncConnectionPool
from psycopg import AsyncCursor
from psycopg.rows import dict_row

from pipdepgraph import models, constants
from pipdepgraph.repositories import table_names


@dataclasses.dataclass
class RequirementResult:
    package_name: models.PackageName
    version: models.Version
    distribution: models.Distribution
    requirement: models.Requirement


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
            PARAMS_PER_INSERT = 5
            for requirement_batch in itertools.batched(
                requirements,
                constants.POSTGRES_MAX_QUERY_PARAMS // PARAMS_PER_INSERT,
            ):
                query = f"""
                insert into {table_names.REQUIREMENTS}
                (
                    distribution_id,
                    extras,
                    dependency_name,
                    dependency_extras,
                    version_constraint
                )
                values
                """

                query += ",".join(
                    " ( %s, %s, %s, %s, %s ) " for _ in range(len(requirement_batch))
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
                    offset += PARAMS_PER_INSERT

                await cursor.execute(query, params)

        if cursor:
            await _insert_requirements(cursor)
        else:
            async with self.db_pool.connection() as conn, conn.cursor() as cursor:
                await _insert_requirements(cursor)
                await cursor.execute("commit;")

    async def iter_requirements(
        self,
        package_name: str | None = None,
        package_version: str | None = None,
        dist_package_type: str | None = None,
        dist_processed: bool | None = None,
        output_as_dict=False,
    ) -> AsyncIterable[RequirementResult | dict]:
        """
        Iterates over a list of requirements records, returning each
        requirement record, along with all of the 
        """

        async with (
            self.db_pool.connection() as conn,
            conn.cursor(row_factory=dict_row) as cursor,
        ):
            query = f"""
            select
                name.package_name      package_name,
                name.date_discovered   date_discovered,
                name.date_last_checked date_last_checked,

                version.version_id      version_id,
                version.package_version package_version,
                version.package_release package_release,
                version.date_discovered date_discovered,

                dist.distribution_id    distribution_id,
                dist.package_type       package_type,
                dist.python_version     python_version,
                dist.requires_python    requires_python,
                dist.upload_time        upload_time,
                dist.yanked             yanked,
                dist.package_filename   package_filename,
                dist.package_url        package_url,
                dist.metadata_file_size metadata_file_size,
                dist.processed          processed,

                req.extras             extras,
                req.dependency_name    dependency_name,
                req.dependency_extras  dependency_extras,
                req.version_constraint version_constraint

            from {table_names.PACKAGE_NAMES} name
            join {table_names.VERSIONS} version on version.package_name = name.package_name
            join {table_names.DISTRIBUTIONS} dist on dist.version_id = version.version_id
            join {table_names.REQUIREMENTS} req on req.distribution_id = dist.distribution_id
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

            await cursor.execute(query, params)
            async for record in cursor:
                yield (
                    record
                    if output_as_dict
                    else RequirementResult(
                        package_name=models.PackageName.from_dict(record),
                        version=models.Version.from_dict(record),
                        distribution=models.Distribution.from_dict(
                            record
                        ),
                        requirement=models.Requirement.from_dict(record),
                    )
                )
