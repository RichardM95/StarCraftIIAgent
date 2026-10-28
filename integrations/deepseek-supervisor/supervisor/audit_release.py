"""Inspect release invariants and scan generated text for existing credential values without printing them."""
import hashlib
import json
import os
import tomllib
from pathlib import Path
import yaml
from .runtime import ROOT


def strings(value):
    if isinstance(value, str):
        yield value
    elif isinstance(value, dict):
        for child in value.values():
            yield from strings(child)
    elif isinstance(value, list):
        for child in value:
            yield from strings(child)


def main():
    codex = Path(os.environ["CODEX_HOME"])
    backup = ROOT / "backups/20261008-initial"
    before = tomllib.loads((backup / "config.toml").read_text(encoding="utf-8"))
    after = tomllib.loads((codex / "config.toml").read_text(encoding="utf-8"))
    service = after["mcp_servers"].pop("deepseek-supervisor")
    assert before == after, "Unrelated Codex settings changed"
    assert Path(service["command"]).is_file()
    original_rules = (backup / "AGENTS.md").read_text(encoding="utf-8").strip()
    current_rules = (codex / "AGENTS.md").read_text(encoding="utf-8").split("# DeepSeek 自主协作")[0].strip()
    assert original_rules == current_rules, "Unrelated global instructions changed"
    credential = yaml.safe_load(Path(os.environ["DEEPSEEK_CREDENTIALS_PATH"]).read_text(encoding="utf-8"))
    candidates = [s.encode("utf-8") for s in strings(credential.get("refs", {}).get("DEEPSEEK_API_KEY")) if len(s) >= 20]
    matches = []
    scanned = 0
    for path in ROOT.rglob("*"):
        relative = path.relative_to(ROOT)
        if any(part in (".venv", "backups", "__pycache__", ".git") for part in relative.parts):
            continue
        if not path.is_file() or path.suffix not in (".json", ".jsonl", ".yml", ".yaml", ".md", ".toml"):
            continue
        scanned += 1
        data = path.read_bytes()
        if any(value in data for value in candidates):
            matches.append(str(relative))
    report = {"unrelated_codex_settings_preserved": True, "original_global_rules_preserved": True,
              "credential_candidate_values_checked": len(candidates), "text_files_scanned": scanned,
              "credential_match_files": matches, "scan_limit": "Exact configured credential values only; not a proof against every encoding or hostile local process",
              "plugin_sha256": hashlib.sha256((ROOT / "plugins/task-policy.mjs").read_bytes()).hexdigest()}
    (ROOT / "reports/release-audit.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report))
    assert not matches, "Credential match found; inspect locally without printing values"


if __name__ == "__main__":
    main()
