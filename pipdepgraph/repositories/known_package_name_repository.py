from typing import AsyncIterable

from pipdepgraph import models

class KnownPackageNameRepository:
    def __init__(self):
        # TODO: Add ref to db pool
        ...

    async def save_known_package_names(self, package_names: list[models.KnownPackageName | str]):
        ...

    async def iter_known_package_names(self) -> AsyncIterable[models.KnownPackageName]:
        ...

    async def iter_known_package_name_batches(self, batch_size: int) -> AsyncIterable[list[models.KnownPackageName]]:
        ...
