# StarCraftIIAgent — StarCraft II mod development agent

[中文](README.md)
<!-- translation-source: README.md; sha256: 4f044690da5fbd16577fc8b8f62e69edc6cd3f098c54d580b3acb89dba47b986 -->

SC2 custom campaign development with a shared knowledge base, 29 skills (10 root, 13 Galaxy, six sc2data), local tools and references. **Author: 扯蛋虾米.** See [attribution](AUTHORS.en.md).

[Install](setup.en.md) · [Rules](AGENTS.en.md) · [Wiki](wiki/index.en.md) · [Tools](tools/README.en.md) · [Language](wiki/guides/agent-language.en.md)

## Overview and requirements

The suite supports Catalog/Actor investigation, editable GUI triggers, existing hand-written Galaxy, campaign Banks, developer string anchors and Editor handoff. It includes WoL/HotS/LotV exports and official XSD references. The local agent-config.json determines the active project; do not infer selection from this README or directory contents.

Use Windows/Python and an installed SC2 Editor for corresponding game operations, with a host able to read local files/run tools. Trae metadata is included; rules and skills remain workspace-local. Deep API/game/third-party sources retain their original language. Skills are one shared English technical tree; the agent explains them in the chosen user language.

## Quick start

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
```

After an Editor save, restoring missing anchors is a separate **write**: tools/audit-gamestrings-anchors.py --locale <actual locale> --fill. Deployment begins with tools/deploy-mod.py --dry-run; copying requires authorization. See [full tools guide](tools/README.en.md), [CASC](wiki/reference/official-casc-cache.en.md) and archive conversion there. Attack-wave tools inspect actual GUI definitions, preserve scheduling and generated scripts; consult the dedicated skill rather than copy historical IDs.

## Common request examples

Supply target, desired behavior, known unit/ability/player/region/resources, and scope (read-only/design/edit+static checks). The agent retrieves facts already in config/source; ask only for material missing inputs. Deliver actual source/evidence/check scope plus Editor/game steps. The following are requests, not executed acceptance evidence.

| Example | Copyable request and expected delivery |
|---|---|
| 1 Read a unit chain | “Investigate health, armor, weapons, abilities and production for Unit:<单位ID>. Show local overrides, parent and active providers, including upgrade/behavior influences. Read-only.” Return effective values/provenance, not reference assumptions. |
| 2 Base health | “Set unupgraded base health of Unit:<单位ID> to 120 after checking inheritance. Edit actual source, preserve upgrades/behaviors, run relevant checks; no deployment.” Report before/after and scope. |
| 3 Display mismatch | “Editor health is 120 but game shows 150. Inspect Unit:<单位ID>, parent, upgrades, behaviors, triggers and loaded version. Confirm cause before repairing.” Do not counteract an unknown cause with another override. |
| 4 New unit variant | “Create a project-specific variant of Unit:<原单位ID>, named <名称>, costing <资源成本>, trained by <建筑ID>. Reuse assets, check training/card/Actor/text, follow actual project ID conventions.” Deliver full production/presentation wiring. |
| 5 Blink variant | “Add a separate Blink variant to Unit:<单位ID>, cooldown 10 seconds, named ‘Shadow Blink’. Keep the original, inspect buttons/requirements/card/Actor and actual project string keys.” Names follow the actual data locale; no assumed old prefixes. |
| 6 Area damage | “Implement radius <范围>, damage <数值>, filtering <阵营与单位类型>. Query existing ability/effect/search/Actor precedents and reuse active definitions.” Explain the actual cast/effect/filter/visual chain and validate XML. |
| 7 Temporary buff | “Buff <单位ID> for <秒数>, changing <属性与数值>. Check stack/refresh/removal and field shapes; provide repeat/early-removal game tests.” Deliver lifecycle/scope. |
| 8 Validator | “Allow <技能ID> only under <具体条件>. Check existing dependency validators and field shapes, then implement and validate references.” Distinguish cast-entry restrictions from effect validation. |
| 9 Upgrade | “Add <升级名称>, unlocked by <前置科技>, affecting <单位和属性>. Check Requirement, research ability/button/entry and duplicate unlocks; preserve existing upgrades.” Deliver independent IDs and checks. |
| 10 Missing visuals | “<武器或技能ID> deals damage but has no projectile/hit effect. Trace effects, Actor events, models, attachments and creation/destruction; repair from evidence.” A disconnected model alone is insufficient. |
| 11 Asset replacement | “Use existing <模型或音效资源> for <对象ID> without gameplay changes. Check path/bindings/animation/audio events; report absent assets.” Give birth/attack/death checks. |
| 12 Command-card collision | “A new button on <单位ID> replaced <按钮>. Inspect effective slots, Command indexes and Requirements; preserve positions unless a layout choice is needed.” Report cause, final slots and ability binding. |
| 13 Text surface | “Change <对象ID>'s <选择面板名称 / 命令卡按钮文字 / tooltip / 世界悬停文字> in <语言>. Identify field/key first.” Do not confuse Editor names with player text or expand into whole-project translation. |
| 14 Restore anchors | “After the Editor save, some player text shows keys. Inspect <语言> GameStrings/ObjectStrings, restore missing anchors and check encoding/references; preserve existing text.” Never infer missing prose from object names. |
| 15 Initialization | “Call the mod's exported GUI init action from <地图.SC2Map>. Check actual dependencies, Library and existing order; prevent repeats. Edit Triggers only; inspect generated Galaxy read-only.” Deliver loading/wiring evidence. |
| 16 Objective | “Complete ‘<目标文字>’ after destroying <三个建筑或单位对象>. Save a dedicated objective handle and count only specified objects; check initial state and duplicate deaths.” Never complete another LastCreated objective. |
| 17 Victory/defeat | “Lose when <基地对象> is destroyed and win on <条件>. Connect existing settlement/progress actions through GUI.” Test both paths without bypassing campaign saves. |
| 18 Region filter | “Trigger once when player <编号>'s <英雄或单位类型> enters <已建立区域>. Check real objects and state.” Request missing Editor regions; test wrong players/units and reentry. |
| 19 Countdown | “Show a two-minute timer at mission start, then <动作>. Save the timer and use the correct object for display/start/expiry.” Check repeat starts, pause and cleanup; validate GUI. |
| 20 Wave scaling | “Scale ordinary GUI attack waves in <地图.SC2Map> by actual difficulty. Check AI startup, target points, groups and counts; preserve scheduling and use loaded definitions.” Report wrapped/unhandled scope and Editor steps. |
| 21 Custom AI migration | “Convert Custom AI personality waves in <地图.SC2Map> to editable GUI. Preserve conditions/order/targets/count rules and AI entry.” Never edit MapScript.galaxy; report non-equivalent parts and missing references/resources. |
| 22 One-shot dialogue | “When player <编号> enters <区域>, play <资源> with <模型> portrait and <文字或键> subtitles once.” Confirm send definition/resources/player scope/state. Library compatibility is not audiovisual acceptance. |
| 23 Sequential dialogue | “Have <角色A>, <角色B>, <角色A> speak sequentially. Compare Transmission with existing Conversation data and use target-compatible GUI.” Save handles/context; explain waits, interruption and absent audio. |
| 24 Choices and timeout | “Show two choices leading to <分支A>/<分支B>; default A after ten seconds. Save handles and event player; share a single commit path for click/timeout and clean up timer/window.” Multiplayer synchronization requires explicit design. |
| 25 Skippable cinematic | “Run <过场或对白段落>; normal finish and <按键> skip both continue the mission. Preserve camera/selection/pause/control and share cleanup. Existing objects: <输入>.” List missing Editor objects and test each exit. |
| 26 Bank design only | “Design mission/difficulty/unit-unlock Bank storage. Inspect name/format/preload; propose section/key/version/migration. No source edits.” Base choices on current evidence; don't default to standalone Galaxy. |
| 27 Bank implementation | “Implement the confirmed Bank save/load design, using agreed defaults for old files. Keep old keys and existing GUI/settlement/preload order.” Test new/old/missing/repeated saves. |
| 28 Hand-written Galaxy | “Maintain <已确认手写脚本入口> with a difficulty multiplier function. Confirm prefixes/include order from Triggers; edit only hand-written source and validate.” Lib*.galaxy and MapScript.galaxy stay read-only. |
| 29 Design intake | “Ingest <附件或内容> into current project data docs/design/ with sources in docs/sources.md. Separate agreed needs, undecided choices and constraints.” Project facts do not enter suite wiki/. |
| 30 Cross-session issue | “Record <问题>, reproduction, confirmed cause and evidence in the project ledger. Update current state/necessary decision reasons, linking rules; preserve uncommitted work.” No duplicate change diary. |
| 31 Check only | “Run applicable static checks without edits. Report actual target, dependency scope and passing/failing checks; use explicit map targets.” Without Editor/game evidence the highest state is static validation passed. |
| 32 Editor evidence | “After external edits, saving causes <动作消失或参数变化>. Here are before/after files and Editor version. Compare GUI ownership/sub-actions/generated calls, then repair source.” Keep static and Editor results separate. |
| 33 Runtime logs | “The package shows <现象>; steps <步骤>, logs/screenshots <路径>. Check loaded version, calls/assets, confirm cause and repair.” Give matched retest steps; static success is not runtime success. |
| 34 Deployment preview | “Preview current source_mode deployment: source, target, overwrite scope; no copy.” After review: “Deploy in that verified direction, retain recovery and verify copying; give Editor reload/save steps.” Preview alone does not authorize copying; publish/ is never source. |
| 35 Reference index | “Official Mods: <目录>; Campaigns: <目录>. Build an external trigger reference index and list curated mechanisms. No project selection/source edits; report missing metadata.” Return fingerprints; target availability still needs target evidence. |
| 36 Suite maintenance | “Fix <工具或文档问题> in this workspace, preserve uncommitted work and project selection. Reuse current paths/implementation and run tools/docs checks.” Deliver reasons, scope and untested behavior without modifying projects or official sources. |

More setup conversations: [installation](setup.en.md). Trigger-specific conversations: [44 scenarios and two dialogues](wiki/reference/trigger-agent-dialogue-examples.en.md); underlying mechanisms: [in-game cases](wiki/reference/trigger-dialogue-examples.en.md).

## Hard rules and limitations

[AGENTS](AGENTS.en.md) is authoritative: prefer GUI, never hand-edit generated scripts/publish/, confirm identity and effective values, use formal schema/static checks, and advance exact lifecycle stages only with evidence. XML comments/attributes use ASCII; no AbilAutoCmd button type or CBehaviorBuff InitEffect; locals at function top, conservative while/explicit assignments and extensionless includes.

Editor opening/saving, terrain/regions/doodads/pathing and cinematics require the operator. Never open Blizzard maps with a project mod external override. Add dependencies through Map → Modules → Dependencies. For os error 206/replacement errors see wiki/implementation/agent-context-efficiency.md (English technical reference). If local rules cannot be read, verify host file access and workspace location rather than assume another installation.

## Independent use and project files

Open this directory as an independent workspace; paths are relative to it and projects are selected through initialization. Sync tools/skills/wiki with Git; keep machine config and runtime data local. Project facts live in the project data directory returned by tools/project-paths.py; docs can be versioned separately, runtime/ is ignored. No whole-project translation/encyclopedia service is implied by bilingual agent usage. No automatic commit, push, deployment or background task is implied by a query.
