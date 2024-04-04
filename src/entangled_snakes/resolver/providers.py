import logging
from operator import attrgetter

from packaging.requirements import Requirement
from packaging.utils import canonicalize_name

from resolvelib.providers import AbstractProvider

from . import Identifier


log = logging.getLogger(__name__)


class PyPiProvider(AbstractProvider):
    def __init__(self, finder):
        self.finder = finder

    def identify(self, requirement_or_candidate):
        return Identifier(
            requirement_or_candidate.name, frozenset(requirement_or_candidate.extras)
        )

    def get_base_requirement(self, candidate):
        return Requirement(
            "{}=={}".format(candidate.distribution.name, candidate.distribution.version)
        )

    def get_preference(
        self, identifier, resolutions, candidates, information, backtrack_causes
    ):
        return sum(1 for _ in candidates[identifier])

    def find_matches(self, identifier, requirements, incompatibilities):
        log.debug(f"finding candidates for {identifier}")
        requirements = list(requirements[identifier])
        log.debug(f"requirements: {requirements}")
        bad_versions = {c.version for c in incompatibilities[identifier]}
        log.debug(f"bad_versions: {bad_versions}")

        candidates = (
            candidate
            for candidate in self.finder.find_candidates(identifier)
            if candidate.distribution.version not in bad_versions
            and all(candidate.distribution.version in r.specifier for r in requirements)
        )
        log.debug(f"found candidates: {candidates}")
        return sorted(candidates, key=attrgetter("distribution.version"), reverse=True)

    def is_satisfied_by(self, requirement, candidate):
        if canonicalize_name(requirement.name) != candidate.distribution.name:
            return False
        # if requirement.extras not in candidate.extras:
        #    return False
        return candidate.distribution.version in requirement.specifier

    def get_dependencies(self, candidate):
        return []
        # deps = candidate.dependencies
        ## if candidate.extras:
        ##    req = self.get_base_requirement(candidate)
        ##    deps.append(req)
        # return deps
