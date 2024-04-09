import logging
from operator import attrgetter
from typing import Sequence

from entangled_snakes.metadata import fetch_metadata
from packaging.requirements import Requirement
from packaging.utils import canonicalize_name

from resolvelib.providers import AbstractProvider

from . import Identifier
from .candidate import Candidate


log = logging.getLogger(__name__)


class PyPiProvider(AbstractProvider):
    def __init__(self, finder, python, pre_installed: Sequence[Candidate]):
        self.finder = finder
        self.python = python
        self.pre_installed = {
            self.identify(candidate): candidate
            for candidate in pre_installed
        }

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
        if identifier in self.pre_installed:
            log.info(f"found {identifier} in pre-installed set from nixpkgs")
            return [self.pre_installed[identifier]]
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
        log.info(f"getting dependencies for {candidate} ({candidate.filename})")
        metadata = fetch_metadata(self.python, candidate)
        return [
            Requirement(d.replace("\n", " "))
            for d in metadata.get('requires_dist', [])
        ]
        # deps = candidate.dependencies
        ## if candidate.extras:
        ##    req = self.get_base_requirement(candidate)
        ##    deps.append(req)
        # return deps
        #
        # deps = self.metadata.get_all("Requires-Dist", [])
        # extras = self.extras if self.extras else [""]
        # for d in deps:
        #    r = Requirement(d.replace("\n", " "))
        #    if r.marker is None:
        #        yield r
        #    else:
        #        for e in extras:
        #            if r.marker.evaluate({"extra": e}):
        #                yield r
