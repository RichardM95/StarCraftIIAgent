"""Pin pre-snapshot v1 runs to the archived exact plugin, preserving their original patch file."""
import json
import shutil
import yaml
from .runtime import ROOT


def main():
    archive = ROOT / "releases/policy-v1.mjs"
    changed = []
    for directory in list((ROOT / "state/tasks").iterdir()) + list((ROOT / "state/evaluations").glob("*-v1/*")):
        patch = directory / "policy.patch.yml"
        snapshot = directory / "task-policy.mjs"
        if not patch.is_file() or snapshot.exists():
            continue
        data = yaml.safe_load(patch.read_text(encoding="utf-8"))
        matches = [entry for operation in data for entry in operation.get("insert", [])
                   if entry.get("id") == "supervisor-task-policy"]
        if len(matches) != 1:
            continue
        shutil.copy2(archive, snapshot)
        shutil.copy2(patch, directory / "policy.initial.patch.yml")
        matches[0]["name"] = str(snapshot)
        patch.write_text(yaml.safe_dump(data, allow_unicode=True, sort_keys=False), encoding="utf-8")
        changed.append(str(directory))
    (ROOT / "reports/legacy-plugin-pinning.json").write_text(json.dumps({"source": str(archive),
        "pinned": changed, "original_patch_preserved": True}, indent=2), encoding="utf-8")
    print(json.dumps({"legacy_runs_pinned": len(changed)}))


if __name__ == "__main__":
    main()
