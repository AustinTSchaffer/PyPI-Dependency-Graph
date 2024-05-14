from typing import AsyncIterable

from pipdepgraph import models

class VersionDistributionRepository:
    def __init__(self):
        # TODO: Add ref to db pool
        ...

    async def save_version_distributions(self, version_distributions: list[models.VersionDistribution]):
        ...

    async def iter_version_distributions(self) -> AsyncIterable[models.VersionDistribution]:
        ...

    async def iter_version_distribution_batches(self, batch_size: int) -> AsyncIterable[list[models.VersionDistribution]]:
        ...
