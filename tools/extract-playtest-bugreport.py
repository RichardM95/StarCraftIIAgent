#!/usr/bin/env python3
"""Extract deduplicated SC2 playtest errors/warnings into bugreport.txt."""
from __future__ import annotations

import argparse
import os
import re
import sys
from dataclasses import dataclass
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
from sc2_paths import project_data_dir, ensure_project_data

SESSION_SUFFIXES = (" Alerts.txt", " ScriptError.txt")
SESSION_WINDOW_SEC = 600

HEADER_LINE_RE = re.compile(r"^=+\s*$")
METADATA_RE = re.compile(
    r"^(?:Executable|Parent Executable|Grandparent Executable|LocalTime|"
    r"<(?:Parameters|ComputerUser|ComputerName|Exe\.Architecture|Version|"
    r"DataBuild|CodeBranch|CodeRevision|Locale\.(?:Assets|Data|Install)|"
    r"AccountCountry|AgentVersion)>|StarCraft II \()"
)
ALERTS_PREFIX_RE = re.compile(
    r"^(?:USER\s+\d+\s+[\d.]+\s+[\d.]+\s+)?"
)
ALERTS_USER_RE = re.compile(r"^USER\s+")
ALERTS_SCOPE_RE = re.compile(r"\[\s*[0-9a-fA-F]+\s+[0-9a-fA-F]+\s*\]\s*")
NEAR_LINE_RE = re.compile(
    r"^\s*Near line (\d+) in ([^(]+)\(\) in (.+)$"
)
COMPILE_ERROR_RE = re.compile(
    r"^Script compile error:\s*(.+?)\s*\((\d+)\),\s*(.+)$"
)

# Editor map tests cannot authorize vanilla LotV campaign APIs in Blizzard libs.
NOT_AUTHORIZED_RE = re.compile(r"Calling '[^']+' is not authorized")
VOID_CAMPAIGN_LIB_RE = re.compile(
    r"in TriggerLibs/(?:VoidCampaignLib|VoidCampaignMissionLib)\.galaxy\s*$",
    re.MULTILINE,
)


@dataclass(frozen=True)
class LogFile:
    path: Path
    kind: str
    mtime: float


def default_logs_dirs() -> list[Path]:
    home = Path.home()
    return [
        home / "OneDrive" / "Dokumente" / "StarCraft II" / "GameLogs",
        home / "Documents" / "StarCraft II" / "GameLogs",
        home / "OneDrive" / "Documents" / "StarCraft II" / "GameLogs",
    ]


def resolve_logs_dir(explicit: str | None) -> Path:
    if explicit:
        path = Path(explicit).expanduser()
        if not path.is_dir():
            raise SystemExit(f"GameLogs directory not found: {path}")
        return path

    env = os.environ.get("SC2_GAMELOGS_PATH")
    if env:
        path = Path(env).expanduser()
        if path.is_dir():
            return path

    for candidate in default_logs_dirs():
        if candidate.is_dir():
            return candidate

    raise SystemExit(
        "Could not find StarCraft II GameLogs directory. "
        "Pass --logs-dir or set SC2_GAMELOGS_PATH."
    )


def list_session_logs(logs_dir: Path) -> list[LogFile]:
    found: list[LogFile] = []
    for entry in logs_dir.iterdir():
        if not entry.is_file():
            continue
        name = entry.name
        kind: str | None = None
        if name.endswith(" Alerts.txt"):
            kind = "alerts"
        elif name.endswith(" ScriptError.txt"):
            kind = "script_error"
        else:
            continue
        found.append(
            LogFile(
                path=entry,
                kind=kind,
                mtime=entry.stat().st_mtime,
            )
        )
    return found


def pick_session_logs(
    logs_dir: Path,
    logs: list[LogFile],
    since: float | None = None,
) -> tuple[LogFile | None, LogFile | None]:
    if not logs:
        return None, None

    if since is not None:
        window_start = since - 5.0
    else:
        # Reference time is the newest file in the GameLogs directory (e.g. SystemInfo.txt, Graphics.txt)
        all_txt = [f for f in logs_dir.glob("*.txt") if f.is_file()]
        if all_txt:
            ref_time = max(f.stat().st_mtime for f in all_txt)
        else:
            ref_time = max(item.mtime for item in logs)
        window_start = ref_time - SESSION_WINDOW_SEC

    in_window = [item for item in logs if item.mtime >= window_start]
    if not in_window:
        return None, None

    alerts = max(
        (item for item in in_window if item.kind == "alerts"),
        key=lambda item: item.mtime,
        default=None,
    )
    script_error = max(
        (item for item in in_window if item.kind == "script_error"),
        key=lambda item: item.mtime,
        default=None,
    )
    return alerts, script_error


def read_text(path: Path) -> list[str]:
    for encoding in ("utf-8-sig", "utf-8", "cp1252"):
        try:
            return path.read_text(encoding=encoding).splitlines()
        except UnicodeDecodeError:
            continue
    return path.read_text(encoding="utf-8", errors="replace").splitlines()


def is_cutscene_noise(message: str) -> bool:
    lowered = message.lower()
    return "cutscene" in lowered or ".sc2cutscene" in lowered


def is_header_or_noise(line: str) -> bool:
    stripped = line.strip()
    if not stripped:
        return True
    if HEADER_LINE_RE.match(stripped):
        return True
    if METADATA_RE.match(stripped):
        return True
    if stripped == "Final report for this error this game.":
        return True
    return False


def canonical_alert_message(line: str) -> str | None:
    stripped = ALERTS_PREFIX_RE.sub("", line).strip()
    stripped = ALERTS_USER_RE.sub("", stripped).strip()
    if not stripped or HEADER_LINE_RE.match(stripped):
        return None
    if METADATA_RE.match(stripped):
        return None
    while True:
        next_value = ALERTS_SCOPE_RE.sub("", stripped, count=1)
        if next_value == stripped:
            break
        stripped = next_value.strip()
    return stripped or None


def parse_script_errors(lines: list[str]) -> list[str]:
    entries: list[str] = []
    seen: set[str] = set()
    i = 0
    while i < len(lines):
        line = lines[i].rstrip()
        i += 1
        if is_header_or_noise(line):
            continue

        compile_match = COMPILE_ERROR_RE.match(line.strip())
        if compile_match:
            file_path, line_no, message = compile_match.groups()
            entry = f"Compile error: {file_path} ({line_no}): {message}"
            if i < len(lines) and lines[i].lstrip().startswith("Script code:"):
                code = lines[i].split(":", 1)[1].strip()
                entry = f"{entry}\n  Code: {code}"
                i += 1
            key = entry
            if key not in seen and not is_cutscene_noise(entry):
                seen.add(key)
                entries.append(entry)
            continue

        if line.startswith("Script load failed:"):
            entry = line.strip()
            if entry not in seen and not is_cutscene_noise(entry):
                seen.add(entry)
                entries.append(entry)
            continue

        if line.startswith("Trigger Error in "):
            entry = line.strip()
            if i < len(lines):
                near = lines[i].rstrip()
                near_match = NEAR_LINE_RE.match(near)
                if near_match:
                    line_no, func, galaxy_path = near_match.groups()
                    entry = (
                        f"{entry}\n"
                        f"  at line {line_no} in {func.strip()}() "
                        f"in {galaxy_path.strip()}"
                    )
                    i += 1
            key = entry
            if key not in seen and not is_cutscene_noise(entry):
                seen.add(key)
                entries.append(entry)
            continue

        stripped = line.strip()
        if stripped and not stripped.startswith("Script code:"):
            if stripped not in seen and not is_cutscene_noise(stripped):
                seen.add(stripped)
                entries.append(stripped)

    return entries


def is_editor_void_campaign_noise(entry: str) -> bool:
    return bool(
        NOT_AUTHORIZED_RE.search(entry) and VOID_CAMPAIGN_LIB_RE.search(entry)
    )


def filter_script_errors(entries: list[str]) -> tuple[list[str], int]:
    kept: list[str] = []
    skipped = 0
    for entry in entries:
        if is_editor_void_campaign_noise(entry):
            skipped += 1
            continue
        kept.append(entry)
    return kept, skipped


def parse_alerts(lines: list[str]) -> list[str]:
    entries: list[str] = []
    seen: set[str] = set()
    for line in lines:
        message = canonical_alert_message(line)
        if not message or message in seen or is_cutscene_noise(message):
            continue
        seen.add(message)
        entries.append(message)
    return entries


ACTOR_ERROR_RE = re.compile(
    r"^(?:Cannot create actor with actor catalog entry|"
    r"CActorAction\[.*?\] Can only create one CActorAction per effect|"
    r"CActorAction\[.*?\] unable to find|"
    r"CActorUnit\[.*?\] unable to find|"
    r"Could not find (?:model|texture|sound|asset)|"
    r"Unable to find attachment point|"
    r"No matching model found for)",
    re.IGNORECASE,
)


def categorize_alerts(alert_items: list[str]) -> tuple[list[str], list[str]]:
    actor_errors: list[str] = []
    warnings: list[str] = []
    for msg in alert_items:
        if ACTOR_ERROR_RE.search(msg):
            actor_errors.append(msg)
        else:
            warnings.append(msg)
    return actor_errors, warnings


def format_report(
    *,
    logs_dir: Path,
    alerts: LogFile | None,
    script_error: LogFile | None,
    actor_error_items: list[str],
    warning_items: list[str],
    error_items: list[str],
    skipped_script_errors: int = 0,
) -> str:
    lines = [
        "Latest playtest bug report",
        f"Source directory: {logs_dir}",
        "",
    ]

    if alerts:
        lines.append(f"Alerts log: {alerts.path.name}")
    if script_error:
        lines.append(f"ScriptError log: {script_error.path.name}")

    lines.extend(["", "== Script errors =="])
    if error_items:
        lines.extend(error_items)
    else:
        lines.append("(none)")

    lines.extend(["", "== Actor creation & action errors =="])
    if actor_error_items:
        lines.extend(actor_error_items)
    else:
        lines.append("(none)")

    lines.extend(["", "== Alerts / warnings =="])
    if warning_items:
        lines.extend(warning_items)
    else:
        lines.append("(none)")

    total_alerts = len(actor_error_items) + len(warning_items)
    lines.extend(
        [
            "",
            f"Summary: {len(error_items)} unique script issue(s), "
            f"{len(actor_error_items)} unique actor error(s), "
            f"{len(warning_items)} general alert(s) ({total_alerts} total alerts).",
        ]
    )
    if skipped_script_errors:
        lines.append(
            f"Filtered: {skipped_script_errors} editor-only Void campaign "
            f"trigger authorization noise (libVoiC/libVCMI)."
        )
    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Read the latest SC2 Alerts.txt and ScriptError.txt from a playtest "
            "session and write deduplicated bugreport.txt for coding agents."
        )
    )
    parser.add_argument(
        "--logs-dir",
        help="StarCraft II GameLogs directory (default: auto-detect).",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=None,
        help="Output file; default: selected project runtime/reports/bugreport.txt. Without a project, supply --output.",
    )
    parser.add_argument(
        "--since",
        type=float,
        help="Filter session logs created on or after this timestamp (epoch seconds).",
    )
    args = parser.parse_args()

    data = None
    if args.output is None:
        try:
            data = project_data_dir(REPO_ROOT)
            if data is None:
                parser.error("Select a project or supply an explicit --output")
            args.output = data / "runtime/reports/bugreport.txt"
        except ValueError as exc:
            parser.error(str(exc))
    logs_dir = resolve_logs_dir(args.logs_dir)
    session_logs = list_session_logs(logs_dir)
    alerts_file, script_error_file = pick_session_logs(logs_dir, session_logs, since=args.since)

    raw_alert_items: list[str] = []
    error_items: list[str] = []
    skipped_script_errors = 0

    if script_error_file:
        raw_errors = parse_script_errors(read_text(script_error_file.path))
        error_items, skipped_script_errors = filter_script_errors(raw_errors)
    if alerts_file:
        raw_alert_items = parse_alerts(read_text(alerts_file.path))

    actor_error_items, warning_items = categorize_alerts(raw_alert_items)

    report = format_report(
        logs_dir=logs_dir,
        alerts=alerts_file,
        script_error=script_error_file,
        actor_error_items=actor_error_items,
        warning_items=warning_items,
        error_items=error_items,
        skipped_script_errors=skipped_script_errors,
    )
    if data is not None:
        ensure_project_data(data)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(report, encoding="utf-8", newline="\n")

    print(f"Wrote {args.output}")
    if alerts_file:
        print(
            f"  Alerts: {alerts_file.path.name} "
            f"({len(actor_error_items)} actor errors, {len(warning_items)} warnings)"
        )
    else:
        print("  Alerts: (none)")
    if script_error_file:
        print(
            f"  ScriptError: {script_error_file.path.name} "
            f"({len(error_items)} unique"
            + (
                f", {skipped_script_errors} Void campaign noise filtered"
                if skipped_script_errors
                else ""
            )
            + ")"
        )
    else:
        print("  ScriptError: (none)")

    has_failures = bool(error_items or actor_error_items)
    return 1 if has_failures else 0


if __name__ == "__main__":
    sys.exit(main())
