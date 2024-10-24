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

    async def _insert_requirements(
        self,
        requirements: list[models.Requirement],
        cursor: AsyncCursor,
    ):
        if not requirements:
            return

        PARAMS_PER_INSERT = 5
        for requirements in itertools.batched(
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
                " ( %s, %s, %s, %s, %s ) " for _ in range(len(requirements))
            )
            query += " on conflict do nothing; "

            params = [None] * PARAMS_PER_INSERT * len(requirements)
            offset = 0
            for dd in requirements:
                params[offset + 0] = dd.distribution_id
                params[offset + 1] = dd.extras
                params[offset + 2] = dd.dependency_name
                params[offset + 3] = dd.dependency_extras
                params[offset + 4] = dd.version_constraint
                offset += PARAMS_PER_INSERT

            await cursor.execute(query, params)

    async def insert_requirements(
        self,
        requirements: list[models.Requirement],
        cursor: AsyncCursor | None = None,
    ):
        if cursor:
            await self._insert_requirements(requirements, cursor)
        else:
            async with self.db_pool.connection() as conn, conn.cursor() as cursor:
                await self._insert_requirements(requirements, cursor)
                await cursor.execute("commit;")

    async def iter_requirements(
        self,
        package_name: str | None = None,
        package_version: str | None = None,
        dist_package_type: str | None = None,
        dist_processed: bool | None = None,
        output_as_dict=False,
    ) -> AsyncIterable[RequirementResult | dict]:
        """ """

        async with (
            self.db_pool.connection() as conn,
            conn.cursor(row_factory=dict_row) as cursor,
        ):
            query = f"""
            select
                kpn.package_name        package_name,
                kpn.date_discovered     date_discovered,
                kpn.date_last_checked   date_last_checked,

                kv.version_id           version_id,
                kv.version_id           version_id,
                kv.package_version      package_version,
                kv.package_release      package_release,
                kv.date_discovered      date_discovered,

                vd.distribution_id      distribution_id,
                vd.package_type         package_type,
                vd.python_version       python_version,
                vd.requires_python      requires_python,
                vd.upload_time          upload_time,
                vd.yanked               yanked,
                vd.package_filename     package_filename,
                vd.package_url          package_url,
                vd.metadata_file_size   metadata_file_size,
                vd.processed            processed,

                dd.extras               extras,
                dd.dependency_name      dependency_name,
                dd.dependency_extras    dependency_extras,
                dd.version_constraint   version_constraint

            from {table_names.PACKAGE_NAMES} kpn
            join {table_names.VERSIONS} kv on kv.package_name = kpn.package_name
            join {table_names.DISTRIBUTIONS} vd on vd.version_id = kv.version_id
            join {table_names.REQUIREMENTS} dd on dd.distribution_id = vd.distribution_id
            """

            has_where = False
            params = []

            if package_name is not None:
                if not has_where:
                    query += " where "
                    has_where = True
                else:
                    query += " and "
                query += " (kv.package_name = %s) "
                params.append(package_name)

            if package_version is not None:
                if not has_where:
                    query += " where "
                    has_where = True
                else:
                    query += " and "
                query += " (kv.package_version = %s) "
                params.append(package_version)

            if dist_package_type is not None:
                if not has_where:
                    query += " where "
                    has_where = True
                else:
                    query += " and "
                query += " (vd.package_type = %s) "
                params.append(dist_package_type)

            if dist_processed is not None:
                if not has_where:
                    query += " where "
                    has_where = True
                else:
                    query += " and "
                query += " (vd.processed = %s) "
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
