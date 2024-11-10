import datetime
import logging

import packaging
import packaging.specifiers
import packaging.version
from psycopg_pool import AsyncConnectionPool
from psycopg.rows import dict_row

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
        db_pool: AsyncConnectionPool,
        vr: versions_repository.VersionsRepository,
        rr: requirements_repository.RequirementsRepository,
        cr: candidates_repository.CandidatesRepository,
    ):
        self.db_pool = db_pool
        self.versions_repo = vr
        self.requirements_repo = rr
        self.candidates_repo = cr


    async def process_version_record(
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

        async with self.db_pool.connection() as conn, conn.cursor(
            row_factory=dict_row
        ) as cursor:
            logger.info(f"Searching for requirements that depend on: {version.package_name}=={version.package_version}")
            async for reverse_candidate in self.requirements_repo.iter_requirements(dependency_name=version.package_name):
                ...


    async def process_requirement_record(
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

        versions = await self.versions_repo.get_versions(package_name=requirement.dependency_name)
        package_version_to_version_model_map = {
            version.package_version: version
            for version in versions
        }

        parsed_version_to_package_version_map = {}
        for version in versions:
            try:
                parsed_version = packaging.version.Version(version.package_version)
                parsed_version_to_package_version_map[parsed_version] = version.package_version
            except:
                logger.error("Error while parsing version: %s.", version.package_version, exc_info=True)
                pass

        try:
            sorted_parsed_candidate_versions = sorted(req_specifier_set.filter(parsed_version_to_package_version_map.keys()), reverse=True)
        except Exception:
            logger.error("Error while filter-sorting requirements.", exc_info=True)
            return

        candidate_versions_text = [parsed_version_to_package_version_map[v] for v in sorted_parsed_candidate_versions]
        candidate_version_ids = [package_version_to_version_model_map[v].version_id for v in candidate_versions_text]

        await self.candidates_repo.insert_candidate(models.Candidate(
            requirement_id=requirement.requirement_id,
            candidate_versions=candidate_versions_text,
            candidate_version_ids=candidate_version_ids,
        ))
