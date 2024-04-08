# Run pyproject_hooks hooks to gather metadata and/or
# build wheels inside the nix sandbox.
import os
import stat
import shutil
from tempfile import TemporaryDirectory
from pathlib import Path

import pyproject_hooks

name = os.environ["name"]
with TemporaryDirectory(
     suffix=f"metadata-preparation-{name}"
) as temp_dir:

  # pyproject_hooks expect a writable directory, so we copy everything and allow writes.
  shutil.copytree(os.environ["src"], temp_dir, symlinks=True, dirs_exist_ok=True)
  os.chdir(temp_dir)
  for root, dirs, files in os.walk(temp_dir):
    for directory in dirs:
      path = Path(root) / directory
      perms = os.stat(path).st_mode
      path.chmod(perms | stat.S_IWUSR)

  backend = pyproject_hooks.BuildBackendHookCaller(
    source_dir = temp_dir,
    build_backend = os.environ["buildSystem"],
  )

  out = Path(os.environ["out"])
  out.mkdir()
  hook = os.environ["hook"]
  if hook in [
          'prepare_metadata_for_build_wheel',
          'prepare_metadata_for_build_editable',
          'build_sdist',
          'build_wheel',
          'build_editable'
  ]:
      result = getattr(backend, hook)(out)
      (out / "output").symlink_to(result)
