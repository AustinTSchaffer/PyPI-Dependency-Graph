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
        requirement.
        """

        req_specifier_set = packaging.specifiers.SpecifierSet(requirement.version_constraint)

        versions = await self.versions_repo.get_versions(package_name=requirement.dependency_name)
        version_dict = {
            version.package_version: version
            for version in versions
        }

        parsed_versions = [packaging.version.Version(version.package_version) for version in versions]
        candidate_versions = sorted(req_specifier_set.filter(parsed_versions), reverse=True)

        candidate_versions_text = [str(v) for v in candidate_versions]
        candidate_version_ids = [version_dict[v].version_id for v in candidate_versions_text]

        await self.candidates_repo.insert_candidate(models.Candidate(
            requirement_id=requirement.requirement_id,
            candidate_versions=candidate_versions_text,
            candidate_version_ids=candidate_version_ids,
        ))
