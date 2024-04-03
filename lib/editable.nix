{lib}: {
  python,
  project,
}: let
  projectRoot =
    if lib.isString project.projectRoot
    then project.projectRoot
    else
      throw ''
        projectRoot needs to be a string in makeEditable, because we need a
        reference to the working directory, outside the nix store, for a correct
        editable install.
      '';
  # Default to setuptools legacy as per PEP517
  requires' = project.pyproject.build-system.requires or ["setuptools"];
  # Packages using setuptools often implicitly require "wheel" to create
  # the .dist-info directory.
  requires = requires' ++ lib.optionals (lib.elem "setuptools" requires') ["wheel"];
  backend = project.pyproject.build-system.build-backend or "setuptools.build_meta.__legacy__";
  backendImport =
    if backend == "setuptools.build_meta.__legacy__"
    then "setuptools.build_meta"
    else backend;
  # Lookup our build-requirements in nixpkgs. This is
  # to naive at the moment
  # TODO use lib.makeBuildEnvironment
  makePythonPath = python: requirements:
    lib.concatMapStringsSep
    ":"
    (
      name: let
        p = python.pkgs.${name};
      in "${p}/${python.sitePackages}"
    )
    (["python"] ++ requirements);
  editable = builtins.derivation {
    inherit (python.stdenv) system;
    name = "${project.pyproject.project.name or "unnamed"}-editable";
    # TODO filter source here to avoid unecessary rebuilds
    src = /. + projectRoot;
    builder = "${python}/bin/python";
    # Editable wheels are local by definition.
    preferLocalBuild = true;
    allowSubstitutes = false;

    PYTHONPATH = makePythonPath python requires;
    inherit backend backendImport projectRoot;
    inherit (python) sitePackages;
    args = [./editable.py];
  };
in
  editable.drvPath
