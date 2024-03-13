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
        current_system = subprocess.run(
            ["nix", "eval", "--raw", "--impure", "--expr", "builtins.currentSystem"],
            check=True,
            capture_output=True,
            encoding="utf-8",
        ).stdout
    except subprocess.CalledProcessError as e:
        log.fatal(f"Nix error while getting builtins.currentSystem: {e.stderr}")
        sys.exit(1)

    python_attr = python_attr.replace("$system", current_system)
    args = [
        "nix",
        "eval",
        "--json",
        "--impure",
        "--expr",
        f"""
          (builtins.getFlake "{SELF_FLAKE}").lib.dependenciesToFetch {{
            python = (builtins.getFlake \"{python_flake}\").{python_attr};
            projectRoot = {project_root};
            extras = {extras};
          }}
        """,
    ]
    try:
        proc = subprocess.run(args, check=True, capture_output=True, encoding="utf-8")
        return json.loads(proc.stdout)
    except subprocess.CalledProcessError as e:
        log.fatal(f"Nix error while evaluating project {project_root}: {e.stderr}")
        sys.exit(1)
