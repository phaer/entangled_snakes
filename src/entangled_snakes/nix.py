from dataclasses import dataclass
import sys
import logging
import subprocess
import json
from pathlib import Path
from typing import Any, Self, Sequence
from base64 import b64encode, b16decode

log = logging.getLogger(__name__)


def find_entangled_snakes_flake() -> Path:
    """Search the directory tree upwards from the currents scripts path
    in search of flake.nix from this project in order to execute nix
    functions from flake.lib"""

    def find_upwards(filename: str, path: Path) -> Path:
        if (path / filename).exists():
            return path
        elif path == path.parent:
            raise Exception("Could not find entangled_snakes flake.nix")
        else:
            return find_upwards(filename, path.parent)

    return find_upwards("flake.nix", Path(__file__).resolve())


SELF_FLAKE = find_entangled_snakes_flake()
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
    log.debug(f"evaluating {args}")
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
    log.debug(f"building {args}")
    proc = subprocess.run(args, check=check, capture_output=True, encoding="utf-8")
    if raw:
        return proc.stdout
    else:
        data = json.loads(proc.stdout)[0].get("outputs", {}).get(output)
        assert isinstance(data, str)
        return data


def get_wheel_from_derivation(drv: str) -> Path:
    """Return a nix-built wheel from the given python package derivation"""
    built = build(drv, "dist")
    wheels = list(Path(built).glob("*.whl"))
    assert len(wheels) == 1, f"Could not find exactly 1 wheel in {drv}"
    return wheels[0]


def prefetch(url: str, expected_hash=None):
    """
    Let nix download the given url, write it to the nix store and
    compare the hashes, if given.
    """
    args = [
        "nix",
        "store",
        "prefetch-file",
        "--hash-type",
        "sha256",
        "--json",
        url,
    ]
    log.debug("pre-fetching {args}")
    proc = subprocess.run(args, check=True, capture_output=True, encoding="utf-8")
    nix_out = json.loads(proc.stdout)
    nix_hash = nix_out.get("hash")
    if expected_hash:
        assert (
            expected_hash == nix_hash
        ), f"hash mismatch for {url}:\nfound: {nix_hash}\nexpected: {expected_hash}"
    return nix_out.get("storePath")


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


def pypi_to_nix_hash(hashes):
    typ = "sha256"
    nix_hash = b64encode(b16decode(hashes[typ].upper())).decode("utf-8")
    return f"{typ}-{nix_hash}"
