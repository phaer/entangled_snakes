from dataclasses import dataclass
import sys
import logging
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
            current_system = evaluate("builtins.currentSystem", raw=True)
            assert isinstance(current_system, str)
        except subprocess.CalledProcessError as e:
            log.fatal(f"Nix error while getting builtins.currentSystem: {e.stderr}")
            sys.exit(1)
        self.attr = self.attr.replace("$system", current_system)
        return self

    def as_nix_snippet(self) -> str:
        return f'(builtins.getFlake "{self.flake}").{self.attr}'


def evaluate(expr: str, raw: bool = False, check: bool = True) -> str | dict[str, Any]:
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


def build(
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


def get_wheel_from_derivation(drv: str) -> Optional[str]:
    """Return a nix-built wheel from the given python package derivation"""
    built = build(drv, "dist")
    wheels = list(Path(built).glob("*.whl"))
    if wheels:
        assert len(wheels) == 1
        return str(wheels[0])
    else:
        return None


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
        result = evaluate(
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
    return build(drv_path)
