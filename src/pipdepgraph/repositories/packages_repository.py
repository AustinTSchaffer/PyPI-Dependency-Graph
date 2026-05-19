from typing import Iterator, List
import datetime
import itertools

import msgspec
import packaging.utils
from psycopg_pool import ConnectionPool
from psycopg import Cursor
from psycopg.rows import dict_row

from pipdepgraph import models, constants
from pipdepgraph.repositories import table_names


class PackagesRepository:
    def __init__(self, db_pool: ConnectionPool):
        self.db_pool = db_pool

    def insert_packages(
        self,
        packages: list[models.Package] | list[str],
        cursor: Cursor | None = None,
        return_inserted: bool = False,
    ) -> list[models.Package]:
        """
        Inserts a list of packages into the database, with the setting
        "on conflict do nothing". If `return_inserted` is specified, returns
        the list of packages that were actually inserted.
        """

        if not packages:
            return []

        def _insert_packages(cursor: Cursor) -> list[models.Package]:
            output = []
            MAX_PARAMS_PER_INSERT = 3

            for package_batch in itertools.batched(
                packages, constants.POSTGRES_MAX_QUERY_PARAMS // MAX_PARAMS_PER_INSERT
            ):
                query = f"insert into {table_names.PACKAGES} "
                params = []

                if isinstance(package_batch[0], models.Package):
                    query += " (name, date_discovered, date_last_checked) values "
                    query += ",".join(
                        "(%s, coalesce(%s, now()), %s)" for _ in range(len(package_batch))
                    )

                    params = [None] * MAX_PARAMS_PER_INSERT * len(package_batch)
                    offset = 0
                    for package in package_batch:
                        params[offset + 0] = package.name
                        params[offset + 1] = package.date_discovered
                        params[offset + 2] = package.date_last_checked
                        offset += 3
                elif isinstance(package_batch[0], str):
                    query += " (name) values "
                    query += ",".join("(%s)" for _ in range(len(package_batch)))
                    params = package_batch
                else:
                    raise ValueError(f"invalid type for package: {package_batch[0]}")

                query += " on conflict do nothing "
                if return_inserted:
                    query += " returning name, date_discovered, date_last_checked "

                cursor.execute(query, params)

                if return_inserted:
                    rows = cursor.fetchall()
                    output.extend(msgspec.convert(r, models.Package) for r in rows)

            return output

        if cursor:
            return _insert_packages(cursor)
        else:
            with (
                self.db_pool.connection() as conn,
                conn.cursor(row_factory=dict_row) as cursor,
            ):
                result = _insert_packages(cursor)
                cursor.execute("commit;")
                return result


    def update_packages(
        self,
        packages: list[models.Package],
        cursor: Cursor | None = None,
    ):
        """
        Updates the list of packages in the database. This is essentially just a
        "touch" command, only supports updating the "date_last_checked" property.
        """

        if not packages:
            return

        def _update_package_names(cursor: Cursor):
            query = f"update {table_names.PACKAGES} set date_last_checked = %s where package_name = %s;"
            params_seq = [(pn.date_last_checked, pn.name) for pn in packages]
            cursor.executemany(query, params_seq)

        if cursor:
            _update_package_names(cursor)
        else:
            with self.db_pool.connection() as conn, conn.cursor() as cursor:
                _update_package_names(cursor)
                cursor.execute("commit;")

    def get_package(
        self, package: str | models.Package
    ) -> models.Package | None:
        """
        Retrieves a package record from the database, if it exists.
        Canonicalizes the name before retrieval.
        """

        _package = (
            package if isinstance(package, str) else package.name
        )
        _package = packaging.utils.canonicalize_name(_package)

        params = [_package]
        query = f"""
        select
            p.name,
            p.date_discovered,
            p.date_last_checked
        from {table_names.PACKAGES} p
        where p.name = %s
        """

        with (
            self.db_pool.connection() as conn,
            conn.cursor(row_factory=dict_row) as cursor,
        ):
            cursor.execute(query, params)
            result = cursor.fetchone()
            return (
                None
                if not result
                else models.Package(
                    name=result["name"],
                    date_discovered=result["date_discovered"],
                    date_last_checked=result["date_last_checked"],
                )
            )

    def iter_packages(
        self, date_last_checked_before: datetime.datetime | None = None
    ) -> Iterator[models.Package]:
        with (
            self.db_pool.connection() as conn,
            conn.cursor(row_factory=dict_row, name='iter_package_names') as cursor,
        ):
            query = f"select p.name, p.date_discovered, p.date_last_checked from {table_names.PACKAGES} p"

            has_where = False
            params = []

            if date_last_checked_before is not None:
                if not has_where:
                    query += " where "
                    has_where = True
                else:
                    query += " and "
                query += (
                    " (p.date_last_checked is null or p.date_last_checked < %s) "
                )
                params.append(date_last_checked_before)

            cursor.execute(query, params)
            records = cursor.fetchmany(size=constants.PACKAGES_REPO_ITER_BATCH_SIZE)
            while records:
                for record in records:
                    yield msgspec.convert(record, models.Package)
                records = cursor.fetchmany(size=constants.PACKAGES_REPO_ITER_BATCH_SIZE)

    def _propagate_dependencies(self, cursor: Cursor):
        query = f"""
            insert into {table_names.PACKAGES} (name)
            select distinct dependency_name from {table_names.REQUIREMENTS}
            on conflict do nothing;
        """

        cursor.execute(query)

    def propagate_dependencies(self, cursor: Cursor | None = None):
        if cursor:
            self._propagate_dependencies(cursor)
        else:
            with self.db_pool.connection() as conn, conn.cursor() as cursor:
                self._propagate_dependencies(cursor)
                cursor.execute("commit;")
