from typing import AsyncIterable

from pipdepgraph import models

class KnownVersionRepository:
    def __init__(self):
        # TODO: Add ref to db pool
        ...

    async def save_known_versions(self, known_versions: list[models.KnownVersion]):
        ...

    async def iter_known_versions(self) -> AsyncIterable[models.KnownVersion]:
        ...

    async def iter_known_version_batches(self, batch_size: int) -> AsyncIterable[list[models.KnownVersion]]:
        ...
