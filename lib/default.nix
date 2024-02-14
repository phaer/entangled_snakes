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

  makeBuildEnvironment = {
    python,
    requirements,
  }: let
    dependencies = map (r: pyproject.pep508.parseString r) requirements;
    validated = self.constraints.validateDependencies {
      inherit dependencies python;
    };
  in
    if validated.wrong != []
    # TODO better error formatting, format & print reasons for mismatch
    then throw "build requirements could not be satisfied by the current package set: ${toString requirements}"
    else
      python.withPackages(ps: map (d: ps.${d.pname}) validated.right);
})
