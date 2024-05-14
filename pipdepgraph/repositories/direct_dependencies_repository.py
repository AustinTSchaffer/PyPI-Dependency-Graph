from typing import AsyncIterable

from pipdepgraph import models

class DirectDependencyRepository:
    def __init__(self):
        # TODO: Add ref to db pool
        ...

    async def save_direct_dependencies(self, direct_dependencies: list[models.DirectDependency]):
        ...

    async def iter_direct_dependencies(self) -> AsyncIterable[models.DirectDependency]:
        ...

    async def iter_direct_dependency_batches(self, batch_size: int) -> AsyncIterable[list[models.DirectDependency]]:
        ...
