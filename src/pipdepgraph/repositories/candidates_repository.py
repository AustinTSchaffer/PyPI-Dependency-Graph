import itertools

from psycopg_pool import ConnectionPool
from psycopg import Cursor
from psycopg.rows import dict_row

from pipdepgraph import models, constants
from pipdepgraph.repositories import table_names


class CandidatesRepository:
    def __init__(self, db_pool: ConnectionPool):
        self.db_pool = db_pool

    def insert_candidates(
        self,
        candidates: list[models.Candidate],
        cursor: Cursor | None = None,
    ):
        """
        Inserts a list of candidate records into the database in batches.
        Skips records that conflict on the composite primary key.
        """

        if not candidates:
            return

        def _insert_candidates(cursor: Cursor):
            PARAMS_PER_INSERT = 2
            for batch in itertools.batched(
                candidates,
                constants.POSTGRES_MAX_QUERY_PARAMS // PARAMS_PER_INSERT,
            ):
                query = f"""
                insert into {table_names.CANDIDATES}
                (requirement_id, version_id)
                values
                """
                query += ",".join("(%s, %s)" for _ in range(len(batch)))
                query += " on conflict do nothing"

                params = [None] * PARAMS_PER_INSERT * len(batch)
                offset = 0
                for candidate in batch:
                    params[offset + 0] = candidate.requirement_id
                    params[offset + 1] = candidate.version_id
                    offset += PARAMS_PER_INSERT

                cursor.execute(query, params)

        if cursor:
            _insert_candidates(cursor)
        else:
            with self.db_pool.connection() as conn, conn.cursor() as cursor:
                _insert_candidates(cursor)
                cursor.execute("commit;")
