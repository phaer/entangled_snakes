from dataclasses import dataclass
import sys
import logging
import collections.abc
import subprocess
import json
from pathlib import Path
from typing import Sequence


log = logging.getLogger(__name__)


SELF_FLAKE = (Path(__file__) / "../../..").resolve()
DEFAULT_PYTHON_ATTR = "packages.$system.python"


def nix_eval(expr, raw=False, check=True):
    fmt = "--raw" if raw else "--json"
    args = ["nix", "eval", fmt, "--impure", "--expr", expr]
    logging.debug(f"running {args}")
    proc = subprocess.run(args, check=check, capture_output=True, encoding="utf-8")
    if raw:
        return proc.stdout
    else:
        return json.loads(proc.stdout)


@dataclass
class PythonInterpreter:
    flake: Path | str = SELF_FLAKE
    attr: str = DEFAULT_PYTHON_ATTR

    def resolve_system(self):
        try:
            current_system = nix_eval("builtins.currentSystem", raw=True)
        except subprocess.CalledProcessError as e:
            log.fatal(f"Nix error while getting builtins.currentSystem: {e.stderr}")
            sys.exit(1)
        self.attr = self.attr.replace("$system", current_system)
        return self

    def as_nix_snippet(self):
        return f'(builtins.getFlake "{self.flake}").{self.attr}'


def evaluate_project(
    project_root: Path,
    python: PythonInterpreter,
    extras: bool | Sequence[str] = True,
):
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
        return nix_eval(
            f"""
              (builtins.getFlake "{SELF_FLAKE}").lib.dependenciesToFetch {{
                python = {python.as_nix_snippet()};
                projectRoot = {project_root};
                extras = {extras};
              }}
            """,
        )
    except subprocess.CalledProcessError as e:
        log.fatal(f"Nix error while evaluating project {project_root}: {e.stderr}")
        sys.exit(1)


def make_build_environment(
    python: PythonInterpreter,
    requirements: Sequence[str] = [],
):
    """
    Take a python interpreter and a list of constraints, i.e. from build-system.requires,
    check whether those constraint match a python package from the given interpreter
    and if so, prepare a python environment with only the build-requirements installed.
    This is used internally for pep517-compatible builds.
    """
    error_context = (
        f"Error while preparing build environment for {' '.join(requirements)}"
    )
    try:
        result = nix_eval(
            f"""
            (builtins.getFlake "{SELF_FLAKE}").lib.makeBuildEnvironment {{
              python = {python.as_nix_snippet()};
              requirements = ["{ '" "'.join(requirements)}"];
            }}
            """,
            check=True,
        )
    except subprocess.CalledProcessError as e:
        log.fatal(f"Nix {error_context}: {e.stderr}")
        sys.exit(1)

    error = result.get("error")
    if error:
        log.fatal(f"{error_context}: {error}")
        sys.exit(1)

    return result.get("success")
