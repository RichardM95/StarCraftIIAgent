# StarCraftIIAgent — StarCraft II mod development agent

[中文](README.md)

A local workspace for StarCraft II custom campaign development, with development rules, a knowledge base, query and validation tools, and root, Galaxy and SC2Data skills loaded by task. See [task routing](#repository-and-routing) for the skill entries.

Author: **扯蛋虾米**. See [AUTHORS](AUTHORS.en.md).

[Installation](setup.en.md) · [Workspace rules](AGENTS.en.md) · [Wiki](wiki/index.en.md) · [Tools](tools/README.en.md) · [Full development examples](wiki/guides/development-conversations.en.md)

<a id="common-request-examples"></a>

## Start with your task

| Send this request | What to expect first |
|---|---|
| “Find an official example of a one-time mission objective.” | Component and trigger names, plus the conditions the example uses. No project setup required. |
| “Check the evacuation trigger in `<map.SC2Map>` and preview a change so only player 1 can complete it once.” | The actual Components path, region and current conditions, followed by the proposed change. |
| “Initialize my main mod at `<mod.SC2Mod>`.” | The resolved project, editing source and active dependencies. |
| “Show the current project's Marine health, weapons and production requirements. Do not change files.” | The unit ID, effective values and their sources; clarify duplicate names first. |
| “Set the current project's Marine base health to 120, preserving upgrades. Do not deploy yet.” | Before/after base values, actual source location and relevant static checks. |
| “Add a separate Shadow Blink to Stalker with a ten-second cooldown. Keep the original ability.” | Ability, button, command-card and string wiring, with offline checks and game verification as needed. |

Open this directory in an AI assistant able to read local workspace files and run tools. Replace paths with real Components directories. Describe your goal normally; the agent retrieves existing facts, so you do not need to memorize skill names or tool arguments. See [all 36 development scenarios](wiki/guides/development-conversations.en.md), [saved-map collaboration](wiki/guides/development-conversations.en.md#saved-map-examples) and [in-game dialogue examples](wiki/reference/trigger-dialogue-examples.en.md).

For a first request, state the target, desired outcome and scope, for example:

```text
The target is <map-or-mod-Components-path>.
Complete the mission when player 1 first enters the evacuation zone, without triggering again on re-entry.
Inspect the current logic read-only, then show a preview without applying it to the target source.
```

| What you can say | Expected behavior |
|---|---|
| “Read-only investigation this time.” | Query existing content and sources without changing target map or mod source. |
| “Show a preview without applying it.” | Show proposed behavior, differences and impact; tools may create isolated copies, candidates or reports. |
| “Apply this plan without deploying yet.” | Edit the identified development source, run relevant checks and report actual results; changes and deployment can be specified separately. |

## Requirements by task

Use Windows and Python 3.12 for the basic tools. For shared CLI/MCP operations install the isolated Python 3.12+ environment. Offline Galaxy compilation also requires Node 22+ and the installed frontend. Install SC2 for Editor and game checks. Formal XML schema validation requires lxml or xmllint. See [installation](setup.en.md) and [integration regression and Windows UAC](wiki/guides/shared-tools.en.md).

## Quick start

1. **Load the rules.** Open this workspace in your assistant and send “Read AGENTS.md and skills/sc2-project-entry/SKILL.md before handling my task.” Explicit file access also works when automatic skill discovery is unavailable.
2. **Check installation.** Run these checks from the workspace root, or ask the assistant to run them. Neither requires a selected project.

   ```powershell
   python tools/test-suite.py --ui-language en --scope docs
   python tools/test-suite.py --ui-language en --scope tools
   ```

3. **Provide a target.** Before modifying a mod, send “My primary Mod Components folder is `<actual-path>`. Please initialize the project,” then describe your task. Official research or inspection of an explicit map can proceed without changing the selected project.

Initialization runs `tools/init-project.py`, checks recursive dependencies and generates local `agent-config.json`; no manual JSON editing is needed. Its absence in a fresh clone is normal. Components are folders saved by the Editor. If you only have a `.SC2Mod` / `.SC2Map` archive, use the [initialization guide](wiki/guides/project-initialization.en.md) and [archive guide](tools/README.en.md#packed-components-and-conversion) to determine how to read or convert it.

## Validation: offline first

- **Queries, documentation and static checks:** launch neither the Editor nor the game.
- **Map runtime checks:** prefer offline generation, type checking, independent MPQ packaging and direct game tests, collecting this run's Bank and logs automatically.
- **Native operations and Editor acceptance:** explain the concrete need before using the Editor for unsupported GUI structures, required native saves or specific Editor acceptance.

Ask: “Test this change in an independent copy of `<map-path>`, prefer skipping the Editor, and report scope and observed results.” See [offline testing](wiki/guides/offline-testing.en.md) for coverage, longer scenarios, background jobs and evidence.

The offline checker is an independent static frontend, not the Blizzard compiler. Smoke success proves this script executed and the game advanced briefly; mission conditions, visuals and save compatibility need separate checks. The offline route can reach `packaged runtime passed` without granting `Editor accepted`.

## Capabilities

| Task | What it supports | What to provide | Editor and game validation |
|---|---|---|---|
| Units, abilities and tech | Effective-value and chain queries, attributes, abilities, upgrades and unit variants | Project path, object ID and desired behavior; the agent retrieves existing facts | Static checks first; direct game tests and Editor acceptance as needed |
| Actors, models and audio | Presentation-chain diagnosis, official asset queries, appearance swaps and effects | Object, desired appearance or observed problem | Observe animation, attachments, sound and actual visuals |
| GUI triggers and attack waves | Objectives, timers, victory/defeat, dialogue, wave scaling and migration | Explicit map, players, conditions and target objects | Offline generation and direct game checks for the supported GUI subset; native saves as needed |
| Banks and campaign saves | Campaign persistence, old-save compatibility, settlement and unlock wiring | Save requirements, existing Bank and settlement entry; the agent retrieves existing facts | New/old save loading, saving and progress checks |
| Hand-written Galaxy and offline checks | Maintain confirmed hand-written source and use the installed frontend for offline compilation diagnostics | Source entry, target components and actual dependencies; offline compilation also needs Node 22+ and the frontend | The static frontend checks syntax, symbols and types; engine compatibility needs actual runtime evidence |
| Official examples and data research | Query official data, trigger precedents and asset reference chains | Object ID, mechanism description or component scope | Reference hits still require checking the target project's loaded dependencies |
| Developer strings | Player string keys, locale files and missing anchors | Object, text surface and data locale | Check in-game text; whole-project translation is outside scope |
| Terrain and scenes | Map investigation, isolated copies, placement and supported terrain changes | Valid map base, output path, layout and preservation constraints | Query capability per operation; verify visuals, traversal and save/reopen separately |
| Unit migration and layer merges | Providers, chains, conflicts and assets, followed by explicitly planned import | Sources, target and unit list or layer precedence | Test production, abilities and presentation; layer merging alone is not full migration |
| Icon creation and checks | Create or redraw icons using identity, gameplay and faction references; check small-size readability and the required DDS profile | Original image or purpose, dimensions/compression and visual references; format checks need Pillow | Decode compressed candidates and check the actual UI after replacement |
| Roguelike mechanics | Design and diagnose talents, draws, shops, rewards, stacking and cross-map restoration | Project rules, an entry or a reproducible problem | Test acquisition, caps, repeated actions and save restoration separately |
| Talent-list export | Inspect UserData and static GUI registrations, export bilingual Excel through project mappings and resolve base values in descriptions | Mod path, field and rarity mappings; Excel export needs openpyxl | Read back the workbook and report missing, ambiguous and unresolved data; test runtime bonuses separately |
| Checks, deployment and project records | Static checks, log diagnosis, deployment previews and authorized deployment, design and issue records | Explicit target, scope or reproduction evidence | Record static checks, conditional Editor acceptance and actual runtime results separately |

The basic workflow uses local rules, skills and Python tools. Shared CLI/MCP, model delegation and Harness2 are optional extensions with separate local environments and connections. Workflows independent of them remain available without installation.

Data queries explain local overrides, inheritance and dependency providers, identifying uncertain merge rules or missing dependencies. Upgrades, behaviors and triggers may also change values at runtime, so final in-game behavior needs actual testing. Previews help inspect layout and data; verify actual visuals and pathing in the Editor and game.

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
| Icon creation and small-size review | [sc2-icon-art](skills/sc2-icon-art/SKILL.md) |
| Roguelike mechanics and restoration audits | [sc2-roguelike-mechanics](skills/sc2-roguelike-mechanics/SKILL.md) |
| Bilingual talent Excel export | [sc2-roguelike-talent-export](skills/sc2-roguelike-talent-export/SKILL.md) |

### File structure and project records

```text
StarCraftIIAgent/
├── README.md / README.en.md    Usage
├── AGENTS.md / AGENT.md        Workspace rules / Identity
├── AUTHORS.md                 Attribution
├── setup.md / setup.en.md      Installation and configuration
├── agent-config.json          Generated locally at initialization; not distributed
├── skills/                    Root and sub-skills loaded by task
├── tools/                     Queries, validation, deployment and XSD schemas
├── integrations/              Optional shared-tool and model integration source
├── wiki/                      General development rules, references and guides
├── docs/                      Suite development records
├── DataEditorXML/             Official data reference exports
├── DesignDocument.md          General capability sources
├── editor-tests/              Local independent test maps; not distributed
├── .runtime/                  Local candidates, builds, reports and caches
└── publish/                   Publication output; never editing source
```

Configuration resolves the actual primary mod, editing source and maps. `in_place` edits the selected source directly; `workspace_copy` edits the specified copy and deploys when needed. Confirm hand-written script entries and include order from the target Triggers.

Use `python tools/project-paths.py --ui-language en` to locate project data. The default is `<mod-name>.agent` beside the primary mod; initialization accepts `--project-data-dir`. Reads and initialization do not create empty data directories. Project design, mechanisms and cross-session issues belong in its `docs/`, with source summaries in `docs/sources.md`; indexes, reports and temporary investigations belong in `runtime/`. Project docs can be versioned separately; runtime files are ignored by default. Suite wiki pages hold reusable rules. See [project data](docs/agents/project-data.en.md).

Git distributes generic rules, skills, source, tests and references. It excludes `projects/`, `editor-tests/`, root `.SC2Mod/`, machine settings, `.runtime/`, environment variables, virtual environments, reports, credentials and personal model settings. Rebuild environments and indexes on a new machine. Local maps in `editor-tests/` are separate from versioned generic samples in `tests/fixtures/`. Keep logs and task receipts in `.runtime/`.

### Tools and optional extensions

| Need | Entry |
|---|---|
| Tools, command-card audits, logs, archives and indexes | [Tools guide](tools/README.en.md) |
| Project setup, switching and dependency diagnosis | [Setup](setup.en.md), [initialization](wiki/guides/project-initialization.en.md) |
| Official data, triggers and assets | [Wiki routing](wiki/index.en.md), [CASC cache](wiki/reference/official-casc-cache.en.md) |
| Terrain operations and unit migration | [Terrain guide](wiki/guides/sc2-terrain-editing.en.md), [migration](wiki/guides/unit-migration.en.md) |
| Offline builds and automated game checks | [Offline testing](wiki/guides/offline-testing.en.md) |
| Shared CLI/MCP and model delegation | [Local installation, configuration, diagnosis and registration](wiki/guides/shared-tools.en.md) |
| Harness2 experiments and skill optimization | [Linux/WSL setup, baselines, review and recovery](wiki/guides/harness2.en.md); actual runs consume model quota |

Choose checks by change scope. Run commands from the workspace root:

| Scope | Command | Prerequisite |
|---|---|---|
| Usage and skill documentation | `python tools/test-suite.py --ui-language en --scope docs` | No active project required |
| General tool regression | `python tools/test-suite.py --ui-language en --scope tools` | No active project required |
| Mod or map components | `python tools/test-suite.py --ui-language en --scope mod --mod-dir "<Components-path>"` | Valid target and required dependencies; omit the target to use the current project |
| Shared SC2 tool integration regression | `python tools/test-suite.py --ui-language en --scope integration` | Shared-tool isolated environment installed; exit SC2 first |

Specify maps and temporary external targets explicitly; tool `--help` defines current arguments. If Windows directory symlink permissions are missing, use the optional UAC retry described in the [integration regression guide](wiki/guides/shared-tools.en.md). Report ordinary regression and retry results separately.

For attack waves, `python skills/sc2-attack-wave-scaling/scripts/wrap_attack_wave_counts.py "<map-path>/Triggers"` inspects without edits, `--apply` writes and `--check` checks count wrapping. Load the relevant skill and verify actual GUI definitions first.

After an Editor save, use `python tools/audit-gamestrings-anchors.py --ui-language en --locale <actual-locale> --fill` to restore missing player-text anchors; `--fill` writes. Preview deployment with `python tools/deploy-mod.py --ui-language en --dry-run`, then copy within the user's authorized scope.

### Bilingual use

Usage pages are available in Chinese and English. Skills and deeper references retain one source of truth, explained in the selected language. [Language rules](wiki/guides/agent-language.en.md) support automatic selection, temporary `--ui-language` and saved preferences. `python tools/agent-language.py --ui-language en` is read-only; `--set en`, `--set zh-CN` or `--set auto` explicitly saves a preference. UI language does not change SC2 `--locale`, configuration or index identity.

## Limitations and troubleshooting

### Hard rules

[AGENTS.md](AGENTS.en.md) owns the rules: prefer GUI for new triggers and wire maps through exported mod GUI actions. Edit actual development source; never hand-edit generated `MapScript.galaxy`, `Lib*.galaxy` or publication output.

[AGENTS.md](AGENTS.en.md) and specialist skills own detailed XML, Galaxy and source-protection rules. Report `static validation passed`, conditional `Editor accepted` and scoped `packaged runtime passed` from their separate evidence. Static checks alone cannot prove runtime success.

### Editor and capability boundaries

Query current capabilities before terrain edits, resizing or scene work. Supported operations can write isolated Components copies. Saving, reopening, visual checks, unsupported-operation experiments and cinematics require the actual Editor. The agent may perform authorized steps when GUI control is verified; hand off necessary unavailable steps to the user. Capture raw terrain save differences before anchor processing through the [handoff workflow](wiki/guides/editor-handoff.en.md).

Never open Blizzard maps with a project mod active as an external override. Add dependencies through Map → Modules → Dependencies. Opening and saving Blizzard maps require SC2 account login. Developer string support excludes whole-project translation, translation knowledge bases, automatic UI text extraction and encyclopedia products.

### Common problems

- Cannot read rules or skills: verify this workspace is open, local file access is available, `AGENTS.md`, the entry skill and `wiki/index.md` exist, and Python runs.
- No selected project: provide the primary Components mod path for initialization. tools/docs checks and research against explicit targets remain available independently.
- Initialization reports unresolved official dependencies: check [CASC cache coverage](wiki/reference/official-casc-cache.en.md#unresolved-official-dependencies-during-initialization), restore tool-readable evidence, then retry. Missing cache coverage does not mean the game lacks the dependency.
- Missing optional tools: rebuild local environments using the integration guide; registration and actual client connection are separate checks.
- `os error 206` or replacement failures: narrow operations using the [recovery guide](wiki/implementation/agent-context-efficiency.md), preserve encoding/line endings and run relevant checks.
- Runtime problems: provide the actual map/mod, reproduction steps, Editor version, logs and screenshots; follow the [runtime diagnosis guide](wiki/implementation/runtime-diagnostics.en.md).

<!-- translation-source: README.md; sha256: 12fd3bd31b685885416f6d402d74c1c0b9b706070375ddf215168b9e6041fcb6 -->
