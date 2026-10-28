"""Archive the evaluated v1 policy before making any later production improvements."""
import hashlib
import json
import shutil
from .runtime import ROOT


def main():
    plugin = ROOT / "plugins/task-policy.mjs"
    target = ROOT / "releases/policy-v1.mjs"
    target.parent.mkdir(exist_ok=True)
    if target.exists():
        raise RuntimeError("Baseline archive already exists; do not overwrite evidence")
    shutil.copy2(plugin, target)
    for batch in (ROOT / "state/evaluations").iterdir():
        if batch.name.startswith("pilot"):
            continue
        summary_path = batch / "summary.json"
        if not summary_path.exists():
            raise RuntimeError("Finish batch before archiving: " + batch.name)
        summary = json.loads(summary_path.read_text(encoding="utf-8"))
        manifest_path = batch / "manifest.json"
        manifest = json.loads(manifest_path.read_text(encoding="utf-8")) if manifest_path.exists() else {}
        manifest.update(expected_total=summary["total"], harness_version="0.2.0-rc.2",
                        plugin_sha256=hashlib.sha256(target.read_bytes()).hexdigest(),
                        archived_plugin=str(target), provenance="v1 policy archived after batch completion, before any policy change")
        manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print(json.dumps({"archived_plugin": str(target)}))


if __name__ == "__main__":
    main()
