"""
Get distribution metadata from a given package or checkout.

* Check whether a PEP-658-compatible metadata file is available via HTTPS.
* If the package is a wheel, use the included metadata file.
* If the package is a sdist, check whether metadata file exists.
* If the package is a sdist, but no metadata file exists:
  * extract the source tree.
  * create a python environment that includes build-time requirements.
  * run a pep517-build in an isolated environment to acquire the metadata .


https://packaging.python.org/en/latest/specifications/core-metadata
https://peps.python.org/pep-0658/
"""

import logging
import subprocess
from io import BytesIO
from pathlib import Path
from contextlib import contextmanager
from tempfile import TemporaryDirectory
from zipfile import ZipFile
from typing import Optional, Sequence, Mapping
import tarfile

import requests
from packaging.metadata import parse_email

from . import nix

log = logging.getLogger(__name__)



#        nix_hash = pypi_to_nix_hash(candidate.hashes)
#        nix_path = prefetch(candidate.url, nix_hash)



class MetadataNotFound(Exception):
    pass


class MetadataPreparationFailed(Exception):
    def __init__(self, exc, candidate):
        super().__init__(f"Metadata preparation for {candidate.url} failed: {exc}")
        self.stdout = exc.exception.stdout
        self.stderr = exc.exception.stderr


def fetch_metadata(python, candidate):
    metadata = metadata_from_pep658(candidate)
    if metadata:
        log.debug(f"Found metadata for {candidate} via pep658")
        return metadata

    distribution_path = Path(nix.prefetch(candidate.url, nix.pypi_to_nix_hash(candidate.hashes)))

    with open(distribution_path, "rb") as distribution_file:
        if candidate.distribution.is_wheel:
            where = "wheel"
            metadata = metadata_from_wheel(candidate, distribution_file)
        elif candidate.distribution.is_sdist:
            where = "sdist"
            metadata = metadata_from_sdist(candidate, distribution_file)
            if not metadata: #or candidate.name in candidate.app_context.legacy_metadata:
                log.warn(
                    f"acquiring metadata for {candidate} from "
                    f"{candidate.distribution.filename}"
                )
                distribution_file.seek(0)
                with source_tree_from_sdist(candidate, distribution_file) as source_dir:
                    metadata_dir = (nix.metadata_from_source_dir(python, source_dir) / "output").resolve()
                    with open(metadata_dir / 'METADATA', "r") as f:
                        return parse_metadata(f)


    if metadata:
        log.debug(f"Found metadata for {candidate} in the {where} {candidate.url}")
        return metadata

    raise MetadataNotFound(f"No metadata found for {candidate} ({candidate.url})")


def parse_metadata(fp):
    raw, _ = parse_email(fp.read())
    return raw


def metadata_from_pep658(candidate):
    response = requests.get(f"{candidate.url}.metadata")
    if response.status_code == 404:
        return None
    response.raise_for_status()
    return parse_metadata(BytesIO(response.content))


def metadata_from_wheel(candidate, distribution_file):
    with ZipFile(distribution_file) as zip:
        try:
            return parse_metadata(zip.open(candidate.distribution.metadata_path))
        except KeyError:
            pass


def metadata_from_sdist(candidate, distribution_file):
    with tarfile.open(
        candidate.distribution.filename, fileobj=distribution_file
    ) as tar:
        try:
            return parse_metadata(tar.extractfile(candidate.distribution.metadata_path))
        except KeyError:
            pass


@contextmanager
def source_tree_from_sdist(candidate, distribution_file):
    filename = candidate.distribution.filename
    name_underscore = candidate.name.replace("-", "_")
    search_dirs = [
        f"{candidate.name}-{candidate.distribution.version}",
        f"{name_underscore}-{candidate.distribution.version}",
    ]
    distribution_file.seek(0)
    with tarfile.open(filename, fileobj=distribution_file) as tar, TemporaryDirectory(
        suffix=f"metadata-preparation-{filename}"
    ) as temp_dir:
        tar.extractall(temp_dir, filter="data")
        temp_dir = Path(temp_dir)

        for search_dir in search_dirs:
            if (temp_dir / search_dir).exists():
                temp_dir = temp_dir / search_dir

        yield temp_dir
