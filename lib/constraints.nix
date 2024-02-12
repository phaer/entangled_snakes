{
  lib,
  pep440,
  pep508,
  pep621,
  pypa,
  ...
}:
lib.fix (self: let
  inherit (lib) flatten;
in {
  validators = [
    self.validateExistenceInPackageSet
    self.validateVersionConstraints
    self.validateExtrasConstraints
  ];

  validate = {
    # Project metadata as returned by `lib.project.loadPyproject`
    project,
    # Python derivation
    python,
    # Python extras (optionals) to enable
    extras ? [],
    validators ? self.validators,
  }: let
    filteredDeps = pep621.filterDependencies {
      inherit (project) dependencies;
      environ = pep508.mkEnviron python;
      inherit extras;
    };
    validators' = map (fn: fn {inherit python;}) validators;
    flatDeps =
      map (dep: dep // {pname = pypa.normalizePackageName dep.name;})
      (filteredDeps.dependencies ++ flatten (lib.attrValues filteredDeps.extras) ++ filteredDeps.build-systems);
  in
    lib.foldl'
    (
      acc: validator: let
        result = lib.partition (x: !(x ? "failure")) (map validator acc.right);
      in {
        inherit (result) right;
        wrong = acc.wrong ++ result.wrong;
      }
    )
    {
      right = flatDeps;
      wrong = [];
    }
    validators';

  validateExistenceInPackageSet = {python}: dependency:
    if lib.hasAttr dependency.pname python.pkgs
    then dependency
    else
      dependency
      // {
        failure = {
          type = "existence";
        };
      };

  validateVersionConstraints = {python}: dependency: let
    pversion = python.pkgs.${dependency.pname}.version;
    version = pep440.parseVersion python.pkgs.${dependency.pname}.version;
    incompatible = lib.filter (cond: ! pep440.comparators.${cond.op} version cond.version) dependency.conditions;
  in
    if incompatible == []
    then dependency
    else
      dependency
      // {
        failure = {
          type = "version";
          found = pversion;
          inherit incompatible;
        };
      };

  /*
  Checks whether pkgs.python contains all extras declared in the parsed project.
  */
  validateExtrasConstraints = {python}: dependency: let
    pkg = python.pkgs.${dependency.pname};
    optionalDeps = pkg.passthru.optional-dependencies or {};
    found = lib.filter (extra: optionalDeps ? extra) dependency.extras;
    missing = lib.filter (extra: (lib.subtractLists pkg.propagatedBuildInputs optionalDeps.${extra}) != []) found;
    unknown = lib.subtractLists found dependency.extras;
  in
    if missing == [] || unknown == []
    then dependency
    else
      dependency
      // {
        failure = {
          type = "extra";
          inherit found;
          inherit missing;
          inherit unknown;
        };
      };
})
