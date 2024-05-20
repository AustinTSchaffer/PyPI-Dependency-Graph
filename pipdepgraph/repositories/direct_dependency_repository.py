from typing import AsyncIterable
import textwrap
import itertools
import dataclasses

from psycopg_pool import AsyncConnectionPool
from psycopg import AsyncCursor
from psycopg.rows import dict_row

from pipdepgraph import models, constants
from pipdepgraph.repositories import table_names


@dataclasses.dataclass
class DirectDependencyResult:
    known_package_name: models.KnownPackageName
    known_version: models.KnownVersion
    version_distribution: models.VersionDistribution
    direct_dependency: models.DirectDependency

class DirectDependencyRepository:
    def __init__(self, db_pool: AsyncConnectionPool):
        self.db_pool = db_pool

    async def _insert_direct_dependencies(
        self,
        direct_dependencies: list[models.DirectDependency],
        cursor: AsyncCursor,
    ):
        if not direct_dependencies:
            return

        PARAMS_PER_INSERT = 5
        for direct_dependencies in itertools.batched(
            direct_dependencies,
            constants.POSTGRES_MAX_QUERY_PARAMS // PARAMS_PER_INSERT,
        ):
            query = textwrap.dedent(
                f"""
                    insert into {table_names.DIRECT_DEPENDENCIES}
                    (
                        version_distribution_id,
                        extras,
                        dependency_name,
                        dependency_extras,
                        version_constraint
                    )
                    values
                """
            )

            query += ",".join(
                " ( %s, %s, %s, %s, %s ) " for _ in range(len(direct_dependencies))
            )
            query += " on conflict do nothing; "

            params = [None] * PARAMS_PER_INSERT * len(direct_dependencies)
            offset = 0
            for dd in direct_dependencies:
                params[offset + 0] = dd.version_distribution_id
                params[offset + 1] = dd.extras
                params[offset + 2] = dd.dependency_name
                params[offset + 3] = dd.dependency_extras
                params[offset + 4] = dd.version_constraint
                offset += PARAMS_PER_INSERT

            await cursor.execute(query, params)

    async def insert_direct_dependencies(
        self,
        direct_dependencies: list[models.DirectDependency],
        cursor: AsyncCursor | None = None,
    ):
        if cursor:
            await self._insert_direct_dependencies(direct_dependencies, cursor)
        else:
            async with self.db_pool.connection() as conn, conn.cursor() as cursor:
                await self._insert_direct_dependencies(direct_dependencies, cursor)
                await cursor.execute("commit;")


    async def iter_direct_dependencies(
        self,
        kv_package_name: str | None = None,
        kv_package_version: str | None = None,
        vd_package_type: str | None = None,
        vd_processed: bool | None = None,
        output_as_dict=False,
    ) -> AsyncIterable[DirectDependencyResult | dict]:
        """
        """

        async with (
            self.db_pool.connection() as conn,
            conn.cursor(row_factory=dict_row) as cursor,
        ):
            query = textwrap.dedent(
                f"""
                    select
                        kpn.package_name            package_name,
                        kpn.date_discovered         date_discovered,
                        kpn.date_last_checked       date_last_checked,
                        kv.known_version_id         known_version_id,

                        kv.known_version_id         known_version_id,
                        kv.package_version          package_version,
                        kv.package_release          package_release,
                        kv.date_discovered          date_discovered,

                        vd.version_distribution_id  version_distribution_id,
                        vd.package_type             package_type,
                        vd.python_version           python_version,
                        vd.requires_python          requires_python,
                        vd.upload_time              upload_time,
                        vd.yanked                   yanked,
                        vd.package_filename         package_filename,
                        vd.package_url              package_url,
                        vd.metadata_file_size       metadata_file_size,
                        vd.processed                processed,

                        dd.extras                   extras,
                        dd.dependency_name          dependency_name,
                        dd.dependency_extras        dependency_extras,
                        dd.version_constraint       version_constraint

                    from {table_names.KNOWN_PACKAGE_NAMES} kpn
                    join {table_names.KNOWN_VERSIONS} kv on kv.package_name = kpn.package_name
                    join {table_names.VERSION_DISTRIBUTIONS} vd on vd.known_version_id = kv.known_version_id
                    join {table_names.DIRECT_DEPENDENCIES} dd on dd.version_distribution_id = vd.version_distribution_id
                """
            )

            params = []
            if kv_package_name is not None:
                if not params:
                    query += " where "
                else:
                    query += " and "
                query += (
                    " (kv.package_name = %s) "
                )
                params.append(kv_package_name)

            if kv_package_version is not None:
                if not params:
                    query += " where "
                else:
                    query += " and "
                query += (
                    " (kv.package_version = %s) "
                )
                params.append(kv_package_version)

            if vd_package_type is not None:
                if not params:
                    query += " where "
                else:
                    query += " and "
                query += (
                    " (vd.package_type = %s) "
                )
                params.append(vd_package_type)

            if vd_processed is not None:
                if not params:
                    query += " where "
                else:
                    query += " and "
                query += (
                    " (vd.processed = %s) "
                )
                params.append(vd_processed)

            await cursor.execute(query, params)
            async for record in cursor:
                yield record if output_as_dict else DirectDependencyResult(
                    known_package_name=models.KnownPackageName.from_dict(record),
                    known_version=models.KnownVersion.from_dict(record),
                    version_distribution=models.VersionDistribution.from_dict(record),
                    direct_dependency=models.DirectDependency.from_dict(record),
                )
