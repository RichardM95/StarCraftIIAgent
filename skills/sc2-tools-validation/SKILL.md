---
name: sc2-tools-validation
description: StarCraft II mod development tooling for the active project. Use when running pre-flight tests, XML schema validation, Galaxy syntax checks, catalog queries, mod deployment, or playtest bug extraction. Covers all tools/ CLI commands and when to use each.
---

# SC2 Tools & Validation

## When to Use

Load this skill when running any tool from the `tools/` directory: pre-flight tests, XML validation, Galaxy syntax checks, catalog queries, deployment, or playtest bug extraction.

## Quick Decision Guide

| If you need to... | Run this command |
|---|---|
| **Initialize/select project from one Mod path** | `python tools/init-project.py "<primary.SC2Mod>"` |
| **Verify target mod edits** | `python tools/test-suite.py [--mod-dir <path>] [--primary-only]` |
| **Check only tools, docs, or mod** | `python tools/test-suite.py --scope tools|docs|mod` |
| **Validate GameData XML & Galaxy** | `python tools/validate-mod.py` |
| **Inspect recursive mod dependencies** | `python tools/inspect-mod-dependencies.py` |
| **Inspect units/abilities/data chains** | `python tools/sc2-catalog-query.py <cmd>` |
| **Find official/partner component examples or strings** | `python tools/sc2-reference-query.py find <term> --family <Family> --component <name> --limit 20` |
| **Refresh stale catalog query DB** | `python tools/build-sc2-catalog-graph.py --sqlite-only` |
| **Preview/deploy mod to SC2 install** | `python tools/deploy-mod.py --dry-run` |
| **Check GameStrings / localization anchors** | `python tools/audit-gamestrings-anchors.py --fill` |
| **Audit command cards** | `python tools/audit-actor-and-card-integrity.py` |
| **Extract playtest errors & logs** | `python tools/extract-playtest-bugreport.py` |
| **Check documentation links** | `python tools/check-doc-links.py` |
| **Audit issue lifecycle labels/evidence** | `python tools/audit-issue-lifecycle.py` |

## Pre-Flight Linters & Testing

### `init-project.py` (default project setup entry)
Pass the primary Components `.SC2Mod` folder path. The tool infers the standard SC2 layout, recursively validates local component dependencies, and atomically writes `agent-config.json` only after checks pass. Use `--dry-run` to preview; use explicit directory options only for nonstandard layouts. Do not make users manually edit JSON or enumerate dependencies.

### `test-suite.py` (select the affected scope)
Unified pre-flight suite. It reads `agent-config.json`, resolves the configured primary mod, prints both the config and exact target, and fails if no mod is found. It follows `validation.include_dependencies` and `validation.exclude_mods`; use `--primary-only`, `--include-dependencies`, or repeatable `--exclude-mod` for one-run overrides. Runs:
- tool unit tests
- `validate-agent-config.py` — portable config, primary-mod, and recursive component-dependency checks
- `validate-mod.py` — XML schema + Galaxy syntax for the primary Mod and selected dependencies
- `audit-actor-and-card-integrity.py` — primary-Mod command card slot collisions (legacy filename; no Actor binding claim)
- `audit-gamestrings-anchors.py` — localization anchor checks
- `check-doc-links.py` — broken Markdown links

Use `--scope tools|docs|mod` or a focused regression for local changes. Validate actual component edits before Editor handoff. Cross-module changes and full acceptance follow [workspace execution levels](../../AGENTS.md#独立工作区与按需执行). Read-only queries do not require this suite.

### `validate-mod.py`
Comprehensive static checks:
- Formal W3C XSD schema validation on GameData XML (`tools/schemas/sc2-xsd/Catalog.xsd`) using `lxml` or `xmllint`; missing backends fail validation
- UI layout XML parsing plus engine-compatible root, top-level child, and ASCII checks; `SC2Layout.xsd` is reference-only because it does not cover all Editor output
- ASCII-only XML comment/attribute checks and rejection of comment-only catalogs
- Galaxy script AST/syntax validation (variable hoisting, include paths, forbidden operators, non-ASCII characters)

### `inspect-mod-dependencies.py`
Starts from the configured primary mod, uses `ComponentList.SC2Components` to locate the info component (normally `DocumentInfo`), parses its dependency declarations, and repeats for every locally resolved `.SC2Mod`. Shared dependencies are expanded once, cycles are marked, and missing pure local `file:Mods` dependencies fail validation. Engine and Battle.net dependencies remain visible but do not require unpacked component folders.

### `audit-actor-and-card-integrity.py`
Detects:
- Command card slot collisions
- Attack button displacements

The filename is retained for compatibility. Actor-chain validation must use catalog queries and focused Actor review until a dependency-aware Actor linter is implemented.

### `audit-gamestrings-anchors.py`
Checks active catalog `Name`/`Tooltip`/`Description` string references against `GameStrings.txt`. Use `--fill` to restore missing keys from `ObjectStrings.txt` after an Editor save.

## Catalog Navigation & Querying

### `sc2-catalog-query.py` (primary lookup tool)
Token-efficient catalog lookup over `sc2-catalog-graph-out/catalog.sqlite` (or `graph.json`). Use this INSTEAD of reading raw `DataEditorXML/` dumps.

Common commands:
```bash
python tools/sc2-catalog-query.py find <term> --source-class local_mod
python tools/sc2-catalog-query.py unit-chain <Unit:Id>
python tools/sc2-catalog-query.py production-chain <Unit:Id>
python tools/sc2-catalog-query.py actor-chain <Actor:Id>
python tools/sc2-catalog-query.py show <Family:Id> --limit 30 --depth 2
python tools/sc2-catalog-query.py unresolved --contains <term>
```

### `build-sc2-catalog-graph.py`
Rebuilds catalog data from reference exports, the configured primary Mod, and recursively resolved local component dependencies. Use `--sqlite-only` for the current query database; omit it when JSON, GraphML, and summary reports are also needed. Primary definitions use `local_mod`; resolved dependency definitions use `active_component_dependency`.

### `sc2-reference-query.py`
Read-only, bounded search of `DataEditorXML/SC2GameDataComponents/`. Use `components` to identify a package, `find` with `--area gamedata|enus|zhcn`, `--family`, `--component`, and `--limit` for a line/string, or `object <Family:Id> --component <name>` for one complete catalog object. The top-level `DataEditorXML/*.txt` dumps already contain some identical XML; consult the graph first. The sample snapshot is not included in the graph and does not imply an active dependency.

## Deployment

### `deploy-mod.py` (and `deploy-mod.ps1`)
- Reads `project.source_mode` from `agent-config.json`.
- In `in_place` mode the configured Mod under `paths.mods_dir` is already the authoritative source, so deployment is an explicit no-op; edit and validate that source directly.
- In `workspace_copy` mode `project.source_mod` (workspace-relative or absolute) is authoritative; missing or invalid paths stop writes. The configured source and deployment copies outward to `paths.mods_dir`. Never copy changes back from the deployed target as a normal workflow.
- Copies the `.SC2Mod` component folder to `paths.mods_dir` from `agent-config.json` (overridable with `--mods-dir`); it never rewrites generated `Lib*.galaxy`
- Use `--dry-run` before deployment; a source already equal to the destination is treated as a safe no-op

After a `workspace_copy` deployment, open and save the mod in the SC2 Editor to regenerate compiled libraries. In `in_place` mode, skip deployment and open the authoritative source directly.

## Playtest Bug Extraction

### `extract-playtest-bugreport.py` (and `.ps1`)
Extracts alerts and script errors from StarCraft II `GameLogs` into a clean report (`bugreport.txt`). Run after playtesting to triage runtime issues.

## XSD Schemas

Bundled in `tools/schemas/sc2-xsd/`:
- `Catalog.xsd` — GameData XML schema
- `SC2Layout.xsd` — UI layout IDE/reference schema; not enforced by `validate-mod.py`

VS Code workspace settings (`.vscode/settings.json`) bind `Base.SC2Data/GameData/*.xml` to `Catalog.xsd` for real-time diagnostics.

## Tool Failure Recovery

If a patch helper or tool reports `os error 206` or string replacement errors:
- Use exact text replacement
- Preserve encoding/newlines
- Run the affected scope or regression to verify

## Reference

- `tools/README.md` — full tooling guide
- `wiki/implementation/agent-context-efficiency.md` — context efficiency guidelines
- `wiki/guides/multi-pc-setup.md` — multi-PC setup & IDE config

## Chinese Task Knowledge (Merged)

Distilled from `references/tools-and-validation.md` and `references/source-caveats.md`. PowerShell examples kept verbatim; duplicates above omitted. Working directory is the project root; quote Windows paths with spaces.

### Catalog Query Sequence (full PowerShell sample)
```powershell
python tools/sc2-catalog-query.py stats
python tools/sc2-catalog-query.py find Marine --family Unit --limit 10
python tools/sc2-catalog-query.py providers Unit:Marine
python tools/sc2-catalog-query.py show Unit:Marine --depth 2 --limit 20
python tools/sc2-catalog-query.py unit-chain Unit:Marine --limit 10
python tools/sc2-catalog-query.py production-chain Unit:Marine --limit 10
python tools/sc2-catalog-query.py actor-chain Unit:Marine --limit 10
```
- `ability-chain Abil:<ActualId>` for ability chains.
- `unresolved --contains <ActualPrefix> --limit 30` for suspicious unresolved references.
- Add `--source-class local_mod` to `find` / chain queries to narrow to local records. **Do NOT filter with `local_mod` when querying base objects** — it would hide the base dependency entries.

### Targeted Static Checks (PowerShell)
```powershell
python tools/test-suite.py --mod-dir "$env:SC2_MODS_PATH\AeonOfIhanrii.SC2Mod"
python tools/validate-mod.py --mod-dir "$env:SC2_MODS_PATH\AeonOfIhanrii.SC2Mod"
python tools/audit-actor-and-card-integrity.py --mod-dir "$env:SC2_MODS_PATH\AeonOfIhanrii.SC2Mod"
python tools/audit-gamestrings-anchors.py --mod-dir "$env:SC2_MODS_PATH\AeonOfIhanrii.SC2Mod"
python tools/check-doc-links.py
```
Replace example paths with the actual target.

### `test-suite.py` Scope Caveats (critical)
- `test-suite.py` accepts `--mod-dir` and otherwise resolves the configured `project.primary_mod`; `SC2_MODS_PATH` and sibling-layout discovery only supply candidate roots. With no configured project name it fails closed instead of guessing an AeonOfIhanrii target. It passes the resolved absolute target to every mod-aware subtool.
- Dependency content validation follows `agent-config.json`; the current project scans the complete local component dependency chain with no exclusions. Localization and command-card audits remain primary-Mod scoped because naive per-dependency localization checks do not model inherited strings.
- The suite now fails when no target mod exists, and `validate-mod.py` reports scanned file counts. Still confirm the printed target is the intended component directory.
- Command-card slot collisions that may be gated by dependency requirements are non-fatal candidates by default; inspect them with `audit-actor-and-card-integrity.py --strict` before a focused command-card handoff.
- Do not present a zero-exit run as Editor or packaged-runtime acceptance — the suite remains a static rule set.

### Database Caveats
- Default catalog queries check manifest additions, removals and changed inputs even without an active mod. Missing/invalid configured sources block current-data queries; rebuild only after repairing configuration. `--allow-stale` permits explicit historical inspection and prints a historical-only warning. `reference_export` is a TXT reference source, while `active_component_dependency` comes from the resolved component chain. Cross-check current XML, dependency declarations, and source path.
- Refresh with `python tools/build-sc2-catalog-graph.py --sqlite-only` when the query index is missing or stale. Verify its input config covers the target mod first. Do not rebuild for a single sample lookup.
- Search the component snapshot only for a question the graph and selected dumps do not answer; keep source, component, family, area, and result limit narrow.
- `audit-gamestrings-anchors.py --fill --mod-dir '<ActualPath>'` rewrites localization files. After Editor save, use it to restore anchors and review the diff.
- `deploy-mod.py` copies components when source and target differ — verify the target first; without `--dry-run` it is NOT a read-only validation command and does not regenerate compiled libraries.

### Issue Lifecycle & Feedback
- Project issue lifecycle: `reported → root cause confirmed → source fixed → static validation passed → Editor accepted → packaged runtime passed`. Advance a stage only with effective-value evidence.
- Static layer: XML/schema, Galaxy rules, ID & command-card references, duplicate definitions, localization, doc links.
- Editor layer: open the mod/map with correct dependencies, review warnings, save Components, review normalization diff. Do NOT open vanilla maps with the project mod as an external override.
- Game layer: minimal-scenario tests — production & actual deduction, command card, attack target, abilities, morph, model/audio, each upgrade level & unlocks.
- Record feedback in `wiki/implementation/bug-reports/latest.md` with at least: map, player/faction, repro steps, expected/actual, full warnings. Before using the log extractor, verify its path configuration — do not assume the old machine's `GameLogs` path applies.

### Source Caveats (from `source-caveats.md`)
- **Localization tool:** Use the existing `audit-gamestrings-anchors.py`; documentation tool references are checked automatically by `check-doc-links.py` so removed legacy commands do not reappear unnoticed.
- **Validation scope:** Older tool versions silently passed when no mod was scanned. Current tools share `sc2_paths.py`, accept/propagate `--mod-dir`, and fail closed when discovery finds no target.

## Dependency completeness and deployment safety

All investigation tools use the shared dependency-root resolver. A configured editing source keeps configured Mods; a one-off explicit component uses its own Mods ancestor. If neither applies, pass `--mods-dir` to inspection/build or the test suite. Never silently use another installation's same-name mod.

Current catalog builds/queries stop for missing or damaged component dependencies. `--allow-incomplete-dependencies` permits explicitly marked partial read-only investigation; the v3 manifest stores problems and each query repeats the warning. It does not authorize effective-value confirmation, source writes or dependency validation. `--allow-stale` is independent historical permission. Rebuild old/missing manifests and include the actual component-list info file.

Deployment preserves no-op for identical paths and rejects both ancestor/descendant overlaps before dry-run, cleaning or copying.

Disabling `project.resolve_dependencies_recursive` retains only primary-component results and is a partial scope; both building and querying require `--allow-incomplete-dependencies`, with an explicit configuration-disabled warning.

Index artifacts and manifests bind the same build_id; identity mismatch always stops. Every index path checks its recorded selection. Legacy history requires explicit permission and never overrides partial-dependency permission. Builds stage the complete output before publication; SQLite-only retains previous JSON/reports and manual extras.

Deployment stages clean replacements or merge copies, checks source stability and copied bytes, and retains one owned previous version. Publication rollback failures preserve all surviving diagnostic paths; do not remove them automatically or treat the new version as accepted.
