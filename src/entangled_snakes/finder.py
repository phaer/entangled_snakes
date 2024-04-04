import logging
from platform import python_version

import requests
from packaging.version import Version, InvalidVersion
from packaging.utils import InvalidSdistFilename
from packaging.tags import Tag
from packaging.specifiers import InvalidSpecifier, SpecifierSet

from .resolver import UnsupportedFileType
from .resolver.candidate import Candidate

PYTHON_VERSION = Version(python_version())
log = logging.getLogger(__name__)


class SimpleIndexFinder:
    def __init__(self, index_url="https://pypi.org/simple"):
        self.index_url = index_url
        self.session = requests.Session()
        self.cache = dict()
        # TODO We only accept platform-independent wheels atm, and else fallback to
        # sdists. This helps keeping cross-platform compatibility for the lock file and
        # leaves the rest to nix.
        self.acceptable_tags = frozenset([Tag("py3", "none", "any")])

    def find_candidates(self, identifier):
        log = logging.getLogger(f"{__name__}.{identifier}")
        """Return candidates created from the project name and extras."""
        if identifier in self.cache:
            log.info(
                f"reusing cached candidates for {identifier} from {self.index_url}"
            )
            for candidate in self.cache[identifier]:
                yield candidate
            return

        self.cache[identifier] = []
        log.debug(f"gathering candidates for {identifier} from {self.index_url}")
        url = f"{self.index_url}/{identifier.name}"

        response = self.session.get(
            url, headers={"Accept": "application/vnd.pypi.simple.v1+json"}
        )
        response.raise_for_status()
        data = response.json()

        for link in data.get("files", []):
            try:
                candidate = Candidate(
                    link["filename"],
                    url=link["url"],
                    hashes=link["hashes"],
                    extras=identifier.extras,
                )
                if candidate.distribution.is_wheel:
                    if not candidate.distribution.tags.intersection(
                        self.acceptable_tags
                    ):
                        log.debug(
                            " ".join(
                                [
                                    f"skipping {link['filename']} because its tags",
                                    ",".join(
                                        [str(t) for t in candidate.distribution.tags]
                                    ),
                                    "do not match",
                                    ",".join([str(t) for t in self.acceptable_tags]),
                                ]
                            )
                        )
                        continue
            except UnsupportedFileType:
                log.warning(
                    f"skipping {link['filename']} as file format is not supported"
                )
                continue
            except (InvalidVersion, InvalidSdistFilename) as e:
                log.warning(f"skipping {link['filename']} because of {e}")
                continue

            # Skip items that need a different Python version
            requires_python = link.get("requires-python")
            if requires_python:
                try:
                    spec = SpecifierSet(requires_python)
                    if PYTHON_VERSION not in spec:
                       continue
                except InvalidSpecifier:
                    log.warning(f"invalid specifier for {link['filename']}: {requires_python}")
            self.cache[identifier].append(candidate)
            yield candidate
