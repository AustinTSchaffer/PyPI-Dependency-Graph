import dataclasses
from typing import Optional
import datetime
import uuid
import json


@dataclasses.dataclass
class KnownPackageName:
    package_name: str
    date_discovered: Optional[datetime.datetime]
    date_last_checked: Optional[datetime.datetime]

    @classmethod
    def from_dict(cls, data: dict) -> "KnownPackageName":
        return cls(
            package_name=data.get("package_name", None),
            date_discovered=data.get("date_discovered", None),
            date_last_checked=data.get("date_last_checked", None),
        )

    def to_json(self) -> str:
        return json.dumps(
            dict(
                package_name=self.package_name,
                date_discovered=(
                    None
                    if self.date_discovered is None
                    else self.date_discovered.isoformat("T")
                ),
                date_last_checked=(
                    None
                    if self.date_last_checked is None
                    else self.date_last_checked.isoformat("T")
                ),
            )
        )


@dataclasses.dataclass
class KnownVersion:
    known_version_id: Optional[str | uuid.UUID]
    package_name: str
    package_version: str
    package_release: tuple[int, ...]
    package_release_numeric: None | tuple[int, ...]
    date_discovered: Optional[datetime.datetime]

    @classmethod
    def from_dict(cls, data: dict) -> "KnownVersion":
        return cls(
            known_version_id=data.get("known_version_id", None),
            package_name=data.get("package_name", None),
            package_version=data.get("package_version", None),
            package_release=data.get("package_release", None),
            package_release_numeric=data.get("package_release_numeric", None),
            date_discovered=data.get("date_discovered", None),
        )


@dataclasses.dataclass
class VersionDistribution:
    known_version_id: Optional[str]
    version_distribution_id: Optional[str]
    package_type: str
    python_version: str
    requires_python: Optional[str]
    upload_time: datetime.datetime
    yanked: bool
    package_filename: str
    package_url: str
    processed: bool
    metadata_file_size: int | None

    @classmethod
    def from_dict(cls, data: dict) -> "VersionDistribution":
        return cls(
            known_version_id=data.get("known_version_id", None),
            version_distribution_id=data.get("version_distribution_id", None),
            package_type=data.get("package_type", None),
            python_version=data.get("python_version", None),
            requires_python=data.get("requires_python", None),
            upload_time=data.get("upload_time", None),
            yanked=data.get("yanked", None),
            package_filename=data.get("package_filename", None),
            package_url=data.get("package_url", None),
            processed=data.get("processed", None),
            metadata_file_size=data.get("metadata_file_size", None),
        )

    def to_json(self) -> str:
        return json.dumps(
            dict(
                known_version_id=(
                    str(self.known_version_id)
                    if self.known_version_id is not None
                    else None
                ),
                version_distribution_id=(
                    str(self.version_distribution_id)
                    if self.version_distribution_id is not None
                    else None
                ),
                package_type=self.package_type,
                python_version=self.python_version,
                requires_python=self.requires_python,
                upload_time=self.upload_time.isoformat("T"),
                yanked=self.yanked,
                package_filename=self.package_filename,
                package_url=self.package_url,
                processed=self.processed,
                metadata_file_size=self.metadata_file_size,
            )
        )


@dataclasses.dataclass
class DirectDependency:
    version_distribution_id: str
    extras: Optional[str]
    dependency_name: str
    dependency_extras: Optional[str]
    version_constraint: Optional[str]

    @classmethod
    def from_dict(cls, data: dict) -> "DirectDependency":
        return cls(
            version_distribution_id=data.get("version_distribution_id", None),
            extras=data.get("extras", None),
            dependency_name=data.get("dependency_name", None),
            dependency_extras=data.get("dependency_extras", None),
            version_constraint=data.get("version_constraint", None),
        )
