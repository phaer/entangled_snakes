import argparse
import logging
import json
from .nix import PythonInterpreter, evaluate_project, SELF_FLAKE, DEFAULT_PYTHON_ATTR


def info_command(args):
    python = PythonInterpreter(args.python_flake, args.python_attr).resolve_system()
    project = evaluate_project(
        project_root=args.project,
        python=python,
        # TODO extras
    )
    if args.json:
        print(json.dumps(project))
    else:
        print(project.get("info"))


def build_command(args):
    print("build", args)


def main():
    arg_parser = argparse.ArgumentParser()
    arg_parser.add_argument(
        "-l",
        "--log-level",
        default="info",
    )
    arg_parser.add_argument(
        "-j", "--json", action="store_true", default=False, help="print json output"
    )

    command_parsers = arg_parser.add_subparsers(required=True)
    parser_info = command_parsers.add_parser("info")
    parser_info.add_argument("project", help="path to a python project")
    parser_info.add_argument(
        "--python-flake",
        help="flake to get a python package set from.\ni.e. 'github:nixos/nixpkgs/nixos-unstable'",
        default=SELF_FLAKE,
    )
    parser_info.add_argument(
        "--python-attr",
        help="attribute of the flake to get a python package set from\ni.e. 'legacyPackages.$system.python3'",
        default=DEFAULT_PYTHON_ATTR,
    )
    parser_info.set_defaults(func=info_command)

    parser_build = command_parsers.add_parser("build")
    parser_build.set_defaults(func=build_command)

    args = arg_parser.parse_args()
    logging.basicConfig(level=args.log_level.upper())

    args.func(args)
