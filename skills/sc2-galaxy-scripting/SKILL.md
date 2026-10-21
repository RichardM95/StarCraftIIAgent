---
name: sc2-galaxy-scripting
description: StarCraft II Galaxy scripting rules and gotchas for the selected project. Use when writing, editing, or debugging .galaxy files, trigger custom scripts, bank logic, or UI/dialog code. Covers syntax constraints, source-of-truth, modular script boundaries, and deployment.
---

# SC2 Galaxy Scripting

## When to Use

Load this skill when the task involves Galaxy script (`.galaxy` files): writing trigger actions, bank persistence, dialog/UI code, unit events, or any custom script block. Also load when debugging "function not found", parse errors, or linker drops.
Do not select standalone Galaxy for a new trigger merely because SC2 compiles GUI triggers to Galaxy. Follow `sc2-map-triggers` for GUI-first authoring; use this skill for an explicitly requested Galaxy implementation, existing script maintenance, or a necessary embedded Custom Script block.

This skill is the **Galaxy router**. It owns project compatibility policy, source-of-truth rules, modular script boundaries, and deployment. For deep Galaxy API work (specific native calls, subsystem APIs, struct/enum references), route to the appropriate `galaxy-*` sub-skill under `skills/galaxy/` after loading this skill.

## Galaxy Sub-Skill Router

For deep Galaxy script API work, load the matching `galaxy-*` sub-skill under `skills/galaxy/`. This skill retains the project **compatibility policy** and **source-of-truth** rules that all sub-skills obey.

| Task | Sub-skill | Path |
|---|---|---|
| Core syntax, types, structs, arrays, control flow | `galaxy-language-fundamentals` | `skills/galaxy/galaxy-language-fundamentals/SKILL.md` |
| File structure, include order, modular layout | `galaxy-code-organization` | `skills/galaxy/galaxy-code-organization/SKILL.md` |
| Math, strings, type conversion, colors, bit ops | `galaxy-math-strings-conversion` | `skills/galaxy/galaxy-math-strings-conversion/SKILL.md` |
| Units: creation, properties, XP/upgrade, groups, orders | `galaxy-units-and-groups` | `skills/galaxy/galaxy-units-and-groups/SKILL.md` |
| Points, regions, geometry, pathing | `galaxy-points-regions-geometry` | `skills/galaxy/galaxy-points-regions-geometry/SKILL.md` |
| Players, alliances, race, resources, camera, difficulty | `galaxy-players-and-alliances` | `skills/galaxy/galaxy-players-and-alliances/SKILL.md` |
| Actor visuals: ActorSend, AttachModelToUnit, PlayAnimation | `galaxy-actor-and-visuals` | `skills/galaxy/galaxy-actor-and-visuals/SKILL.md` |
| Sound, music, camera, cinematic, weather, lighting | `galaxy-sound-camera-environment` | `skills/galaxy/galaxy-sound-camera-environment/SKILL.md` |
| UI dialogs, XML frames, hero/upgrade panels, HUD, SSF | `galaxy-ui-and-dialogs` | `skills/galaxy/galaxy-ui-and-dialogs/SKILL.md` |
| Triggers: TriggerExecute, event registration, async | `galaxy-triggers-and-functions` | `skills/galaxy/galaxy-triggers-and-functions/SKILL.md` |
| Game systems: bank save/load, spawner, waves, revive, tech | `galaxy-game-systems` | `skills/galaxy/galaxy-game-systems/SKILL.md` |
| AI behavior, tech tree, wave difficulty scaling | `galaxy-ai-and-techtree` | `skills/galaxy/galaxy-ai-and-techtree/SKILL.md` |
| Debug, Data Table, Catalog runtime, UserData | `galaxy-debug-data-catalog` | `skills/galaxy/galaxy-debug-data-catalog/SKILL.md` |

> Sub-skills complement the existing top-level skills: `sc2-bank-system` (bank schema/persistence), `sc2-map-triggers` (trigger XML wiring), `sc2-attack-wave-scaling` (GUI wave count wrappers). When a sub-skill topic overlaps with a top-level skill, the top-level skill owns project conventions and the sub-skill owns API reference.

## Source of Truth

- **Edit only:** the hand-authored source referenced by the actual target Triggers and its include chain. Resolve the source component from `agent-config.json`. A historical script filename is not proof that the current project still uses it.
- **Do NOT edit:** `Lib*.galaxy` (compiled library wrappers, auto-generated and overwritten on Editor save) or `MapScript.galaxy` inside maps (auto-generated).
- **Deploy:** In `workspace_copy` mode, preview then use `python tools/deploy-mod.py` to copy component sources to SC2. In `in_place` mode no deployment is needed. The SC2 Editor, not this tool, regenerates compiled wrappers on save.

## Compatibility policy and reference

For hand-written code use `while`, explicit assignment (`i = i + 1;`), and function-top declarations with runtime assignments after them. These are conservative workspace conventions, not proof that all alternatives are unsupported by the Galaxy language.

The [syntax notes](../../wiki/implementation/galaxy-gotchas.md) own the detailed examples and compilation caveats; the language sub-skill supplies type/API reference. Preserve whole function boundaries, avoid duplicate definitions, and inspect the actual include/call order.

For embedded ScriptCode, copy the structure/indentation of an Editor-saved block of the same type in the target component and inspect generated code after saving. No universal four-space or sixteen-space prefix is established. XML parsing and the static validator do not compile embedded scripts.

## Existing Script Includes

For maintenance of existing Galaxy, inspect the target library and its saved Custom Script/include declarations first. Preserve include order and verify generated output after an Editor save; edit the hand-authored entry, not the generated wrapper. If a feature has migrated to GUI, maintain that GUI source rather than recreating its old external script. New standalone scripts require the implementation choice described above.

## Map-to-Mod Calls Must Use GUI Actions

Define exported GUI actions in the mod and call them from map triggers. This is the conservative workspace wiring practice; verify actual generated output. The universal linker claim lacks a versioned reproduction; see [evidence scope](../../wiki/reference/trigger-knowledge.md#编辑器行为的证据范围).

## Project identity and error triage

Library IDs, function/global prefixes and Bank names come from the actual target source. Preserve existing interfaces. Use [syntax/error notes](../../wiki/implementation/galaxy-gotchas.md#community-error-triage) for compiler symptoms rather than maintaining a second table here.

## Reference

- Deep syntax primer: `wiki/reference/galaxy-language.md`
- Bank function signatures: `wiki/reference/galaxy-bank.md`
- Gotchas source: `wiki/implementation/galaxy-gotchas.md`
- Bank system design: `wiki/implementation/bank-system.md`

## Native and event lookup

Query exact native names, parameters and constants from the target definitions and cross-check actual native declarations or Editor-generated output. Unit creation, training, warp completion, morph and re-entry have distinct semantics; select the required event and verify per-unit de-duplication. Timer scans use their current iteration object, not an unrelated event response.
