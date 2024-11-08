from typing import AsyncIterable
import itertools
import dataclasses

from psycopg_pool import AsyncConnectionPool
from psycopg import AsyncCursor
from psycopg.rows import dict_row

from pipdepgraph import models, constants
from pipdepgraph.repositories import table_names


class CandidatesRepository:
    def __init__(self, db_pool: AsyncConnectionPool):
        self.db_pool = db_pool

    async def insert_candidate(
        self,
        candidate: models.Candidate,
        cursor: AsyncCursor | None = None,
    ):
        """
        Inserts a candidate record into the database. Updates the existing record
        on PK conflict.
        """

        async def _insert_candidate(cursor: AsyncCursor):
            query = f"""
            insert into {table_names.CANDIDATES}
            (requirement_id, candidate_versions, candidate_version_ids)
            values (%s, %s, %s)
            on conflict (requirement_id) do update set
                candidate_versions = EXCLUDED.candidate_versions,
                candidate_version_ids = EXCLUDED.candidate_version_ids
            ;"""

            params = [candidate.requirement_id, candidate.candidate_versions, candidate.candidate_version_ids]

            await cursor.execute(query, params)

        if cursor:
            await _insert_candidate(cursor)
        else:
            async with self.db_pool.connection() as conn, conn.cursor() as cursor:
                await _insert_candidate(cursor)
                await cursor.execute("commit;")
