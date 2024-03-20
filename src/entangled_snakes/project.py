import sys
import logging
from pathlib import Path
from typing import Sequence, TypedDict
from subprocess import CalledProcessError
import collections.abc

import packaging.utils

from . import nix


log = logging.getLogger(__name__)


class FromNixpkgs(TypedDict):
    pname: packaging.utils.NormalizedName
    extras: set[packaging.utils.NormalizedName]
    pin: str
    version: str
    drv: str


class ToFetch(TypedDict):
    pname: packaging.utils.NormalizedName
    extras: set[packaging.utils.NormalizedName]
    requirements: Sequence[str]


class Project(TypedDict):
    info: str
    fromNixpkgs: Sequence[FromNixpkgs]
    toFetch: Sequence[ToFetch]


def evaluate_project(
    project_root: Path,
    python: nix.PythonInterpreter,
    extras: bool | Sequence[str] = True,
) -> Project:
    """
    Parse dependency constraints from a pep621-compliant pyproject.toml
    in the given projectRoot. Verify whether those constraints match
    a python package from the given interpreter and the declared extras.
    If so, return a pin for the matched version.
    If not, return the constraints.
    Both together can be used by our python script, to resolve the
    missing dependencies while considering those from the interpreter
    as fixed.
    """
    if isinstance(extras, collections.abc.Sequence):
        extras = "[" + (" ".join(extras)) + "]"
    else:
        extras = str(extras).lower()

    try:
        data = nix.evaluate(
            f"""
              (builtins.getFlake "{nix.SELF_FLAKE}").lib.dependenciesToFetch {{
                python = {python.as_nix_snippet()};
                projectRoot = {project_root};
                extras = {extras};
              }}
            """,
        )
        assert isinstance(data, dict)
        return Project(**data)
    except CalledProcessError as e:
        log.fatal(f"Nix error while evaluating project {project_root}: {e.stderr}")
        sys.exit(1)