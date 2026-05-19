import datetime
import logging

import packaging
import packaging.specifiers
import packaging.version
from psycopg_pool import ConnectionPool

from pipdepgraph import models
from pipdepgraph.repositories import (
    requirements_repository,
    versions_repository,
    candidates_repository,
)

logger = logging.getLogger(__name__)

class CandidateCorrelationService:
    """
    The candidate correlation service matches up requirement records and
    version records, maintaining the "candidates" table in postgres.
    """

    def __init__(
        self,
        *,
        db_pool: ConnectionPool,
        vr: versions_repository.VersionsRepository,
        rr: requirements_repository.RequirementsRepository,
        cr: candidates_repository.CandidatesRepository,
    ):
        self.db_pool = db_pool
        self.versions_repo = vr
        self.requirements_repo = rr
        self.candidates_repo = cr


    def process_version_record(
        self,
        version: models.Version,
    ):
        """
        Processes a single version record, finding requirements that the version
        can satisfy.

        TODO: This method is probably way too slow for popular packages. Recheck
        this once we're not redoing the entire reqs table. It might be better to
        use iter_requirements on the package name and pump those requirements into
        RabbitMQ.
        """

        try:
            parsed_version = packaging.version.Version(version.package_version)
        except Exception:
            logger.error("Error while parsing version: %s.", version.package_version, exc_info=True)
            return

        candidates = []
        for requirement in self.requirements_repo.iter_requirements(dependency_name=version.package_name):
            if not requirement.dependency_name or str.isspace(requirement.dependency_name):
                continue

            try:
                req_specifier_set = packaging.specifiers.SpecifierSet(requirement.version_constraint)
            except Exception:
                logger.error("Error while parsing specifier set: %s", requirement.version_constraint, exc_info=True)
                continue

            if parsed_version in req_specifier_set:
                candidates.append(
                    models.Candidate(
                        requirement_id=requirement.requirement_id,
                        version_id=version.version_id,
                    )
                )

        self.candidates_repo.insert_candidates(candidates)


    def process_requirement_record(
        self,
        requirement: models.Requirement,
    ):
        """
        Processes a single requirement record, finding versions that satisfy the
        requirement. Most errors in here fail silently, as that likely indicates
        pip will also have a problem with those specifier sets and version strings
        as well. Some errors, such as DB interaction issues, will cause genuine a
        failure.
        """

        # Related to a bug with metadata files that have a blank "RequiresDist:"
        # entry. There's no point in trying to process an empty package name.
        if not requirement.dependency_name or str.isspace(requirement.dependency_name):
            return

        try:
            req_specifier_set = packaging.specifiers.SpecifierSet(requirement.version_constraint)
        except Exception:
            logger.error("Error while parsing specifier set: %s", requirement.version_constraint, exc_info=True)
            return

        versions = self.versions_repo.get_versions(package_name=requirement.dependency_name)
        parsed_version_to_package_version_map: dict[packaging.version.Version, models.Version] = {}
        for version in versions:
            try:
                parsed_version = packaging.version.Version(version.package_version)
                parsed_version_to_package_version_map[parsed_version] = version
            except:
                logger.error("Error while parsing version: %s.", version.package_version, exc_info=True)
                pass

        parsed_candidate_versions = list(req_specifier_set.filter(parsed_version_to_package_version_map.keys()))
        candidates = [
            models.Candidate(
                requirement_id=requirement.requirement_id,
                version_id=parsed_version_to_package_version_map[v].version_id,
            )
            for v in parsed_candidate_versions
        ]

        self.candidates_repo.insert_candidates(candidates)
