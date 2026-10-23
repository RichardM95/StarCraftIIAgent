# AGENTS.md — workspace entry

[中文](AGENTS.md)
<!-- translation-source: AGENTS.md; sha256: 60f73afebd266fdda40ab93980f0f9833953c0032c0db7d9cf5da2e088831f7a -->

**Author: 扯蛋虾米.** Unified attribution: [AUTHORS](AUTHORS.en.md).

AGENTS.md is the authoritative rule entry. Read agent-config.json when paths matter; route domain reading through [wiki/index](wiki/index.en.md), opening [catalog](wiki/catalog.en.md) only if needed. README is the human overview; wiki/reference/editor-guide.md contains Editor workflow notes (Chinese original).

## User language

Follow [language selection](wiki/guides/agent-language.en.md): explicit instruction → fixed personal preference → current user's natural language → system default. Inspect preferences read-only with tools/agent-language.py --json when needed. Code, paths and quotes do not switch language. Pass --ui-language en or zh-CN to tools. Read usage pages in the selected language; skills/technical rules retain one source and are explained in the selected language. UI language never changes SC2 --locale, config, IDs or exact acceptance labels. Ordinary queries do not save preferences.

## Project and editing rules

When given a primary Components .SC2Mod directory and asked to initialize/select, run `python tools/init-project.py "<primary-mod-components-path>"` directly. It infers SC2/Mods/Maps, resolves recursive dependencies and writes agent-config.json. Do not require manual JSON editing. Ask only for missing paths that cannot be derived from a nonstandard layout. Verify project identity from the chosen component; never guess Bank, Library ID or prefixes.

After initialization follow project.source_mode: in_place edits the configured primary source; workspace_copy edits project.source_mod, resolved relative to the workspace or absolute. Missing copy stops writes. Deploy using tools/deploy-mod.py in the verified direction. Never edit publish/.

Confirm hand-written Galaxy entry points/include order from current Triggers. Edit only hand-written source, never Lib*.galaxy, MapScript.galaxy or other generated output.

Suite wiki/ stores reusable rules/references. Project design, mechanisms and cross-session issues belong in project data located by tools/project-paths.py. Update current topic facts; record necessary decisions/reasons rather than change histories. Link canonical pages; omit redundant file lists, test output, issue details or commit hashes from decision logs. Git holds history.

Every issue follows reported → root cause confirmed → source fixed → static validation passed → Editor accepted → packaged runtime passed. Before numeric changes record local object, parent, inherited value and intended override. Before text edits identify world hover, selection panel, command card, tooltip or Editor text. Report only the exact highest proven gate. Static checks cannot establish Editor accepted without reload/save evidence or packaged runtime passed without in-game steps/results.

Ask for missing information when needed. If repeated research no longer narrows the issue, stop and summarize findings. Ingest project design into docs/design/ with provenance in docs/sources.md after selecting a project. Only reusable findings with scope/evidence enter suite wiki/.

## Repository purpose and routes

A starting workspace for SC2 custom campaign development with AI assistance (CCM community): WoL/HotS/LotV DataEditorXML exports, XSD schemas, static linters, bounded Catalog tools and structured references.

Implementation tasks load skills/sc2-project-entry/SKILL.md, then relevant specialists. Documentation/tool maintenance reads only relevant rules/files. Local AGENTS.md, config, skills and tool --help/source are the contract; global skills only locate this workspace. [Issue tracking](docs/agents/issue-tracker.en.md), [domain docs](docs/agents/domain.en.md) and [research](docs/agents/research.en.md) define their respective workflows.

The selected project comes from local config; only absence means unselected. Inspect actual config/Triggers/component identity. No fixed campaign, Bank, library or prefix is assumed.

| Path | Purpose |
|---|---|
| AUTHORS.md | Unified attribution |
| agent-config.json | Portable workspace/install/Mods/maps/source/dependency paths |
| wiki/index.md | Task router |
| wiki/catalog.md | Full page inventory, only when routing is insufficient |
| wiki/log.md | General decision reasons; project decisions belong in project data |
| wiki/design/ | Project-data location guidance |
| wiki/implementation/ | Construction patterns, localization and pitfalls |
| wiki/reference/ | Lookups, Actors and SC2 references |
| wiki/guides/ | Handoff, multiple computers and simulated Bank tests |
| skills/ | One skill tree: root routers plus Galaxy/sc2data sub-skills |
| skills/galaxy/ | 13 API sub-skills, after sc2-galaxy-scripting |
| skills/sc2data/ | Six XML schema sub-skills, after sc2-catalog-xml |
| tools/ | Unified tests, static validators and Catalog queries |
| tools/schemas/sc2-xsd/ | Catalog/GameData/SC2Layout schemas |
| DataEditorXML/ | Query/grep before XML edits |
| DesignDocument.md | General capability sources; project sources stay in project docs |
| publish/ | Packaging only; never an editing source |

Configured Mods contains dependencies; configured Maps/Campaign contains campaign maps (for example void/paiur01.SC2Map). tools/project-paths.py returns docs/index/report/temp locations without creating them. Exports cover WoL, HotS and LotV; for Nova/Co-op/custom bases request the relevant export and update wiki/reference/data-editor-xml.md.

For patch-helper os error 206 or string replacement failures, follow wiki/implementation/agent-context-efficiency.md (English technical reference). Use precise replacements, preserve encoding/newlines and run affected tools/docs/mod checks.

## Rules before code changes

Prefer editable GUI events/conditions/actions for new or converted triggers. Use only a minimal embedded Custom Script for logic GUI cannot reasonably express. Standalone Galaxy is for explicit Galaxy requests or existing hand-written source maintenance. Generated scripts remain read-only.

Maps call exported mod GUI actions as the conservative handoff practice. Check generated calls; the [Editor evidence boundary](wiki/reference/trigger-knowledge.en.md#editor-behavior-evidence-boundary) distinguishes practice from proven linker behavior.

Before XML edits run tools/sc2-catalog-query.py; inspect exact exports or tools/sc2-reference-query.py for field shapes. Names/IDs are case-sensitive; samples do not prove active loading. Validate actual changed components; tools/docs use their own scopes. After a successful Editor save, first audit strings read-only, then explicitly use `python tools/audit-gamestrings-anchors.py --locale zhCN --fill` for missing player anchors; other projects use their actual locale.

XML comments/attributes use ASCII. AbilAutoCmd is not a valid SC2 button type; CBehaviorBuff does not support InitEffect. Pure-comment Catalog files are rejected. Check existing dependencies for validators/entities before adding duplicates.

Galaxy locals belong at the start of the function, before executable statements. Conservatively use while and explicit assignment (i = i + 1); this is a workspace policy, not proof all other syntax is invalid. Query target language/API/generated evidence. Include relative paths without extensions, such as include "Scripts/MyScript". Write in mod source blocks or Base.SC2Data/Scripts/, not MapScript.galaxy.

## Editor operations and precautions

Opening/saving Blizzard maps requires the user's Editor/account. Terrain, regions, doodads, pathing and cinematics need Editor work. For initialization obtain a real Components source (setup guidance); explicit archive conversion is available separately. Never open a map while the project mod is active as an external override. Add dependencies via Map → Modules → Dependencies → `<ModName>.SC2Mod`.

## Independent workspace and execution scope

This directory owns its Git, ignores, tools, skills and suite docs. Relative user inputs and project.source_mod resolve against it; development projects come from config.

| Request | Action/validation |
|---|---|
| Query/explanation/read-only research | Read targeted evidence and answer; no maintenance ceremony |
| Documentation/local tool changes | Relevant links, skill entry or regressions; docs/tools scope |
| Mod/map changes | Verify effective values, edit actual source, validate affected target/mod scope |
| Shared tools/full tests | Tool/docs plus necessary actual target checks; without project run tools and docs separately |
| Deployment/recovery | Perform when requested/needed within authorization; keep path protections and recovery |

Reuse unchanged rules/evidence. Recheck changed source/config/implementation, preserving freshness and prepublication checks. Do not rerun passing checks with identical inputs without a reason. Report scope. Execute directly with sufficient information; plan when substantial choices require it.

The workspace develops mods/maps; it does not provide whole-project translation, translation knowledge bases, automatic UI extraction or encyclopedia generation. Development string-key/anchor/encoding maintenance stays with sc2-localization and local tools. Bilingual agent usage does not change that boundary.
