{ lib
, pyproject
, constraints
, messages
}:
lib.fix (self: {

  makeBuildEnvironment = {
    python,
    requirements,
  }: let
    dependencies = map (r: pyproject.pep508.parseString r) requirements;
    validated = constraints.validateDependencies {
      inherit dependencies python;
    };
  in
    if validated.wrong != []
    then throw ''
        build requirements could not be satisfied by the current package set:
         - ${lib.concatMapStringsSep "\n- " messages.formatFailure validated.wrong}
      ''
    else python.withPackages (ps: map (d: ps.${d.pname}) validated.right);

  makeBuildEnvironmentFromProject = {
    python,
    project,
  }: let
    # Default to setuptools legacy as per PEP517
    requirements' = project.pyproject.build-system.requires or ["setuptools"];
    # Packages using setuptools often implicitly require "wheel" to create
    # the .dist-info directory. We use pyproject-hooks to call the build-system
    requirements = requirements' ++
                   ["pyproject_hooks"] ++
                   lib.optionals (lib.elem "setuptools" requirements') ["wheel"];
  in self.makeBuildEnvironment {
    inherit python requirements;
  };

  callHook = {
    python,
      project,
      hook,
      extraPath ? "",
      extraPythonPath ? "",
  }: let
    buildSystem = project.pyproject.build-system.build-backend or "setuptools.build_meta:__legacy__";
    buildPython = self.makeBuildEnvironmentFromProject {
      inherit python project;
    };
  in
    builtins.derivation {
      # TODO allow impure builds via __noChroot = true;
      inherit (buildPython.stdenv) system;
      name = "${project.pyproject.project.name or "unnamed"}";
      src = project.projectRoot;
      builder = "${buildPython}/bin/python";
      PATH = "${buildPython}/bin:${extraPath}";
      PYTHONPATH = "${buildPython.sitePackages}:${extraPythonPath}";
      inherit buildSystem hook;
      args = [ ./pep517.py ];
    };
})
