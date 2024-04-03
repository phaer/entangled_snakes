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
    if backend != "setuptools.build_meta.__legacy__"
    then backend
    else "setuptools.build_meta";
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
    PYTHONPATH = makePythonPath python requires;
    builder = "${python}/bin/python";
    # Editable wheels are local by definition.
    preferLocalBuild = true;
    allowSubstitutes = false;
    args = [
      "-c"
      ''
          import os
          import json
          import shutil
          import importlib.metadata
          from pathlib import Path
          import ${backendImport};

          out = Path(os.getenv("out"))
          out.mkdir()
          site_packages = out / "${python.sitePackages}"
          site_packages.mkdir(parents=True)

          src = Path(os.getenv("src"))

          editable_source = Path("${projectRoot}")
          # TODO Replace this by a better heuristic to find out whether the
          # current project uses src layout or not.
          # We check "src" (in the nix store) because editable_source isn't accessible
          # in the sandbox
          if (src / "src").exists():
            editable_source = editable_source / "src"

          os.chdir(src)
          # Call the build-backend as per PEP660
          dist_info = ${backend}.prepare_metadata_for_build_editable(site_packages)

          # remove .egg_info if it exists, as it's unecessary and might confuse other tools.
          for egg_info in site_packages.glob("*.egg-info"):
            shutil.rmtree(egg_info)

          # write direct_url.json as per PEP 660
          direct_json_path = site_packages / dist_info / "direct_url.json"
          with open(direct_json_path, 'w') as f:
            data = {
              "url": f"file://{editable_source}",
              "dir_info": {
                "editable": True
              }
            }
            json.dump(data, f, indent=2)

          # write .pth file, commented out because we don't
          # use it atm.
          pth_path = (site_packages / dist_info).with_suffix('.pth')
          with open(pth_path, 'w') as f:
            f.write(f"{editable_source}\n")

          # get toplevel modules
          with open(site_packages / dist_info / "top_level.txt", "r") as f:
            top_level_modules = [l.strip() for l in f.readlines()]

          # get console_scripts from entrypoints
          distribution = importlib.metadata.Distribution.at(site_packages / dist_info)
          console_scripts = distribution.entry_points.select(group='console_scripts')
          # TODO support other entrypoints

          # TODO shellhook
          with open(out / "shellHook.sh", "w") as f:
            aliases = "\n".join([
              f"alias {script.name}='${python}/bin/python -m {script.value}'; echo '- {script.name}'"
              for script in console_scripts])
            imports = "\n".join([
              f"${python}/bin/python -c \"import {module}; print('- {module} ->', {module}.__path__[0])\""
              for module in top_level_modules
            ])
            f.write(f"""
              export PYTHONPATH={site_packages}:$PYTHONPATH
              echo console_scripts:
              {aliases}
              echo modules:
              {imports}
            """)
        ''
    ];
  };
in
  editable.drvPath
