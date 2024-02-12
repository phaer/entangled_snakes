{
  lib,
  pyproject,
}:
lib.fix (self: {
  loadProject = projectRoot:
    (
      if builtins.pathExists /${projectRoot}/pyproject.toml
      then pyproject.project.loadPyproject
      else pyproject.project.loadRequirementsTxt
    )
    {
      inherit projectRoot;
    };

  constraints = import ./constraints.nix {
    inherit lib;
    inherit (pyproject) pep440 pep508 pep621 pypa;
  };

  fixtures = import ../fixtures/default.nix {
    inherit lib pyproject;
    inherit (self) constraints loadProject;
  };
})