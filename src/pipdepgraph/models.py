import datetime
import uuid
from typing import Literal

import msgspec


class Package(msgspec.Struct):
    name: str
    date_discovered: datetime.datetime | None = None
    date_last_checked: datetime.datetime | None = None


class Version(msgspec.Struct):
    version_id: uuid.UUID | None
    package_name: str
    package_version: str
    date_discovered: datetime.datetime | None
    epoch: int | None = None
    package_release: tuple[int, ...] | None = None
    pre: tuple[str, int] | None = None
    post: int | None = None
    dev: int | None = None
    local: str | None = None
    is_prerelease: bool | None = None
    is_postrelease: bool | None = None
    is_devrelease: bool | None = None


class Distribution(msgspec.Struct):
    version_id: str | None
    distribution_id: str | None
    package_type: str
    python_version: str
    requires_python: str | None
    upload_time: datetime.datetime
    yanked: bool
    package_filename: str
    package_url: str
    processed: bool
    metadata_file_size: int | None


class Requirement(msgspec.Struct):
    requirement_id: str | None
    distribution_id: str
    marker: str
    dependency_name: str
    version_constraint: str
    dependency_extras: list[str]
    parsable: bool = True


class Candidate(msgspec.Struct):
    requirement_id: str
    version_id: str


class EventLogEntry(msgspec.Struct):
    event_id: int
    operation: Literal["INSERT", "UPDATE", "DELETE"]
    schema: str
    table: str
    before: dict | None
    after: dict | None
    timestamp: datetime.datetime
