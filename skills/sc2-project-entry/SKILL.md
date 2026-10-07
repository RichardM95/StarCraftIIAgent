---
name: sc2-project-entry
description: StarCraft II mod and campaign implementation entry point. Use for SC2Mod/SC2Map, catalog XML, Galaxy, triggers, actors, localization, or Editor handoff; route to the relevant specialist skill.
---

# SC2 Project Entry (Unified Router)

## When to Use

Load this skill for SC2 mod or campaign implementation. Read `agent-config.json` when project paths matter and `AGENTS.md` for repository rules. For documentation or tool-only maintenance, use the relevant file directly. Specialist skills (galaxy-scripting, catalog-xml, map-triggers, tools-validation, editor-handoff, etc.) provide the task-specific detail.

When the user supplies a primary Components `.SC2Mod` folder path and asks to initialize or select a project, run `python tools/init-project.py "<path>"` directly. Do not ask the user to edit `agent-config.json` or list dependencies. Ask for extra paths only if the tool cannot infer a nonstandard layout. After initialization, verify the project-specific identity from evidence; never guess a Bank name, Library ID, script block, or code prefix.

## Project Rules

`AGENTS.md` owns the current mod identity, editing scope, Galaxy/XML constraints, and key paths. Read `agent-config.json` for machine-specific paths. Use the relevant specialist skill for detailed implementation rules; do not maintain a second copy here.

## Task Routing

After reading this skill, route to the appropriate deep skill based on the task. Sub-skills under `skills/galaxy/` and `skills/sc2data/` are loaded after the corresponding top-level router skill.
For a new trigger request, route to `sc2-map-triggers` and prefer editable GUI events, conditions, and actions. Use embedded Custom Script only for a small part that GUI cannot reasonably express; choose standalone Galaxy only when the user explicitly requests it or the task maintains existing Galaxy source.

| Task type | Load next skill | Wiki page |
|---|---|---|
| Writing/editing Galaxy script | `sc2-galaxy-scripting` | `wiki/implementation/galaxy-gotchas.md`, `wiki/reference/galaxy-language.md` |
| Writing/editing mod XML (units, abilities, behaviors, effects, weapons, upgrades, validators, footprints) | `sc2-catalog-xml` | `wiki/implementation/xml-patterns.md`, `wiki/implementation/xml-patterns/catalog-rules.md` |
| Deep actor work (CActorUnit/Action/Model/Beam/Sound, VFX/audio, texture swaps, morph transitions, inactive-XML extraction) | `sc2-actor-system` | `wiki/reference/actors.md`, `wiki/implementation/xml-patterns/editor-roundtrip-and-actors.md` |
| Editing map triggers, GUI action wiring, victory/defeat hooks | `sc2-map-triggers` | `wiki/reference/triggers-overview.md`, `wiki/implementation/per-map-setup.md` |
| Bank system, campaign persistence, mission saves, unlocks | `sc2-bank-system` | `wiki/implementation/bank-system.md`, `wiki/reference/galaxy-bank.md` |
| Localization (GameStrings/ObjectStrings/TriggerStrings), string anchors, blank editor names, GameHotkeys | `sc2-localization` | `wiki/implementation/localization.md` |
| Extracting hardcoded UI text from `.SC2Layout` layouts and Galaxy `StringToText` into GameStrings keys | `sc2-ui-string-extraction` | `wiki/implementation/localization.md` |
| English/Chinese translation and terminology review | `sc2-translation` | `wiki/design/sc2-translation.md` |
| Running tools, validation, deployment | `sc2-tools-validation` | `tools/README.md` |
| Editor handoff, issue lifecycle, playtest | `sc2-editor-handoff` | `wiki/guides/editor-handoff.md`, `wiki/implementation/testing-feedback-workflow.md` |
| Attack wave scaling, AI personality wave migration | `sc2-attack-wave-scaling` | `skills/sc2-attack-wave-scaling/references/ai-personality-to-gui-triggers.md` |

## Specialist Routing

After loading `sc2-galaxy-scripting` or `sc2-catalog-xml`, use that skill's own sub-skill table for the specific Galaxy API or catalog family.

## Large Lookup Sources (do NOT read start-to-finish)

- `DataEditorXML/*.txt` — selected catalog dumps already covered by the graph; grep one identified file for exact fields
- `DataEditorXML/SC2GameDataComponents/` — query with `tools/sc2-reference-query.py`, restricting family, component, and area
- `sc2-catalog-graph-out/` — query with `tools/sc2-catalog-query.py`
- `wiki/reference/triggers-native/` — native function signatures
- Git history (`git log -n <N> -- <path>`) for historical provenance

## What Requires SC2 Editor GUI (Agent cannot do these)

- Opening and saving Blizzard maps (requires SC2 account login)
- Terrain, regions, doodads, pathing
- Cutscenes and cinematics
- Saving mod/map as Components (user action)

## Chinese Task Knowledge (Merged)

Distilled from `references/project-and-sources.md` and `references/source-caveats.md`. No external network or game-run verification was performed.

### Sibling Dependency Mods
Do not infer active dependencies by enumerating sibling folders under `Mods/`. Start at the primary mod, use `ComponentList.SC2Components` to locate its info component, read `<Dependencies>`, and recursively repeat for each locally resolved component mod. Presence on disk alone does not prove a dependency is active.

### New Mod Identity Rule
- A new mod must adopt its own identity and naming prefix. Do not blanket-replace `libEpi_` / `libEpi_g_` / `AeonOfIhanriiBank` / `LegacyoftheIhanrii` strings in user mods — those are AeonOfIhanrii-specific. Old docs referencing `CCM`, `TF`, or fixed deploy paths are historical examples only; resolve current locations from `agent-config.json`.
- Always confirm actual mod identity, deploy path, and naming prefix from the project's `AGENTS.md` / library XML / GUI Action Definition before writing code.

### Source Caveats (from `source-caveats.md`)
- **Old project prefix conflict:** Source docs mix `CCM`, `TF`, and `libEpi_` prefixes. Decide per current project identity; do not unify-replace across all user mods.
- **Export override conflict (cross-ref):** Inactive XML folders may include Coop Commanders references, and complete inactive XML folders may not exist. See `sc2-catalog-xml` Source Caveats for the operational rule.

## Tool Commands

Use `tools/README.md` and each tool's `--help` for current commands and arguments. Project paths come from `agent-config.json`; sample data stays under this workspace's `DataEditorXML/SC2GameDataComponents/`.

## Implementation Workflow

1. **Record effective values:** Before editing statistics, record the object ID, parent, accurate field/array index, effective value provided by active dependencies, and intended override. Missing local field ≠ value is zero.
2. **Query before write:** Query the current project and active dependencies through the catalog graph; if it reports stale inputs, refresh once with `python tools/build-sc2-catalog-graph.py --sqlite-only` before relying on results. Then inspect only the relevant raw XML. For a concrete precedent, use `sc2-reference-query.py object <Family:Id> --component <name>` or a bounded `find`. Reuse that evidence during the task. Snapshot examples cannot establish active dependencies or effective values.
3. **Project-unique IDs:** Make variants with project-unique IDs; only override same-name vanilla IDs when the user explicitly asks for a global change. Sync check gameplay, production entry, presentation, and localization chain.
4. **Edit component source:** Do not hand-edit `publish/`, auto-generated `MapScript.galaxy`, or compiled library output. Respect the current project's hand-authored script entry points.
5. **Static then runtime:** Run static checks against the actual target and confirm the scan scope; then schedule Editor open/save and in-game scenario verification. Do not present static pass as Editor acceptance or game pass without evidence.
6. **Record decisions:** Write durable design facts to `wiki/design/` and summarize in `DesignDocument.md`; write implementation conventions to topic pages. Only log a decision to `wiki/log.md` when its rationale would otherwise be lost.
