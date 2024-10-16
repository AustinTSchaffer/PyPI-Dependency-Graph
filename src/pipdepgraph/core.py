from dataclasses import dataclass

import packaging
import packaging.version

from pipdepgraph import constants

@dataclass(frozen=False)
class ParsedVersion:
    package_release: tuple[int, ...] | None
    package_release_numeric: None | tuple[int, ...]

def parse_version_string(version_string: str) -> ParsedVersion:
    pvc = ParsedVersion(
        package_release=None,
        package_release_numeric=None,
    )

    postgres_bigint_compatible = True

    try:
        parsed_version = packaging.version.parse(version_string)
        for release_term in parsed_version.release:
            if release_term > constants.PACKAGE_RELEASE_TERM_MAX_SIZE:
                postgres_bigint_compatible = False
                break

        if postgres_bigint_compatible:
            pvc.package_release = parsed_version.release
        else:
            pvc.package_release_numeric = parsed_version.release

    except:
        pass

    return pvc
