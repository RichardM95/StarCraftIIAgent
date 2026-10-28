"""Create per-task policy artifacts outside the worker-readable directory."""
import json
import shutil
from pathlib import Path
import yaml
from .runtime import ROOT


def make_policy(run_dir: Path, workspace: Path, *, goal: str, allowed_files: list[str],
                constraints: list[str] | None = None, acceptance: str = "",
                enhanced: bool = False, max_tool_calls: int = 200, retain_tokens: int | None = None,
                plugin: Path | None = None, profile: str = "default"):
    run_dir.mkdir(parents=True, exist_ok=True)
    contract = {"workspace": str(workspace.resolve()), "goal": goal, "allowed_files": allowed_files,
                "constraints": constraints or [], "acceptance": acceptance, "max_tool_calls": max_tool_calls,
                "profile": profile}
    (run_dir / "contract.json").write_text(json.dumps(contract, ensure_ascii=False, indent=2), encoding="utf-8")
    plugin_copy = run_dir / "task-policy.mjs"
    if plugin is not None:
        plugin_copy = run_dir / plugin.name
        if plugin.name != "task-policy.mjs":
            base_copy = run_dir / "task-policy.mjs"
            if not base_copy.exists():
                shutil.copy2(ROOT / "plugins/task-policy.mjs", base_copy)
    if not plugin_copy.exists():
        shutil.copy2(plugin or ROOT / "plugins/task-policy.mjs", plugin_copy)
    patch = [{"insert": [{"id": "supervisor-task-policy", "name": str(plugin_copy),
              "config": {"contractPath": str(run_dir / "contract.json"), "auditPath": str(run_dir / "audit.jsonl"),
                "checkpointPath": str(run_dir / "checkpoint.json"), "controlPath": str(run_dir / "control.json"),
                "controlResultPath": str(run_dir / "control-result.json"), "enhanced": enhanced}}]}]
    if retain_tokens is not None:
        patch.append({"id": "compaction-basic", "config": {"retainTokens": retain_tokens}})
    destination = run_dir / "policy.patch.yml"
    destination.write_text(yaml.safe_dump(patch, allow_unicode=True, sort_keys=False), encoding="utf-8")
    return destination
