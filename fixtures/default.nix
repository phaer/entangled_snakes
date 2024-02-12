{
  lib,
  pyproject,
  constraints,
  loadProject,
}: let
  overrides = {
    requirements_txt.pyproject.project = {
      name = "requirements.txt";
      version = "0.1";
    };
    # FIXME error by default, but document overriding or using ifd
    # to acquire dynamic versions
    pyproject_simple.pyproject.project.version = "0.1";
    pyproject_complex.pyproject.project.version = "0.1";
  };
  names =
    lib.attrNames
    (lib.filterAttrs
      (_: v: v == "directory")
      (builtins.readDir ./.));
  projects =
    lib.genAttrs names (path: loadProject ./${path});

  packages = python:
    lib.mapAttrs
    (
      name: project:
        python.pkgs.buildPythonPackage
        (
          pyproject.renderers.buildPythonPackage {
            inherit python;
            project = lib.recursiveUpdate project (overrides.${name} or {});
          }
        )
    )
    projects;

  dependenciesToFetch = python: extras:
    lib.mapAttrs
    (
      _name: project:
        constraints.validate {
          inherit project python extras;
        }
    )
    projects;
in {
  inherit names projects packages dependenciesToFetch;
}
