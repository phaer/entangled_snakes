{lib}:
lib.fix (self: {
  formatVersion = {
    dev ? null,
    epoch ? 0,
    local ? null,
    post ? null,
    pre ? null,
    release ? [],
  }:
    lib.concatStrings [
      (lib.optionalString (epoch != 0) "${toString epoch}!")
      (lib.concatStringsSep "." (map toString release))
      (lib.concatStringsSep "." (lib.filter (x: x != "") [
        (lib.optionalString (pre != null) "${pre.type}${toString pre.value}")
        (lib.optionalString (post != null) "${post.type}${toString post.value}")
        (lib.optionalString (dev != null) "${dev.type}${toString dev.value}")
      ]))
    ];

  formatCondition = condition: "${condition.op}${self.formatVersion condition.version}";

  formatVersionFailure = failure: [
      "version ${failure.found} does not match constraints:"
      (lib.concatMapStringsSep ", " self.formatCondition failure.incompatible)
    ];
  formatExistenceFailure = failure:
    if failure.evaluationError
    then "failed to evaluate"
    else "does not exist";
  formatExtraFailure = failure:
    with failure;
    if missing != []
    then ["is configured without extras:" (lib.concatStringsSep ", " missing)]
    else if unknown != []
    then ["does not know about extras:" (lib.concatStringsSep ", " unknown)]
    else throw "Unhandled extra failure";

  formatFailure = dependency: let
    type = dependency.failure.type;
  in
    lib.concatStringsSep " "
      (lib.flatten [
        "${dependency.pname}"
        ((if type == "version"
          then self.formatVersionFailure
          else if type == "existence"
          then self.formatExistenceFailure
          else if type == "extra"
          then self.formatExtraFailure
          else throw "Unhandled failure type: ${type}")
          dependency.failure)
      ]);


  #failure.
})
