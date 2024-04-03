import os
import json
import shutil
import importlib
import importlib.metadata
from pathlib import Path

backend_package = importlib.import_module(os.environ["backendImport"])
backend_package_name = backend_package.__name__
backend_module_name = os.environ["backend"].removeprefix(backend_package_name)

backend = backend_package
if len(backend_module_name):
    for k in filter(None, backend_module_name.split(".")):
        backend = getattr(backend, k)

out = Path(os.environ["out"])
out.mkdir()
site_packages = out / os.environ["sitePackages"]
site_packages.mkdir(parents=True)

src = Path(os.environ["src"])

editable_source = Path(os.environ["projectRoot"])
# TODO Replace this by a better heuristic to find out whether the
# current project uses src layout or not.
# We check "src" (in the nix store) because editable_source isn't accessible
# in the sandbox
if (src / "src").exists():
    editable_source = editable_source / "src"

os.chdir(src)
# Call the build-backend as per PEP660
dist_info = backend.prepare_metadata_for_build_editable(site_packages)

# remove .egg_info if it exists, as it's unecessary and might confuse other tools.
for egg_info in site_packages.glob("*.egg-info"):
    shutil.rmtree(egg_info)

# write direct_url.json as per PEP 660
direct_json_path = site_packages / dist_info / "direct_url.json"
with open(direct_json_path, "w") as f:
    data = {"url": f"file://{editable_source}", "dir_info": {"editable": True}}
    json.dump(data, f, indent=2)

# write .pth file, commented out because we don't
# use it atm.
pth_path = (site_packages / dist_info).with_suffix(".pth")
with open(pth_path, "w") as f:
    f.write(f"{editable_source}\n")

# get toplevel modules
with open(site_packages / dist_info / "top_level.txt", "r") as f:
    top_level_modules = [line.strip() for line in f.readlines()]

# get console_scripts from entrypoints
distribution = importlib.metadata.Distribution.at(site_packages / dist_info)
console_scripts = distribution.entry_points.select(group="console_scripts")
# TODO support other entrypoints

with open(out / "shellHook.sh", "w") as f:
    aliases = "\n".join(
        [
            f"alias {script.name}='python -m {script.value}'; echo '- {script.name}'"
            for script in console_scripts
        ]
    )
    imports = "\n".join(
        [
            f"python -c \"import {module}; print('- {module} ->', {module}.__path__[0])\""
            for module in top_level_modules
        ]
    )
    f.write(
        f"""
    export PYTHONPATH={site_packages}:{editable_source}:$PYTHONPATH
    echo "modules:"
    {imports}
    echo "console_scripts:"
    {aliases}
  """
    )
