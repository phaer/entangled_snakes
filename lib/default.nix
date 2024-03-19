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

  messages = import ./messages.nix {
    inherit lib;
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
    validated = self.constraints.validate {
      inherit project python;
      extras = extras';
    };
    fromNixpkgs =
      map (dependency: let
        drv = python.pkgs.${dependency.pname};
        inherit (dependency) pname extras;
        inherit (drv) version;
      in  {
        inherit pname version extras;
        drv = drv.drvPath;
        pin = "${pname}==${version}";
      })
      validated.right;
    fromNixpkgsCount = builtins.length fromNixpkgs;
    toFetch = map (dep:
      dep // { pin = lib.concatMapStringsSep " " (c: "${dep.name}${c.op}${self.messages.formatVersion c.version}") dep.conditions; }
    ) validated.wrong;
    toFetchCount = builtins.length toFetch;

  in {
    inherit fromNixpkgs toFetch;
    info = lib.concatStringsSep "\n" ([
        "# ${project.pyproject.project.name or "unnamed project"} at ${projectRoot}"
    ]
    ++ lib.optionals (fromNixpkgsCount > 0) [
        "\n## The following ${toString fromNixpkgsCount} dependencies will be re-used from the current package set:"
        "- ${lib.concatMapStringsSep "\n- " (d: "${d.pname} ${d.version}") fromNixpkgs}"
    ]
    ++ lib.optionals (toFetchCount > 0) [
        "\n## The following ${toString toFetchCount} dependencies need to be locked:"
        "- ${lib.concatMapStringsSep "\n- " self.messages.formatFailure toFetch}"
    ]);
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
    then {
      error = ''
        build requirements could not be satisfied by the current package set:
         - ${lib.concatMapStringsSep "\n- " self.messages.formatFailure validated.wrong}
      '';
    }
    else {
      success = (python.withPackages(ps: map (d: ps.${d.pname}) validated.right)).drvPath;
    };
})
