# External SC2 Modding Resources

Use this page as a fast router to external references. Keep durable project decisions in this wiki; use external sites for lookup, field meaning, signatures, and broader editor concepts.

## Source Map

| Source | Best use | Notes |
|---|---|---|
| [SC2Mapster Wiki](https://sc2mapster.wiki.gg/) | Broad editor orientation across Terrain, Data, Trigger, UI, Maps/Mods, Scripting, AI, and debugging. | Prefer `wiki.gg` over legacy Fandom when both exist. Search can still land on Fandom mirrors. |
| [Language Overview](https://sc2mapster.fandom.com/wiki/Language_Overview#List_of_SC2_natives) | Galaxy language constraints and mental model. | Good for syntax traps: local declarations at top, array dimensions after type, no `++`, no block comments, no dynamic allocation, strict types. |
| [Talv Galaxy Reference](https://mapster.talv.space/galaxy/reference) | Native/library function signatures, GUI names, return types, presets, and category browsing. | Primary online lookup for Galaxy calls. Also covers UI layout docs and links to data docs. |
| [Talv Data File List](https://mapster.talv.space/data/files.html) | Header-file-level routing for data schemas. | Useful when you know the catalog family: `Unit.h`, `Abil.h`, `Behavior.h`, `Effect.h`, `Requirement.h`, `Actor.h`, `Weapon.h`, etc. |
| [Talv Data Class List](https://mapster.talv.space/data/annotated.html) | Catalog class/member browsing and inheritance shape. | Use for field meaning after local XML grep. Examples: `CUnit`, `CAbilTrain`, `CAbilEffect`, `CBehaviorBuff`, `CEffectDamage`, `CRequirement*`, `CActorUnit`. |
| [sc2-gamedata-documentation](https://github.com/chansey97/sc2-gamedata-documentation/tree/master) | Offline Windows reference for data structures. | Upstream project provides a compiled CHM release. Talv's online data docs credit this project. |
| [SC2Mapster Triggers](https://sc2mapster.wiki.gg/wiki/Triggers) | Trigger Editor concepts, element types, GUI layout, and category navigation. | Good for human Editor work; use local trigger XML pages for external XML generation. |
| [SC2Mapster Errors/Debugging](https://sc2mapster.wiki.gg/wiki/Errors/Debugging) | Galaxy compile/runtime error triage. | Use after checking local [galaxy-gotchas.md](../implementation/galaxy-gotchas.md). |
| [SC2 Editor Tutorials - Data Editor](https://s2editor-guides.readthedocs.io/New_Tutorials/04_Data_Editor/058_Data_Editor_Introduction/) | Catalog-oriented Data Editor concepts. | Units, actors, buttons, dependencies, and data spaces. |
| [SC2Mapster/SC2GameData](https://github.com/SC2Mapster/SC2GameData) | Public extracted GameData/UI/Galaxy reference. | Useful for cross-checking Blizzard patterns. |

## Tooling, Language Servers & Schemas

| Tool / Repository | Purpose | Notes |
|---|---|---|
| [sc2-galaxy-toolkit](https://github.com/sc2-arcade-watcher/sc2-galaxy-toolkit) | VS Code language extension for Galaxy Script. | Syntax highlighting, symbol lookup, and diagnostics. |
| [Talv/plaxtony](https://github.com/Talv/plaxtony) | Static analysis & AST parser for Galaxy, Triggers, and GameData XML. | TypeScript-based SC2 parser; builds symbol tables and validates schemas. |
| [sc2-arcade-watcher/sc2-xsd](https://github.com/sc2-arcade-watcher/sc2-xsd) | Formal XSD schemas for StarCraft II GameData XML. | Real-time XML catalog validation against engine specs. |
| [SC2Mapster/sc2layout-schema](https://github.com/SC2Mapster/sc2layout-schema) | Formal XSD schema for SC2Layout definitions. | Schema validation for custom UI frames and layouts. |
| [Talv/sc2-layouts](https://github.com/Talv/sc2-layouts) | VS Code extension for SC2Layout files. | Syntax highlighting and frame schema validation. |
| [sc2-modkit](https://github.com/sc2-arcade-watcher/sc2-modkit) | VS Code modding suite for SC2. | Project scaffolding, packaging, and editor integration. |
| [Talv/vscode-sc2-galaxy](https://github.com/Talv/vscode-sc2-galaxy) | VS Code Galaxy language support. | Language server integration for Galaxy scripts. |
| [galaxy-parser](https://github.com/rameshvarun/galaxy-parser) | Formal EBNF grammar and parser for Galaxy Script. | Grammar specification reference. |
| [Galaxy Language Fundamentals (LobeHub)](https://lobehub.com/de/skills/kimplaybit-starcraft-2-editor-skills-galaxy-language-fundamentals) | Coding agent guidelines for Galaxy syntax. | Hoisting, compound assignments, primitive type rules. |

## Lookup Workflow

1. Exact XML field, index, ID, or Blizzard pattern: grep `DataEditorXML/` first, then inactive XML if extracting unused-dependency units.
2. Meaning of a known data field: use Talv Data Class List or File List, then record only project-relevant conclusions in this wiki.
3. Galaxy function signature: search existing `.galaxy` files, then use Talv Galaxy Reference; use local `triggers-native/` pages when generating Trigger XML.
4. Trigger GUI concept or category: use SC2Mapster Triggers; use local trigger XML pages for schema rules.
5. Compile/runtime error: check local gotchas, then SC2Mapster Errors/Debugging for broader error names.
6. XML/Layout validation: cross-reference with `sc2-xsd` and `sc2layout-schema`.

## Project Rule

External pages are reference material, not source of truth. When a lookup affects the project, add the small conclusion to the relevant wiki page and append `wiki/log.md` when the rationale is durable.

