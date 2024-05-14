from typing import AsyncIterable

from psycopg_pool import AsyncConnectionPool
from psycopg import AsyncCursor

from pipdepgraph import models


class DirectDependencyRepository:
    def __init__(self, db_pool: AsyncConnectionPool):
        self.db_pool = db_pool

    async def save_direct_dependencies(
        self,
        direct_dependencies: list[models.DirectDependency],
        cursor: AsyncCursor | None,
    ): ...

    async def iter_direct_dependencies(
        self,
    ) -> AsyncIterable[models.DirectDependency]: ...

    async def iter_direct_dependency_batches(
        self, batch_size: int
    ) -> AsyncIterable[list[models.DirectDependency]]: ...
