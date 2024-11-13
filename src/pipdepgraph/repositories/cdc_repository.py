from typing import AsyncIterable

from psycopg_pool import AsyncConnectionPool
from psycopg import AsyncCursor
from psycopg.rows import dict_row

from pipdepgraph import models, constants
from pipdepgraph.repositories import table_names


class CdcRepository:
    def __init__(self, db_pool: AsyncConnectionPool):
        self.db_pool = db_pool


    async def iter_event_log(
        self,
        from_beginning: bool = False,
        auto_upsert_offset: bool = True,
    ) -> AsyncIterable[models.EventLogEntry]:
        async with self.db_pool.connection() as conn, conn.cursor(
            row_factory=dict_row, name='iter_event_log'
        ) as cursor:
            event_id_offset = None
            if not from_beginning:
                query = f"select o.event_id event_id from {table_names.CDC_OFFSETS} o where o.table = %s;"
                params = [table_names.CDC_EVENT_LOG]
                await cursor.execute(query, params)
                result = await cursor.fetchall()
                if len(result) > 1:
                    raise ValueError(f"{table_names.CDC_OFFSETS} has more than one entry for table {table_names.CDC_EVENT_LOG}")
                if len(result) == 1:
                    event_id_offset = result[0]["event_id"]

            query = f"""
            select
                el.event_id,
                el.operation,
                el.schema,
                el.table,
                el.before,
                el.after,
                el.timestamp
            from {table_names.CDC_EVENT_LOG} el
            """

            params = []
            if event_id_offset is not None:
                query += " where el.event_id > %s "
                params.append(event_id_offset)

            query += " order by el.event_id asc;"

            await cursor.execute(query, params)
            records = await cursor.fetchmany(size=constants.CDC_EVENT_LOG_REPO_ITER_BATCH_SIZE)

            max_event_id_seen = None
            while records:
                for record in records:
                    event = models.EventLogEntry.from_dict(record)

                    if max_event_id_seen is None:
                        max_event_id_seen = event.event_id
                    else:
                        max_event_id_seen = max(max_event_id_seen, event.event_id)

                    yield event

                records = await cursor.fetchmany(size=constants.CDC_EVENT_LOG_REPO_ITER_BATCH_SIZE)

                if auto_upsert_offset:
                    await self.upsert_offset(table_names.CDC_EVENT_LOG, max_event_id_seen)

            if max_event_id_seen is not None and auto_upsert_offset:
                await self.upsert_offset(table_names.CDC_EVENT_LOG, max_event_id_seen)


    async def upsert_offset(
        self,
        table_name: str,
        event_id_offset: int,
        cursor: AsyncCursor = None,
    ):
        async def _upsert_offset(cursor: AsyncCursor):

            query = f"""
            insert into {table_names.CDC_OFFSETS}
                ("table", "event_id")
            values
                (%s, %s)
            on conflict ("table") do update set
                "event_id" = EXCLUDED."event_id"
            ;
            """

            params = [table_name, event_id_offset]
            await cursor.execute(query, params)

        if cursor:
            await _upsert_offset(cursor)
        else:
            async with self.db_pool.connection() as conn, conn.cursor() as cursor:
                await _upsert_offset(cursor)
                await cursor.execute("commit;")
