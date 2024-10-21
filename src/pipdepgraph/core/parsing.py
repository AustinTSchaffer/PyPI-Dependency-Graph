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

    If any of the terms of the parsed version are greater than
    `constants.PACKAGE_RELEASE_TERM_MAX_SIZE`, the respective property
    will be set to None.
    """

    try:
        parsed_version = packaging.version.parse(version_string)
    except:
        return None

    release_is_bigint_compatible = True
    for release_term in parsed_version.release:
        if release_term > constants.PACKAGE_RELEASE_TERM_MAX_SIZE:
            release_is_bigint_compatible = False
            break

    return ParsedVersion(
        epoch=parsed_version.epoch if parsed_version.epoch <= constants.PACKAGE_RELEASE_TERM_MAX_SIZE else None,
        package_release=parsed_version.release if release_is_bigint_compatible else None,
        pre=parsed_version.pre if parsed_version.pre[1] <= constants.PACKAGE_RELEASE_TERM_MAX_SIZE else None,
        post=parsed_version.post if parsed_version.post <= constants.PACKAGE_RELEASE_TERM_MAX_SIZE else None,
        dev=parsed_version.dev if parsed_version.dev <= constants.PACKAGE_RELEASE_TERM_MAX_SIZE else None,
        local=parsed_version.local,
        is_devrelease=parsed_version.is_devrelease,
        is_prerelease=parsed_version.is_prerelease,
        is_postrelease=parsed_version.is_postrelease,
    )
