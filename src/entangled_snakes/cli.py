import argparse
import logging
import json

from . import nix
from . import project


def info_command(args: argparse.Namespace) -> None:
    python = nix.PythonInterpreter(args.python_flake, args.python_attr).resolve_system()
    pyproject = project.evaluate_project(
        project_root=args.project.removesuffix("/"),
        python=python,
    )

    for package in pyproject.get("fromNixpkgs", []):
        if package.get("drv", None):
            package.update(wheel=nix.get_wheel_from_derivation(package["drv"]))

    if args.json:
        print(json.dumps(pyproject))
    else:
        print(pyproject.get("info"))


def make_build_env_command(args: argparse.Namespace) -> None:
    python = nix.PythonInterpreter(args.python_flake, args.python_attr).resolve_system()
    print(nix.make_build_environment(python, args.requirements))


def make_editable_command(args: argparse.Namespace) -> None:
    python = nix.PythonInterpreter(args.python_flake, args.python_attr).resolve_system()
    project_root = args.project.removesuffix("/")
    print(project.make_editable(project_root, python))


def main() -> None:
    arg_parser = argparse.ArgumentParser()
    arg_parser.add_argument(
        "-l",
        "--log-level",
        default="info",
    )
    arg_parser.add_argument(
        "-j", "--json", action="store_true", default=False, help="print json output"
    )

    arg_parser.add_argument(
        "--python-flake",
        help="flake to get a python package set from.\ni.e. 'github:nixos/nixpkgs/nixos-unstable'",
        default=nix.SELF_FLAKE,
    )
    arg_parser.add_argument(
        "--python-attr",
        help="attribute of the flake to get a python package set from\ni.e. 'legacyPackages.$system.python3'",
        default=nix.DEFAULT_PYTHON_ATTR,
    )

    command_parsers = arg_parser.add_subparsers(required=True)
    parser_info = command_parsers.add_parser("info")
    parser_info.add_argument("project", help="path to a python project")
    parser_info.set_defaults(func=info_command)

    parser_make_build_env = command_parsers.add_parser("make-build-environment")
    parser_make_build_env.add_argument(
        "requirements", nargs="*", help="list of pep508 requirements"
    )
    parser_make_build_env.set_defaults(func=make_build_env_command)

    parser_make_editable = command_parsers.add_parser("make-editable")
    parser_make_editable.add_argument("project", help="path to a python project")
    parser_make_editable.set_defaults(func=make_editable_command)

    args = arg_parser.parse_args()
    logging.basicConfig(level=args.log_level.upper())

    args.func(args)
