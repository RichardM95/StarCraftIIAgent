# Skill invocation and conversation examples

[中文](skill-conversations.md)

Start in the cloned workspace and have the agent read [AGENTS.md](../../AGENTS.en.md) and the [project entry skill](../../skills/sc2-project-entry/SKILL.md). The workspace contains **34 skills: 15 root skills, 13 Galaxy sub-skills and six SC2Data sub-skills**. See the [README routes](../../README.en.md#repository-and-routing); the Galaxy and SC2Data roots own their detailed sub-routing.

## Invoking skills

For layer-specific drawing, see [26 terrain scenarios and two multi-turn conversations](terrain-conversations.en.md), covering heights, textures, cliffs/ramps, water, objects, pathing and continuation after saves. This page retains cross-skill integration and collaboration examples.

Describe the task normally, or explicitly request: “Read `skills/<skill-id>/SKILL.md` and follow its workflow.” Workspace skills may not appear in the host's global skill menu; explicit file loading works without that discovery. Use the host's selector if it already discovers the skill. Typing `$skill-name` alone does not install anything.

Replace every `<...>` with actual input. An explicit map determines the terrain target. Mod initialization, temporary map investigation, model delegation and global registration are separate actions. Specify UI language independently of the SC2 data locale. Keep credentials out of chats, packets and Git.

## Copyable requests

| Number | Scenario and skill | Request to the agent | Expected result |
|---|---|---|---|
| 01 | Fresh-machine check: `sc2-project-entry`, `sc2-tools-validation` | “This workspace was just cloned. Check rules, skills and tools; run tools/docs checks. Do not select a project or reuse another machine's configuration.” | Check results and missing dependencies; explicitly report an uninitialized project. |
| 02 | Explicit skill loading | “Read AGENTS.md, skills/sc2-project-entry/SKILL.md and skills/sc2-terrain-editing/SKILL.md. Target `<map.SC2Map>`; investigate read-only.” | Actual map, capabilities and scope; the selected mod does not replace the map target. |
| 03 | Read-only terrain investigation: `sc2-terrain-editing` | “Inspect `<map.SC2Map>` format, dimensions, playable bounds, existing objects and terrain capabilities. Query capabilities first; use bounded audits/previews without writes.” | Components/archive distinction, evidence and gaps; previews do not prove native rendering or pathfinding. |
| 04 | Expansion and composition: `sc2-terrain-editing` | “Use `<latest-saved-map>` to expand `<direction-and-functional-space>` into `<new-workspace-copy>`. Read map-adaptation, preserve story references, roads and coordinate constraints. Establish connected spaces before dressing.” | Explicit source/output, hash-bound plan, actual diff and separate copy; unverified connections remain open. |
| 05 | Facing, grounding and blocking: `sc2-terrain-editing` | “Move/orient `<object-selection>`. Ground ordinary objects, preserve authored bridge-deck heights, inspect existing occupancy and reserved routes; add static blockers only with evidence.” | Position, facing, height-mode and blocker-ownership differences; reservation circles do not prove native collision. |
| 06 | Bridge or tunnel: `sc2-terrain-editing`, `sc2-catalog-xml` | “Investigate why `<bridge-or-tunnel-object>` may look connected but remain impassable. Check active dependencies, model, footprint, both approaches and required vehicles; prepare a separate repair candidate.” | Data/terrain evidence, candidate and infantry/vehicle tests; a static image cannot establish crossing. |
| 07 | Editor evidence: `sc2-terrain-editing`, `sc2-editor-handoff` | “Validate `<one-operation>` on an isolated copy. Use authorized, verifiably available GUI control for save/close/reopen; otherwise list only necessary user steps. Capture raw save differences before anchor restoration.” | Evidence bound to the operation/artifact; one save does not validate every terrain capability. |
| 08 | Mission objects and GUI organization: `sc2-map-triggers` | “Wire editable GUI objectives/interactions for `<mission-objects>` in `<map.SC2Map>` and organize trigger folders. Preserve references, initialization and behavior; generated Galaxy stays read-only.” | GUI/reference checks, structural diff and handoff; fixed project scripts are not generic map tools. |
| 09 | Selective migration: `sc2-unit-migration` | “Transfer `<unit-ids>` from `<source-mod-list>` to `<target-mod>`. First analyze complete official baselines, duplicate sources, chains and external mechanisms. Generate selection/plan only.” | Source choices, ID mapping and gaps; incomplete provenance or unresolved dynamic references block executable export. |
| 10 | Explicit local overrides: `sc2-unit-migration` | “I explicitly want raw local-layer merging including overrides on official IDs. Sources run `<low-to-high-priority>`, target dependencies stay fixed. Show whole-entry conflicts, retained official references and backup plan first.” | Distinguish raw layers from complete playable-unit migration; verify target/plan before writes. |
| 11 | Official resources: `sc2-official-assets`, `sc2-actor-system` | “Find official model, portrait and audio chains for `<theme-or-skin>` on `<object-id>`. Distinguish a skin replacement from a coexisting unit variant; verify active dependencies and actual assets.” | Scoped index hits, Actor/resource chain and readability; a hit is not visual acceptance. |
| 12 | MCP and local tools: `sc2-shared-tools` | “Investigate `<asset-reference/map-shell/region-environment/editor-warning>` for `<explicit-target>`. Read the current tool schema; prefer connected MCP, otherwise use the shared local implementation.” | Entry, target and business diagnosis; existing Catalog/GUI/terrain/localization workflows retain their tools. |
| 13 | Uncertain transaction: `sc2-shared-tools` | “Connection dropped while applying `<candidate-id>`. Query the original transaction and source fingerprints first. Do not resubmit or switch CLI transport to bypass a refusal; continue or restore from confirmed state.” | Original task/transaction state, conflicts and recovery conditions; no unverified repeated write. |
| 14 | Model delegation: `sc2-deepseek-tasks` | “List saved Harness provider/model IDs and use `<provider>/<model>` for `<independent-SC2-subtask>`. Allow only `<file-list>`; define goal, constraints and acceptance before isolated execution.” | Bounded packet, shared task ID, actual candidate diff and primary-agent validation; no exposed keys. |
| 15 | Reconnect and cancel: `sc2-deepseek-tasks` | “Query original `<task-id>` without dispatching again. If still running, cancel it and identify unintegrated candidates.” | Original status and cancellation result; worker completion cannot establish Editor/runtime acceptance. |
| 16 | Skill optimization: `sc2-tools-validation` and Harness2 | “Optimize `<registered-skill-id>` using existing Harness2. Freeze model/source fingerprints, establish baseline, run one parallel round and independent cases. Review the full diff; retain unchanged if benefit is unreliable.” | Cases, knowledge mapping and actual input tokens; grouped adoption requires an observed routing correction or at least 10% lower mean input including reference reads. |
| 17 | Shared-tool setup: `sc2-shared-tools` | “Follow shared-tools to check Python 3.12 and my local Harness, install isolated environments, use my saved provider configuration, diagnose and register global entries. Preserve other MCP services and Hub ownership.” | Local setup, backups and diagnosis; report MCP available only after an actual client connection. |
| 18 | Git distribution: `sc2-tools-validation` | “Check whether generic tools, skills and instructions distribute independently. Exclude projects, local configuration, environments, credentials, reports and runtime state, then run tools/docs checks.” | Distribution evidence; project maps and historical outputs stay outside suite Git. |

Existing Catalog, Actor, Bank, Galaxy, localization, attack-wave and trigger tasks retain the [README's 36 scenarios](../../README.en.md#common-request-examples) and [trigger conversations](../reference/trigger-agent-dialogue-examples.en.md). New capabilities preserve GUI-first, effective-value and generated-source boundaries.

## Multi-turn collaboration

### Map expansion and acceptance

**User:** “Add an equipment courtyard north of `<map>`, output to `<new-copy>`, preserve roads and mission references.”

**Agent:** Verify latest saved source, capabilities and references; prepare connected spaces/composition, execute authorized edits on the copy and report actual differences/static checks. Keep occlusion, slopes and bridge travel as distinct acceptance items.

**User:** “It still looks empty. Add substantial buildings around it and reserve vehicle access.”

**Agent:** Inspect large forms, silhouettes and passages on the current copy; use evidenced occupancy and height modes. Assess appearance only from actual rendered/Editor observations, rather than prop totals or top-down dots.

**User:** “Folders persisted and compilation passed after save/reopen, but the bridge remains untested.”

**Agent:** Record `Editor accepted` for folder persistence/compilation, leaving bridge travel, vehicles and other scenarios open. Close the map before further external edits and bind the next plan to its latest saved state.

### Model delegation and integration

**User:** “Use `<provider>/<model>` for one independent subproblem in `<authorized-SC2-task>`.”

**Agent:** Define scope, allowed files, evidence and acceptance; submit once against an isolated copy and retain request_id/task_id.

**User:** “The interface disconnected. Continue now.”

**Agent:** Query the original task without redispatching. Review actual differences, fingerprints, bridge events and boundary flags; validate independently and integrate eligible changes through the same transaction workflow.

**User:** “The worker says it is fixed. Can we report a game pass?”

**Agent:** Report only the proven gate; static checks establish at most `static validation passed`. Editor save/reopen and game scenarios need their own evidence, which model prose cannot replace.

## Commands and recovery

Run from the workspace root; use each tool's `--help` for its current interface:

```powershell
python tools/test-suite.py --ui-language en --scope docs
python tools/test-suite.py --ui-language en --scope tools
python tools/sc2-terrain.py --ui-language en capabilities
python tools/sc2-migrate.py --ui-language en --help
python tools/sc2-local.py --ui-language en tools
python tools/deepseek-task.py --ui-language en models
python tools/harness2.py --ui-language en sc2-optimize --skill galaxy-language-fundamentals
```

The first two checks need no active project. Shared CLI requires [local environments](shared-tools.en.md); delegation also needs the local Harness/provider. Harness2 optimization requires [Linux/WSL, Codex login and model connectivity](harness2.en.md) and consumes model quota. Examples do not grant unrelated deployment, registration or external writes; follow the user's actual authorized target/scope. Recovery uses the corresponding task/transaction/experiment state and fingerprints, preserving later user edits.

<!-- translation-source: wiki/guides/skill-conversations.md; sha256: b0e0796f5f8c31409cac4e7f2e4cac619b8cd4d0adda59066acd74a72edae16d -->
