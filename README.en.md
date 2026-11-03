# StarCraftIIAgent — StarCraft II mod development agent

[中文](README.md)

A local workspace for StarCraft II custom campaign development, with development rules, a knowledge base, query and validation tools, and 34 skills loaded on demand: 15 root skills, 13 Galaxy sub-skills and six SC2Data sub-skills.

Author: **扯蛋虾米**. See [AUTHORS](AUTHORS.en.md).

[Installation](setup.en.md) · [Workspace rules](AGENTS.en.md) · [Wiki](wiki/index.en.md) · [Tools](tools/README.en.md) · [Full development examples](wiki/guides/development-conversations.en.md)

## Start with your task

| Send this request | What to expect first |
|---|---|
| “Find an official example of a one-time mission objective.” | Component and trigger names, plus the conditions the example uses. No project setup required. |
| “Check the evacuation trigger in `<map.SC2Map>` and preview a change so only player 1 can complete it once.” | The actual Components path, region and current conditions, followed by the proposed change. |
| “Initialize my main mod at `<mod.SC2Mod>`.” | The resolved project, editing source and active dependencies. |

Open this workspace in your assistant and replace paths with real Components directories. See [user–agent conversations](wiki/guides/development-conversations.en.md#saved-map-examples) or [in-game dialogue examples](wiki/reference/trigger-dialogue-examples.en.md).

## Requirements by task

Use Windows and Python 3.12 for the basic tools. For shared CLI/MCP operations install the isolated Python 3.12+ environment. Offline Galaxy compilation also requires Node 22+ and the installed frontend. Install SC2 for Editor and game checks. Formal XML schema validation requires lxml or xmllint. See [installation](setup.en.md) and [integration regression and Windows UAC](wiki/guides/shared-tools.en.md).

## Capabilities

| Task | What it supports | What to provide | Editor and game validation |
|---|---|---|---|
| Units, abilities and tech | Effective-value and chain queries, attributes, abilities, upgrades and unit variants | Project path, object ID and desired behavior; the agent retrieves existing facts | Check Editor loading and in-game behavior after changes |
| Actors, models and audio | Presentation-chain diagnosis, official asset queries, appearance swaps and effects | Object, desired appearance or observed problem | Observe animation, attachments, sound and actual visuals |
| GUI triggers and attack waves | Objectives, timers, victory/defeat, dialogue, wave scaling and migration | Explicit map, players, conditions and target objects | Editor saves and in-game event checks |
| Banks and existing Galaxy | Campaign persistence, old-save compatibility and confirmed hand-written scripts | Save requirements or actual source entry | Loading, saving and relevant runtime scenarios |
| Developer strings | Player string keys, locale files and missing anchors | Object, text surface and data locale | Check in-game text; whole-project translation is outside scope |
| Terrain and scenes | Map investigation, isolated copies, placement and supported terrain changes | Valid map base, output path, layout and preservation constraints | Query capability per operation; verify visuals, traversal and save/reopen separately |
| Unit migration and layer merges | Providers, chains, conflicts and assets, followed by explicitly planned import | Sources, target and unit list or layer precedence | Test production, abilities and presentation; layer merging alone is not full migration |
| Checks, deployment and project records | Static checks, log diagnosis, deployment previews and authorized deployment, design and issue records | Explicit target, scope or reproduction evidence | Static checks cannot replace Editor and packaged runtime acceptance |

The basic workflow uses local rules, skills and Python tools. Shared CLI/MCP, model delegation and Harness2 are optional extensions with separate local environments and connections. Workflows independent of them remain available without installation.

## Advanced guides

### Repository and routing

The agent reads [AGENTS.md](AGENTS.en.md), current configuration and [wiki/index.md](wiki/index.en.md), then the [entry skill](skills/sc2-project-entry/SKILL.md) routes to a specialist. Galaxy and SC2Data roots own their sub-routing. [AGENT.md](AGENT.en.md) provides the identity and knowledge architecture overview.

| Task | Root skill |
|---|---|
| Project identity and routing | `sc2-project-entry` |
| Catalog XML / Actors | `sc2-catalog-xml` / `sc2-actor-system` |
| GUI triggers / Attack waves | `sc2-map-triggers` / `sc2-attack-wave-scaling` |
| Hand-written Galaxy / Banks | `sc2-galaxy-scripting` / `sc2-bank-system` |
| Developer strings and anchors | `sc2-localization` |
| Validation/deployment / Editor handoff | `sc2-tools-validation` / `sc2-editor-handoff` |
| Terrain / Unit migration / Official assets | `sc2-terrain-editing` / `sc2-unit-migration` / `sc2-official-assets` |
| Shared tools / Bounded model delegation | `sc2-shared-tools` / `sc2-deepseek-tasks` |

### File structure and project records

```text
StarCraftIIAgent/
├── README.md / README.en.md    Usage
├── AGENTS.md / AGENT.md        Workspace rules / Identity
├── AUTHORS.md                 Attribution
├── setup.md / setup.en.md      Installation and configuration
├── agent-config.json          Generated locally at initialization; not distributed
├── skills/                    34 skills loaded on demand
├── tools/                     Queries, validation, deployment and XSD schemas
├── integrations/              Optional shared-tool and model integration source
├── wiki/                      General development rules, references and guides
├── docs/                      Suite development records
├── DataEditorXML/             Official data reference exports
├── DesignDocument.md          General capability sources
└── publish/                   Publication output; never editing source
```

Configuration resolves the actual primary mod, editing source and maps. `in_place` edits the selected source directly; `workspace_copy` edits the specified copy and deploys when needed. Confirm hand-written script entries and include order from the target Triggers.

Use `python tools/project-paths.py --ui-language en` to locate project data. The default is `<mod-name>.agent` beside the primary mod; initialization accepts `--project-data-dir`. Reads and initialization do not create empty data directories. Project design, mechanisms and cross-session issues belong in its `docs/`, with source summaries in `docs/sources.md`; indexes, reports and temporary investigations belong in `runtime/`. Project docs can be versioned separately; runtime files are ignored by default. Suite wiki pages hold reusable rules. See [project data](docs/agents/project-data.en.md).

Git distributes generic rules, skills, source, tests and references. It excludes `projects/`, machine settings, `.runtime/`, environment variables, virtual environments, reports, credentials and personal model settings. Rebuild environments and indexes on a new machine.

### Tools and optional extensions

| Need | Entry |
|---|---|
| Tools, command-card audits, logs, archives and indexes | [Tools guide](tools/README.en.md) |
| Project setup, switching and dependency diagnosis | [Setup](setup.en.md), [initialization](wiki/guides/project-initialization.en.md) |
| Official data, triggers and assets | [Wiki routing](wiki/index.en.md), [CASC cache](wiki/reference/official-casc-cache.en.md) |
| Terrain operations and unit migration | [Terrain guide](wiki/guides/sc2-terrain-editing.en.md), [migration](wiki/guides/unit-migration.en.md) |
| Shared CLI/MCP and model delegation | [Local installation, configuration, diagnosis and registration](wiki/guides/shared-tools.en.md) |
| Harness2 experiments and skill optimization | [Linux/WSL setup, baselines, review and recovery](wiki/guides/harness2.en.md); actual runs consume model quota |

Choose checks by change scope: `--scope tools` for tools, `--scope docs` for documentation, and `--scope mod` for target components. Specify maps and temporary external targets explicitly. Tool `--help` defines current arguments.

For attack waves, `python skills/sc2-attack-wave-scaling/scripts/wrap_attack_wave_counts.py "<map-path>/Triggers"` inspects without edits, `--apply` writes and `--check` checks count wrapping. Load the relevant skill and verify actual GUI definitions first.

After an Editor save, use `python tools/audit-gamestrings-anchors.py --ui-language en --locale <actual-locale> --fill` to restore missing player-text anchors; `--fill` writes. Preview deployment with `python tools/deploy-mod.py --ui-language en --dry-run`, then copy within the user's authorized scope.

### Bilingual use

Usage pages are available in Chinese and English. Skills and deeper references retain one source of truth, explained in the selected language. [Language rules](wiki/guides/agent-language.en.md) support automatic selection, temporary `--ui-language` and saved preferences. `python tools/agent-language.py --ui-language en` is read-only; `--set en`, `--set zh-CN` or `--set auto` explicitly saves a preference. UI language does not change SC2 `--locale`, configuration or index identity.

## Limitations and troubleshooting

### Hard rules

[AGENTS.md](AGENTS.en.md) owns the rules: prefer GUI for new triggers and wire maps through exported mod GUI actions. Edit actual development source; never hand-edit generated `MapScript.galaxy`, `Lib*.galaxy` or publication output.

Before XML changes, query the current catalog, parents and active dependencies; use reference queries or DataEditorXML exports for field shapes and precedents as needed. XML comments and attribute values use ASCII; do not use invalid `AbilAutoCmd` buttons or `CBehaviorBuff.InitEffect`, and catalogs cannot contain only comments. Galaxy locals belong at the top of the function; use `while` and explicit assignments (`i = i + 1;`) as a conservative compatibility policy, with extensionless relative includes. Workspace rules and specialist skills maintain the detailed contract.

Advance issues only with evidence: `reported` → `root cause confirmed` → `source fixed` → `static validation passed` → `Editor accepted` → `packaged runtime passed`. Static checks alone can establish at most `static validation passed`; Editor save/reopen and packaged-game reproduction need separate acceptance.

### Editor and capability boundaries

Query current capabilities before terrain edits, resizing or scene work. Supported operations can write isolated Components copies. Saving, reopening, visual checks, unsupported-operation experiments and cinematics require the actual Editor. The agent may perform authorized steps when GUI control is verified; hand off necessary unavailable steps to the user. Capture raw terrain save differences before anchor processing through the [handoff workflow](wiki/guides/editor-handoff.en.md).

Never open Blizzard maps with a project mod active as an external override. Add dependencies through Map → Modules → Dependencies. Opening and saving Blizzard maps require SC2 account login. Developer string support excludes whole-project translation, translation knowledge bases, automatic UI text extraction and encyclopedia products.

### Common problems

- Cannot read rules or skills: verify this workspace is open, local file access is available, `AGENTS.md`, the entry skill and `wiki/index.md` exist, and Python runs.
- No selected project: provide the primary Components mod path for initialization. tools/docs checks and research against explicit targets remain available independently.
- Missing optional tools: rebuild local environments using the integration guide; registration and actual client connection are separate checks.
- `os error 206` or replacement failures: narrow operations using the [recovery guide](wiki/implementation/agent-context-efficiency.md), preserve encoding/line endings and run relevant checks.
- Runtime problems: provide the actual map/mod, reproduction steps, Editor version, logs and screenshots; follow the [runtime diagnosis guide](wiki/implementation/runtime-diagnostics.en.md).

<!-- translation-source: README.md; sha256: ae6b3ec48b33b653f26f182ad11af73fc0a78329603f017c880ad7a7eea08e5e -->
