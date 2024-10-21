from dataclasses import dataclass

import packaging
import packaging.specifiers
import packaging.requirements
import packaging.version

from pipdepgraph import constants


@dataclass(frozen=False)
class ParsedVersion:
    epoch: int
    package_release: tuple[int | None, ...]
    pre: tuple[str, int | None] | None
    post: int | None
    dev: int | None
    local: str | None
    is_prerelease: bool
    is_postrelease: bool
    is_devrelease: bool


def parse_version_string(version_string: str) -> ParsedVersion | None:
    """
    Parses a version string, extracting the version's "release" information.

    If any of the terms of the parsed version are greater than
    `constants.PACKAGE_RELEASE_TERM_MAX_SIZE`, the respective property
    will be set to None.
    """

    try:
        parsed_version = packaging.version.parse(version_string)
    except:
        return None

    def bigint_protection(val: int | None) -> int | None:
        if val is None:
            return None
        if val <= constants.PACKAGE_RELEASE_TERM_MAX_SIZE:
            return val
        if val < 0 and val > -constants.PACKAGE_RELEASE_TERM_MAX_SIZE:
            return val
        return None

    package_release = tuple(
        [bigint_protection(term) for term in parsed_version.release]
    )

    pre: tuple[str, int | None] | None = None
    if parsed_version.pre is not None:
        pre = (
            parsed_version.pre[0],
            bigint_protection(parsed_version.pre[1]),
        )

    return ParsedVersion(
        epoch=bigint_protection(parsed_version.epoch),
        package_release=package_release,
        pre=pre,
        post=bigint_protection(parsed_version.post),
        dev=bigint_protection(parsed_version.dev),
        local=parsed_version.local,
        is_devrelease=parsed_version.is_devrelease,
        is_prerelease=parsed_version.is_prerelease,
        is_postrelease=parsed_version.is_postrelease,
    )
