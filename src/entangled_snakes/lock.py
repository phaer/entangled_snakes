from typing import Sequence

import resolvelib
from packaging.requirements import Requirement

from .finder import SimpleIndexFinder
from . import project
from . import nix
from .resolver.candidate import Candidate
from .resolver.providers import PyPiProvider
from .resolver import reporters

def print_graph_as_tree(graph, node=None, visited=None, level=0):
    if visited is None:
        visited = set()
    if node not in visited:
        print("  " * level + str(node))
        visited.add(node)
        for successor in graph.iter_children(node):
            print_graph_as_tree(graph, successor, visited, level + 1)


def lock(pyproject: project.Project, python: nix.PythonInterpreter):
    from IPython import embed
    from pprint import pprint

    installedFromNixpkgs: Sequence[Candidate] = []
    for package in pyproject.get("fromNixpkgs", []):
        if package.get("drv", None):
            wheel = nix.get_wheel_from_derivation(package["drv"])
            candidate = Candidate(wheel.name, url=f"file://{wheel.absolute()}")
            installedFromNixpkgs.append(candidate)

    requirements: Sequence[Requirement] = []
    for package in pyproject.get("toFetch", []):
        requirements.extend([Requirement(r) for r in package.get("requirements", [])])

    pprint(installedFromNixpkgs)
    pprint(requirements)
    #requirements = [Requirement("ruff==0.0.291")]
    #requirements = [Requirement("billogram-api==1.0.1")]
    #requirements = [Requirement('pydantic-core==2.14.6')]

    finder = SimpleIndexFinder()
    provider = PyPiProvider(finder, python, pre_installed=installedFromNixpkgs)
    reporter = reporters.DebugReporter()
    resolver = resolvelib.Resolver(provider, reporter)
    result = resolver.resolve(requirements, max_rounds=500)

    candidate = list(result.mapping.values())[0]
    embed()
