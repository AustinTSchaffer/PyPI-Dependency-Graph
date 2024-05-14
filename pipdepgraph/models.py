import dataclasses
from typing import Optional
import datetime

@dataclasses.dataclass
class KnownPackageName:
    package_name: str
    date_discovered: Optional[datetime.datetime]
    date_last_checked: Optional[datetime.datetime]

@dataclasses.dataclass
class KnownVersion:
    known_version_id: Optional[str]
    package_name: str
    package_version: str
    package_release: tuple[int, ...]
    date_discovered: Optional[datetime.datetime]

@dataclasses.dataclass
class VersionDistribution:
    known_version_id: Optional[str]
    version_distribution_id: Optional[str]
    python_version: str
    requires_python: Optional[str]
    upload_time: datetime.datetime
    yanked: bool
    package_filename: str
    package_url: str
    processed: bool

@dataclasses.dataclass
class DirectDependency:
    version_distribution_id: str
    extras: Optional[str]
    dependency_name: str
    dependency_extras: Optional[str]
    version_constraint: Optional[str]
