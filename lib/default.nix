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

  dependenciesToFetch = {
    python,
    projectRoot,
    # extras is either a list of strings, or the boolean value true to include
    # all extras, even if no extra named "all" is defined in the project.
    extras ? [],
  }: let
    project = self.loadProject projectRoot;
    extras' =
      if extras == true
      then lib.attrNames (project.pyproject.project.optional-dependencies or {})
      else extras;
  in
    self.constraints.validate {
      inherit project python;
      extras = extras';
    };
})
