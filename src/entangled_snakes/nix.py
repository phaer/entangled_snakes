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


def evaluate_project(
    project_root: Path,
    python_flake: Path | str = SELF_FLAKE,
    python_attr: str = DEFAULT_PYTHON_ATTR,
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
        current_system = nix_eval("builtins.currentSystem", raw=True)
    except subprocess.CalledProcessError as e:
        log.fatal(f"Nix error while getting builtins.currentSystem: {e.stderr}")
        sys.exit(1)

    python_attr = python_attr.replace("$system", current_system)
    try:
        return nix_eval(
            f"""
              (builtins.getFlake "{SELF_FLAKE}").lib.dependenciesToFetch {{
                python = (builtins.getFlake \"{python_flake}\").{python_attr};
                projectRoot = {project_root};
                extras = {extras};
              }}
            """,
        )
    except subprocess.CalledProcessError as e:
        log.fatal(f"Nix error while evaluating project {project_root}: {e.stderr}")
        sys.exit(1)
