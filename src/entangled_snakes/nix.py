from dataclasses import dataclass
import sys
import logging
import collections.abc
import subprocess
import json
from pathlib import Path
from typing import Any, Self, Optional, Sequence


log = logging.getLogger(__name__)


SELF_FLAKE = (Path(__file__) / "../../..").resolve()
DEFAULT_PYTHON_ATTR = "packages.$system.python"


@dataclass
class PythonInterpreter:
    """Thin abstraction to generate nix code that loads a nix python interpreter
    from a given flake and attribute.

    defaults to entangled_snakes wrapped python, but could be i.e.
    nixpkgs#legacyPackages.$system.python3
    """

    flake: Path | str = SELF_FLAKE
    attr: str = DEFAULT_PYTHON_ATTR

    def resolve_system(self) -> Self:
        try:
            current_system = nix_eval("builtins.currentSystem", raw=True)
            assert isinstance(current_system, str)
        except subprocess.CalledProcessError as e:
            log.fatal(f"Nix error while getting builtins.currentSystem: {e.stderr}")
            sys.exit(1)
        self.attr = self.attr.replace("$system", current_system)
        return self

    def as_nix_snippet(self) -> str:
        return f'(builtins.getFlake "{self.flake}").{self.attr}'


def nix_eval(expr: str, raw: bool = False, check: bool = True) -> str | dict[str, Any]:
    "Evaluate the given nix expr and return a json value"
    fmt = "--raw" if raw else "--json"
    args = ["nix", "eval", fmt, "--impure", "--expr", expr]
    logging.debug(f"evaluating {args}")
    proc = subprocess.run(args, check=check, capture_output=True, encoding="utf-8")
    if raw:
        return proc.stdout
    else:
        data = json.loads(proc.stdout)
        assert isinstance(data, dict)
        return data


def nix_build(
    installable: str, output: str = "out", raw: bool = False, check: bool = True
) -> str:
    """build a given nix installable (i.e. a drvPath) and return the selected
    output as json"""
    fmt = "" if raw else "--json"
    args = ["nix", "build", "--no-link", fmt, f"{installable}^{output}"]
    logging.debug(f"building {args}")
    proc = subprocess.run(args, check=check, capture_output=True, encoding="utf-8")
    if raw:
        return proc.stdout
    else:
        data = json.loads(proc.stdout)[0].get("outputs", {}).get(output)
        assert isinstance(data, str)
        return data


def nix_get_wheel_from_derivation(drv: str) -> Optional[str]:
    """Return a nix-built wheel from the given python package derivation"""
    built = nix_build(drv, "dist")
    wheels = list(Path(built).glob("*.whl"))
    if wheels:
        assert len(wheels) == 1
        return str(wheels[0])
    else:
        return None


def evaluate_project(
    project_root: Path,
    python: PythonInterpreter,
    extras: bool | Sequence[str] = True,
) -> dict[str, Any]:
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
        result = nix_eval(
            f"""
              (builtins.getFlake "{SELF_FLAKE}").lib.dependenciesToFetch {{
                python = {python.as_nix_snippet()};
                projectRoot = {project_root};
                extras = {extras};
              }}
            """,
        )
        assert isinstance(result, dict)
        return result
    except subprocess.CalledProcessError as e:
        log.fatal(f"Nix error while evaluating project {project_root}: {e.stderr}")
        sys.exit(1)


def make_build_environment(
    python: PythonInterpreter,
    requirements: Sequence[str] = [],
) -> str:
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

    assert isinstance(result, dict)
    error = result.get("error")
    if error:
        log.fatal(f"{error_context}: {error}")
        sys.exit(1)

    drv_path = result.get("success")
    assert isinstance(drv_path, str)
    return nix_build(drv_path)
