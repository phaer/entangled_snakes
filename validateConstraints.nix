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


  validateConstraints = {
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
    flatDeps = filteredDeps.dependencies ++ flatten (lib.attrValues filteredDeps.extras) ++ filteredDeps.build-systems;
  in
    lib.foldl'
      (acc: validator:
        let
          result = lib.partition (x: !(x ? "failure")) (map validator acc.right);
        in
        { right = result.right; wrong = acc.wrong ++ result.wrong; }
      )
      { right = flatDeps; wrong = []; }
      validators';


  validateExistenceInPackageSet = {python}: dependency: let
    pname = pypa.normalizePackageName dependency.name;
  in
    if lib.hasAttr pname python.pkgs
    then dependency
    else
      {
        failure.existence = {
          name = pname;
        };
      }
  ;

  validateVersionConstraints = {python}: dependency: let
    pname = pypa.normalizePackageName dependency.name;
    pversion = python.pkgs.${pname}.version;
    version = pep440.parseVersion python.pkgs.${pname}.version;
    incompatible = lib.filter (cond: ! pep440.comparators.${cond.op} version cond.version) dependency.conditions;
  in
    if incompatible == []
    then dependency
    else
      {
        failure.version = {
          name = pname;
          version = pversion;
          conditions = incompatible;
        };
      };

  /*
  Checks whether pkgs.python contains all extras declared in the parsed project.
  */
  validateExtrasConstraints = {python}: dependency: let
    pname = pypa.normalizePackageName dependency.name;
    pkg = python.pkgs.${pname};
    optionalDeps = pkg.passthru.optional-dependencies or {};
    known = lib.filter (extra: optionalDeps ? extra) dependency.extras;
    missing = lib.filter (extra: (lib.subtractLists pkg.propagatedBuildInputs optionalDeps.${extra}) != []) known;
    unknown = lib.subtractLists known dependency.extras;
  in
    if missing == [] || unknown == []
    then dependency
    else
      {
        failure.extra = {
          name = pname;
          inherit missing;
          inherit unknown;
        };
      };
})
