from dataclasses import dataclass

import packaging
import packaging.specifiers
import packaging.requirements
import packaging.version

from pipdepgraph import constants


@dataclass(frozen=False)
class ParsedVersion:
    epoch: int
    package_release: tuple[int, ...] | None
    pre: tuple[str, int] | None
    post: int | None
    dev: int | None
    local: str | None
    is_prerelease: bool
    is_postrelease: bool
    is_devrelease: bool


def parse_version_string(version_string: str) -> ParsedVersion | None:
    """
    Parses a version string, extracting the version's "release" information.

    If any of the terms of the package release are greater than
    `constants.PACKAGE_RELEASE_TERM_MAX_SIZE`, the `package_release` property
    will be set to None. There are currently (October 2024) only 52 package
    versions that would benefit from a `package_release_numeric` property.
    """

    try:
        parsed_version = packaging.version.parse(version_string)
    except:
        return None

    postgres_bigint_compatible = True
    for release_term in parsed_version.release:
        if release_term > constants.PACKAGE_RELEASE_TERM_MAX_SIZE:
            postgres_bigint_compatible = False
            break

    return ParsedVersion(
        epoch=parsed_version.epoch,
        package_release=parsed_version.release if postgres_bigint_compatible else None,
        pre=parsed_version.pre,
        post=parsed_version.post,
        dev=parsed_version.dev,
        local=parsed_version.local,
        is_devrelease=parsed_version.is_devrelease,
        is_prerelease=parsed_version.is_prerelease,
        is_postrelease=parsed_version.is_postrelease,
    )
