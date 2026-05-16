import itertools

from psycopg_pool import ConnectionPool
from psycopg import Cursor
from psycopg.rows import dict_row

from pipdepgraph import models, constants
from pipdepgraph.repositories import table_names


class CandidatesRepository:
    def __init__(self, db_pool: ConnectionPool):
        self.db_pool = db_pool

    def insert_candidate(
        self,
        candidate: models.Candidate,
        cursor: Cursor | None = None,
    ):
        """
        Inserts a candidate record into the database. Updates the existing record
        on PK conflict.
        """

        def _insert_candidate(cursor: Cursor):
            query = f"""
            insert into {table_names.CANDIDATES}
            (requirement_id, candidate_versions, candidate_version_ids)
            values (%s, %s, %s)
            on conflict (requirement_id) do update set
                candidate_versions = EXCLUDED.candidate_versions,
                candidate_version_ids = EXCLUDED.candidate_version_ids
            ;"""

            params = [candidate.requirement_id, candidate.candidate_versions, candidate.candidate_version_ids]

            cursor.execute(query, params)

        if cursor:
            _insert_candidate(cursor)
        else:
            with self.db_pool.connection() as conn, conn.cursor() as cursor:
                _insert_candidate(cursor)
                cursor.execute("commit;")
