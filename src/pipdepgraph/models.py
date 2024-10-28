import dataclasses
from typing import Optional
import datetime
import uuid
import json


@dataclasses.dataclass
class PackageName:
    package_name: str
    date_discovered: Optional[datetime.datetime]
    date_last_checked: Optional[datetime.datetime]

    @classmethod
    def from_dict(cls, data: dict) -> "PackageName":
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
class Version:
    version_id: str | uuid.UUID | None
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

    @classmethod
    def from_dict(cls, data: dict) -> "Version":
        if "pre" in data:
            pre = tuple(data['pre'])
        elif "pre_0" in data and "pre_1" in data:
            pre = (data["pre_0"], data["pre_1"])
        else:
            pre = None

        return cls(
            version_id=data.get("version_id", None),
            package_name=data.get("package_name", None),
            package_version=data.get("package_version", None),
            date_discovered=data.get("date_discovered", None),

            epoch=data.get("epoch", 0),
            package_release=data.get("package_release", None),
            pre=pre,
            post=data.get("post", None),
            dev=data.get("dev", None),
            local=data.get("local", None),
            is_prerelease=data.get("is_prerelease", None),
            is_postrelease=data.get("is_postrelease", None),
            is_devrelease=data.get("is_devrelease", None),
        )


@dataclasses.dataclass
class Distribution:
    version_id: Optional[str]
    distribution_id: Optional[str]
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
    def from_dict(cls, data: dict) -> "Distribution":
        return cls(
            version_id=data.get("version_id", None),
            distribution_id=data.get("distribution_id", None),
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
                version_id=(
                    str(self.version_id)
                    if self.version_id is not None
                    else None
                ),
                distribution_id=(
                    str(self.distribution_id)
                    if self.distribution_id is not None
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
class Requirement:
    requirement_id: str | None
    distribution_id: str
    extras: str
    dependency_name: str
    dependency_extras: str
    version_constraint: str
    dependency_extras_arr: list[str]

    @classmethod
    def from_dict(cls, data: dict) -> "Requirement":
        return cls(
            requirement_id=data.get("requirement_id", None),
            distribution_id=data.get("distribution_id", None),
            extras=data.get("extras", None),
            dependency_name=data.get("dependency_name", None),
            dependency_extras=data.get("dependency_extras", None),
            version_constraint=data.get("version_constraint", None),
            dependency_extras_arr=data.get("dependency_extras_arr", None),
        )

    def to_json(self) -> str:
        return json.dumps(
            dict(
                requirement_id=(
                    str(self.requirement_id)
                    if self.requirement_id is not None
                    else None
                ),
                distribution_id=str(self.distribution_id),
                extras=self.extras,
                dependency_name=self.dependency_name,
                dependency_extras=self.dependency_extras,
                version_constraint=self.version_constraint,
                dependency_extras_arr=self.dependency_extras_arr,
            )
        )
