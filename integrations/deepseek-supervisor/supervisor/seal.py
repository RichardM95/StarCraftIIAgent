"""Save reproducible dependency/source manifests without including credentials or task inputs."""
import hashlib
import importlib.metadata
import json
import zipfile
from pathlib import Path
from .runtime import ROOT


def main():
    destination = ROOT / "releases"
    destination.mkdir(exist_ok=True)
    selected = []
    for pattern in ("supervisor/*.py", "supervisor/*.cjs", "plugins/*.mjs", "profiles/*.yml", "profiles/*.md", "tests/*.py", "tests/*.mjs",
                    "state/mode-inspection/*.yml", "state/mode-inspection/manifest.json", "reports/modes.*",
                    "releases/mode_evaluate-native-v1.py",
                    "packets/*.json", "*.md", "pyproject.toml", "config.json"):
        selected.extend(ROOT.glob(pattern))
    files = {p.relative_to(ROOT).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
             for p in sorted(set(selected)) if p.is_file()}
    dependencies = sorted((dist.metadata["Name"], dist.version) for dist in importlib.metadata.distributions()
                          if dist.metadata["Name"].lower() != "deepseek-supervisor")
    lock = ROOT / "requirements.lock.txt"
    lock.write_text("\n".join(f"{name}=={version}" for name, version in dependencies) + "\n", encoding="utf-8")
    files[lock.name] = hashlib.sha256(lock.read_bytes()).hexdigest()
    manifest = {"harness_version": "0.2.0-rc.2", "python": "3.12", "files": files,
                "credentials_included": False, "task_inputs_included": False}
    release_id = hashlib.sha256(json.dumps(files, sort_keys=True).encode()).hexdigest()[:12]
    manifest_path = destination / (release_id + ".json")
    manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    archive = destination / ("deepseek-supervisor-" + release_id + ".zip")
    with zipfile.ZipFile(archive, "w", zipfile.ZIP_DEFLATED) as bundle:
        for name in files:
            bundle.write(ROOT / name, name)
        bundle.write(manifest_path, "source-manifest.json")
    print(json.dumps({"archive": str(archive), "manifest": str(manifest_path)}))


if __name__ == "__main__":
    main()
