# StarCraftIIAgent — StarCraft II mod development agent

[中文](README.md)
<!-- translation-source: README.md; sha256: 71e51af9f3a8ea9318c71da9956cefc010ddf4cd7fbdc624e2c69e6583314f2a -->

SC2 custom campaign development with a shared knowledge base, 34 skills (15 root, 13 Galaxy, six SC2Data), local tools and references. **Author: 扯蛋虾米.** See [attribution](AUTHORS.en.md).

[Install](setup.en.md) · [Rules](AGENTS.en.md) · [Wiki](wiki/index.en.md) · [Tools](tools/README.en.md) · [Language](wiki/guides/agent-language.en.md) · [New skill conversations](wiki/guides/skill-conversations.en.md)

## Overview and requirements

The suite supports Catalog/Actor investigation, editable GUI triggers, existing hand-written Galaxy, campaign Banks, developer string anchors and Editor handoff. It includes WoL/HotS/LotV exports and official XSD references. The local agent-config.json determines the active project; do not infer selection from this README or directory contents.

Use Windows x64/Python 3.12 and an installed SC2 Editor for corresponding game operations, with a host able to read local files/run tools, such as Codex, Trae, Claude Code or Cursor. Shared tools require Python 3.12+; Harness2 requires Linux Python 3.12/3.13. Formal XML schema validation needs `lxml` (`python -m pip install lxml`) or executable `xmllint`; a missing backend is a failure. Trae metadata is included; rules and skills remain workspace-local. Deep API/game/third-party sources retain their original language. Skills are one shared English technical tree; the agent explains them in the chosen user language.

## Quick start

For a fresh clone, run `python tools/test-suite.py --ui-language en --scope docs` and `python tools/test-suite.py --ui-language en --scope tools` from this directory. Neither needs a selected project. See [setup](setup.en.md) for prerequisites and initialize your own Components project rather than copying the maintainer's configuration.

Git distributes generic rules, skills, code, tests and references. It excludes `projects/`, local `agent-config.json`, `.runtime/`, reports, virtual environments, credentials and personal model settings. Rebuild indexes and per-machine settings locally. [Shared CLI/MCP setup](wiki/guides/shared-tools.en.md) covers install/configure/diagnose/register; delegation also needs a local DeepSeek Harness with saved provider/model settings. Optional [Harness2](wiki/guides/harness2.en.md) needs a rebuilt Linux/WSL environment and your own Codex login. Workflows independent of those optional environments remain usable.

Describe a task normally for automatic routing. If the host does not discover workspace skills, explicitly ask it to read AGENTS.md and `skills/sc2-project-entry/SKILL.md`, then load the specialist file. A duplicate global installation of every skill is unnecessary; register global MCP/thin entries separately when needed.

“Load sc2-project-entry and help me [specific task].” The agent reads AGENTS.md, current config and wiki/index.md, then the entry skill and task-specific references. AGENT.md is an optional identity overview. Common requests:

- “Add a Blink variant to Stalker; inspect existing data first.”
- “Run appropriate static preflight checks on the current mod.”
- “Scale the paiur01 attack waves by actual difficulty.”

To select a project:

```text
My primary Mod Components folder is:
E:\Program Files (x86)\StarCraft II\Mods\MyCampaign.SC2Mod
Run tools/init-project.py, validate recursive local dependencies and update agent-config.json.
Verify identity from the actual component and run config validation.
Do not ask me to edit JSON or infer dependencies from the contents of Mods.
```

Choose a personal language with `python tools/agent-language.py --set en` or --set zh-CN; --set auto restores automatic selection. Ordinary display/query commands do not save preferences. `--ui-language` changes UI only; SC2 --locale remains independent.

## Repository and routing

AGENTS.md owns rules, AGENT.md identity, AUTHORS.md attribution and agent-config.json local paths. wiki/index.md routes tasks; wiki/catalog.md is the full inventory. skills/ contains one unified tree; Galaxy/sc2data sub-skills follow their root specialist. tools/ contains queries, validators, project paths, initialization, cache/archive and deployment helpers. DataEditorXML/ is a bounded-query reference, not automatic active data. tools/schemas/sc2-xsd/ contains formal schemas. DesignDocument.md describes general capabilities; project design belongs outside the suite. publish/ is packaging output, never source.

| Work | Skill/reference |
|---|---|
| Catalog/XML | sc2-catalog-xml, then family-specific sc2data reference |
| Actors/presentation | sc2-actor-system |
| GUI triggers/maps | sc2-map-triggers and [trigger queries](wiki/reference/trigger-knowledge.en.md) |
| Existing Galaxy | sc2-galaxy-scripting, then relevant API sub-skill |
| Persistence | sc2-bank-system |
| Developer strings | sc2-localization |
| Validation/deployment | sc2-tools-validation |
| Editor/playtest | sc2-editor-handoff |
| AI waves | sc2-attack-wave-scaling |
| Project identity and task routing | [sc2-project-entry](skills/sc2-project-entry/SKILL.md) |
| Terrain, map expansion, scenes, bridges/tunnels and scoped evidence | [sc2-terrain-editing](skills/sc2-terrain-editing/SKILL.md), [guide](wiki/guides/sc2-terrain-editing.en.md) |
| Unit-chain migration, source choices and explicit local-layer merges | [sc2-unit-migration](skills/sc2-unit-migration/SKILL.md), [guide](wiki/guides/unit-migration.en.md) |
| Official skins, models, portraits and Actor resource chains | [sc2-official-assets](skills/sc2-official-assets/SKILL.md); distinguish skin swaps from coexisting variants |
| Shared CLI/MCP diagnostics, candidates, transactions and recovery | [sc2-shared-tools](skills/sc2-shared-tools/SKILL.md), [setup](wiki/guides/shared-tools.en.md) |
| Bounded SC2 work using Harness-configured local/remote models | [sc2-deepseek-tasks](skills/sc2-deepseek-tasks/SKILL.md); review actual differences and validate independently |

## Tool quick reference

```powershell
python tools/agent-language.py --ui-language en
python tools/project-paths.py --ui-language en
python tools/validate-agent-config.py --ui-language en
python tools/inspect-mod-dependencies.py --ui-language en --json
python tools/sc2-catalog-query.py --ui-language en find Marine --limit 10
python tools/sc2-catalog-query.py --ui-language en --no-auto-rebuild show Unit:Marine
python tools/sc2-reference-query.py --ui-language en object Unit:Marine --component liberty
python tools/sc2-trigger-query.py --ui-language en libraries
python tools/sc2-trigger-query.py --ui-language en check
python tools/test-suite.py --ui-language en --scope tools
python tools/test-suite.py --ui-language en --scope docs
python tools/test-suite.py --ui-language en --scope mod --primary-only
python tools/audit-gamestrings-anchors.py --ui-language en
python tools/sc2-terrain.py --ui-language en capabilities
python tools/sc2-migrate.py --ui-language en --help
python tools/sc2-merge-mod-layers.py --ui-language en --help
python tools/sc2-local.py --ui-language en tools
python tools/deepseek-task.py --ui-language en models
```

After an Editor save, restoring missing anchors is a separate **write**: tools/audit-gamestrings-anchors.py --locale <actual locale> --fill. Deployment begins with tools/deploy-mod.py --dry-run; copying requires authorization. See [full tools guide](tools/README.en.md), [CASC](wiki/reference/official-casc-cache.en.md) and archive conversion there. Attack-wave tools inspect actual GUI definitions, preserve scheduling and generated scripts; consult the dedicated skill rather than copy historical IDs.

## Common request examples

For terrain, migration, official resources, MCP transactions, model delegation and Harness2, see [18 new skill scenarios and two multi-turn conversations](wiki/guides/skill-conversations.en.md). The existing 36 development scenarios remain below.

For Terrain Module work, see [26 drawing requests and two multi-turn conversations](wiki/guides/terrain-conversations.en.md): heights, textures, cliffs/ramps, water, roads, foliage, lighting, creep, vision, units/doodads/regions, pathing, bounds, resizing and continuation after Editor saves, with operation-specific capability and evidence limits.

Supply target, desired behavior, known unit/ability/player/region/resources, and scope (read-only/design/edit+static checks). The agent retrieves facts already in config/source; ask only for material missing inputs. Deliver actual source/evidence/check scope plus Editor/game steps. The following are requests, not executed acceptance evidence.

| Example | Copyable request and expected delivery |
|---|---|
| 1 Read a unit chain | “Investigate health, armor, weapons, abilities and production for `Unit:<unit-id>`. Show local overrides, parent and active providers, including upgrade/behavior influences. Read-only.” Return effective values/provenance, not reference assumptions. |
| 2 Base health | “Set unupgraded base health of `Unit:<unit-id>` to 120 after checking inheritance. Edit actual source, preserve upgrades/behaviors, run relevant checks; no deployment.” Report before/after and scope. |
| 3 Display mismatch | “Editor health is 120 but game shows 150. Inspect `Unit:<unit-id>`, parent, upgrades, behaviors, triggers and loaded version. Confirm cause before repairing.” Do not counteract an unknown cause with another override. |
| 4 New unit variant | “Create a project-specific variant of `Unit:<base-unit-id>`, named `<display-name>`, costing `<resource-cost>`, trained by `<building-id>`. Reuse assets, check training/card/Actor/text, follow actual project ID conventions.” Deliver full production/presentation wiring. |
| 5 Blink variant | “Add a separate Blink variant to `Unit:<unit-id>`, cooldown 10 seconds, named ‘Shadow Blink’. Keep the original, inspect buttons/requirements/card/Actor and actual project string keys.” Names follow the actual data locale; no assumed old prefixes. |
| 6 Area damage | “Implement radius `<radius>`, damage `<value>`, filtering `<factions-and-unit-types>`. Query existing ability/effect/search/Actor precedents and reuse active definitions.” Explain the actual cast/effect/filter/visual chain and validate XML. |
| 7 Temporary buff | “Buff `<unit-id>` for `<duration-in-seconds>`, changing `<attributes-and-values>`. Check stack/refresh/removal and field shapes; provide repeat/early-removal game tests.” Deliver lifecycle/scope. |
| 8 Validator | “Allow `<ability-id>` only under `<specific-condition>`. Check existing dependency validators and field shapes, then implement and validate references.” Distinguish cast-entry restrictions from effect validation. |
| 9 Upgrade | “Add `<upgrade-name>`, unlocked by `<prerequisite-tech>`, affecting `<units-and-attributes>`. Check Requirement, research ability/button/entry and duplicate unlocks; preserve existing upgrades.” Deliver independent IDs and checks. |
| 10 Missing visuals | “`<weapon-or-ability-id>` deals damage but has no projectile/hit effect. Trace effects, Actor events, models, attachments and creation/destruction; repair from evidence.” A disconnected model alone is insufficient. |
| 11 Asset replacement | “Use existing `<model-or-sound-asset>` for `<object-id>` without gameplay changes. Check path/bindings/animation/audio events; report absent assets.” Give birth/attack/death checks. |
| 12 Command-card collision | “A new button on `<unit-id>` replaced `<button>`. Inspect effective slots, Command indexes and Requirements; preserve positions unless a layout choice is needed.” Report cause, final slots and ability binding. |
| 13 Text surface | “Change `<object-id>`'s `<selection-panel-name / command-card-button-text / tooltip / world-hover-text>` in `<data-locale>`. Identify field/key first.” Do not confuse Editor names with player text or expand into whole-project translation. |
| 14 Restore anchors | “After the Editor save, some player text shows keys. Inspect `<data-locale>` GameStrings/ObjectStrings, restore missing anchors and check encoding/references; preserve existing text.” Never infer missing prose from object names. |
| 15 Initialization | “Call the mod's exported GUI init action from `<map.SC2Map>`. Check actual dependencies, Library and existing order; prevent repeats. Edit Triggers only; inspect generated Galaxy read-only.” Deliver loading/wiring evidence. |
| 16 Objective | “Complete ‘`<objective-text>`’ after destroying `<three-building-or-unit-objects>`. Save a dedicated objective handle and count only specified objects; check initial state and duplicate deaths.” Never complete another LastCreated objective. |
| 17 Victory/defeat | “Lose when `<base-object>` is destroyed and win on `<condition>`. Connect existing settlement/progress actions through GUI.” Test both paths without bypassing campaign saves. |
| 18 Region filter | “Trigger once when player `<player-number>`'s `<hero-or-unit-type>` enters `<existing-region>`. Check real objects and state.” Request missing Editor regions; test wrong players/units and reentry. |
| 19 Countdown | “Show a two-minute timer at mission start, then `<action>`. Save the timer and use the correct object for display/start/expiry.” Check repeat starts, pause and cleanup; validate GUI. |
| 20 Wave scaling | “Scale ordinary GUI attack waves in `<map.SC2Map>` by actual difficulty. Check AI startup, target points, groups and counts; preserve scheduling and use loaded definitions.” Report wrapped/unhandled scope and Editor steps. |
| 21 Custom AI migration | “Convert Custom AI personality waves in `<map.SC2Map>` to editable GUI. Preserve conditions/order/targets/count rules and AI entry.” Never edit MapScript.galaxy; report non-equivalent parts and missing references/resources. |
| 22 One-shot dialogue | “When player `<player-number>` enters `<region>`, play `<asset>` with `<model>` portrait and `<text-or-string-key>` subtitles once.” Confirm send definition/resources/player scope/state. Library compatibility is not audiovisual acceptance. |
| 23 Sequential dialogue | “Have `<character-A>`, `<character-B>`, `<character-A>` speak sequentially. Compare Transmission with existing Conversation data and use target-compatible GUI.” Save handles/context; explain waits, interruption and absent audio. |
| 24 Choices and timeout | “Show two choices leading to `<branch-A>`/`<branch-B>`; default A after ten seconds. Save handles and event player; share a single commit path for click/timeout and clean up timer/window.” Multiplayer synchronization requires explicit design. |
| 25 Skippable cinematic | “Run `<cinematic-or-dialogue-segment>`; normal finish and `<key>` skip both continue the mission. Preserve camera/selection/pause/control and share cleanup. Existing objects: `<inputs>`.” List missing Editor objects and test each exit. |
| 26 Bank design only | “Design mission/difficulty/unit-unlock Bank storage. Inspect name/format/preload; propose section/key/version/migration. No source edits.” Base choices on current evidence; don't default to standalone Galaxy. |
| 27 Bank implementation | “Implement the confirmed Bank save/load design, using agreed defaults for old files. Keep old keys and existing GUI/settlement/preload order.” Test new/old/missing/repeated saves. |
| 28 Hand-written Galaxy | “Maintain `<confirmed-handwritten-script-entry>` with a difficulty multiplier function. Confirm prefixes/include order from Triggers; edit only hand-written source and validate.” Lib*.galaxy and MapScript.galaxy stay read-only. |
| 29 Design intake | “Ingest `<attachment-or-content>` into current project data docs/design/ with sources in docs/sources.md. Separate agreed needs, undecided choices and constraints.” Project facts do not enter suite wiki/. |
| 30 Cross-session issue | “Record `<issue>`, reproduction, confirmed cause and evidence in the project ledger. Update current state/necessary decision reasons, linking rules; preserve uncommitted work.” No duplicate change diary. |
| 31 Check only | “Run applicable static checks without edits. Report actual target, dependency scope and passing/failing checks; use explicit map targets.” Without Editor/game evidence the highest state is static validation passed. |
| 32 Editor evidence | “After external edits, saving causes `<disappearing-actions-or-changed-parameters>`. Here are before/after files and Editor version. Compare GUI ownership/sub-actions/generated calls, then repair source.” Keep static and Editor results separate. |
| 33 Runtime logs | “The package shows `<observed-behavior>`; steps `<steps>`, logs/screenshots `<path>`. Check loaded version, calls/assets, confirm cause and repair.” Give matched retest steps; static success is not runtime success. |
| 34 Deployment preview | “Preview current source_mode deployment: source, target, overwrite scope; no copy.” After review: “Deploy in that verified direction, retain recovery and verify copying; give Editor reload/save steps.” Preview alone does not authorize copying; publish/ is never source. |
| 35 Reference index | “Official Mods: `<directory>`; Campaigns: `<directory>`. Build an external trigger reference index and list curated mechanisms. No project selection/source edits; report missing metadata.” Return fingerprints; target availability still needs target evidence. |
| 36 Suite maintenance | “Fix `<tool-or-documentation-issue>` in this workspace, preserve uncommitted work and project selection. Reuse current paths/implementation and run tools/docs checks.” Deliver reasons, scope and untested behavior without modifying projects or official sources. |

More setup conversations: [installation](setup.en.md). Trigger-specific conversations: [44 scenarios and two dialogues](wiki/reference/trigger-agent-dialogue-examples.en.md); underlying mechanisms: [in-game cases](wiki/reference/trigger-dialogue-examples.en.md).

## Hard rules and limitations

[AGENTS](AGENTS.en.md) is authoritative: prefer GUI, never hand-edit generated scripts/publish/, confirm identity and effective values, use formal schema/static checks, and advance exact lifecycle stages only with evidence. XML comments/attributes use ASCII; no AbilAutoCmd button type or CBehaviorBuff InitEffect; locals at function top, conservative while/explicit assignments and extensionless includes.

For terrain editing, map expansion and scene composition, load the [terrain skill](skills/sc2-terrain-editing/SKILL.md) and query current capabilities. Supported operations may write isolated Components copies; acceptance remains scoped to observed operations. Editor save/reopen, visual checks, unsupported-operation experiments and cinematics require the actual Editor. The agent may perform authorized steps when GUI control is verifiably available; hand off necessary unavailable steps to the user. Follow the [handoff skill](skills/sc2-editor-handoff/SKILL.md) for save and anchor checks; capture raw terrain experiment differences first. Never open Blizzard maps with a project mod external override. Add dependencies through Map → Modules → Dependencies. For os error 206/replacement errors see wiki/implementation/agent-context-efficiency.md (English technical reference). If local rules cannot be read, verify host file access and workspace location rather than assume another installation.

## Independent use and project files

Open this directory as an independent workspace; paths are relative to it and projects are selected through initialization. Sync tools/skills/wiki with Git; keep machine config and runtime data local. Project facts live in the project data directory returned by tools/project-paths.py; docs can be versioned separately, runtime/ is ignored. No whole-project translation/encyclopedia service is implied by bilingual agent usage. No automatic commit, push, deployment or background task is implied by a query.
