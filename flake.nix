{
  inputs = {
    nixpkgs.url = "github:nixos/nixpkgs/nixos-unstable";

    flake-parts.url = "github:hercules-ci/flake-parts";
    flake-parts.inputs.nixpkgs-lib.follows = "nixpkgs";

    treefmt-nix.url = "github:numtide/treefmt-nix";
    treefmt-nix.inputs.nixpkgs.follows = "nixpkgs";
    pre-commit-hooks-nix.url = "github:cachix/pre-commit-hooks.nix";
    pre-commit-hooks-nix.inputs.nixpkgs.follows = "nixpkgs";

    pyproject-nix.url = "github:nix-community/pyproject.nix";
    pyproject-nix.inputs.nixpkgs.follows = "nixpkgs";
  };

  outputs = inputs @ {
    nixpkgs,
    flake-parts,
    pyproject-nix,
    ...
  }:
    flake-parts.lib.mkFlake {inherit inputs;} ({self, ...}: {
      # Currently tested systems are Linux on x86_64 and macOS on arm.
      systems = ["x86_64-linux" "aarch64-darwin"];
      # treefmt allows us to do liniting with 'nix fmt' and to require it in
      # 'nix flake check', see perSystem.treefmt below for config
      imports = [
        inputs.treefmt-nix.flakeModule
        inputs.pre-commit-hooks-nix.flakeModule
      ];

      flake.lib = import ./lib/default.nix {
        inherit (nixpkgs) lib;
        pyproject = pyproject-nix.lib;
      };

      perSystem = {
        self',
        lib,
        pkgs,
        ...
      }: let
        # We could use 'projectRoot = ./.;' here, but that would mean
        # that the input for our python environment would change every
        # time any file in our git repo changes, and trigger a rebuild.
        # So we filter the files using 'nixpkgs.lib.fileset' and
        # copy them to a dedicated storePath.
        projectRoot = let
          fs = lib.fileset;
        in
          fs.toSource {
            root = ./.;
            fileset =
              # fs.traceVal  # remove the first '#' to get a trace
              # of the resulting store path and it's content
              fs.difference
              (fs.fromSource (lib.sources.cleanSource ./.))
              (fs.unions [
                (fs.maybeMissing ./result)
                (fs.maybeMissing ./.gitignore)
                (fs.maybeMissing ./.envrc)
              ]);
          };

        # Load pyproject.toml metadata from the root directory of the
        # this flake, after copying that to the nix store.
        project = inputs.pyproject-nix.lib.project.loadPyproject {
          inherit projectRoot;
        };

        args = {
          # A python interpreter taken from our flake outputs, or straight from pkgs.python3.
          inherit (self'.packages) python;
          # Our project as represented by pyproject-nix and loaded above.
          inherit project;
        };
        withPackagesArgs =
          inputs.pyproject-nix.lib.renderers.withPackages
          (args
            // {
              extras = ["dev"];
            });
        pythonEnv = args.python.withPackages withPackagesArgs;

        buildPythonPackageArgs =
          (project.renderers.buildPythonPackage args)
          // {
            # Copy nix code to the built derivation, so that python can call it
            # during runtime.
            postInstall = ''
              cp -rv "$src/flake.nix" "$src/flake.lock" "$src/lib" $out
            '';
          };
        entangledSnakes = args.python.pkgs.buildPythonPackage buildPythonPackageArgs;
      in {
        devShells.default = pkgs.mkShell {
          packages = [pythonEnv];

          shellHook = ''
            editable="$(nix run .# -- make-editable "$(pwd)")"
            source "$editable/shellHook.sh"
          '';
        };

        packages = {
          default = entangledSnakes;
          inherit entangledSnakes;

          python = pkgs.python3.override {
            self = pkgs.python3;
            packageOverrides = self: super: {
              # pdm and maturin are exposed as a toplevel package (pkgs.pdm)
              # in nixpkgs, but exposes all required python attributes, so we
              # add them to our package set here, as we might need them for
              # resolving.
              pdm = self.toPythonModule pkgs.pdm;
              maturin = self.toPythonModule pkgs.maturin;

              # https://github.com/NixOS/nixpkgs/pull/253239
              resolvelib = let
                version = "1.0.1";
              in
                super.resolvelib.overridePythonAttrs {
                  inherit version;
                  src = pkgs.fetchFromGitHub {
                    owner = "sarugaku";
                    repo = "resolvelib";
                    rev = "/refs/tags/${version}";
                    hash = "sha256-oxyPn3aFPOyx/2aP7Eg2ThtPbyzrFT1JzWqy6GqNbzM=";
                  };
                };

            };
          };
        };

        treefmt = {
          projectRootFile = "flake.lock";

          # Shell
          programs.shellcheck.enable = true;

          # Nix
          programs.deadnix.enable = true;
          programs.statix.enable = true;
          programs.alejandra.enable = true;

          # Python
          programs.mypy.enable = true;
          programs.mypy.directories."./src" = {
            options = ["--strict" "-m"];
            modules = ["entangled_snakes"];
          };
          programs.black.enable = true;
          programs.ruff.enable = true;
        };
      };
    });
}
