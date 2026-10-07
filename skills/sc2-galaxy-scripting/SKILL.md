---
name: sc2-galaxy-scripting
description: StarCraft II Galaxy scripting rules and gotchas for the AeonOfIhanrii campaign. Use when writing, editing, or debugging .galaxy files, trigger custom scripts, bank logic, or UI/dialog code. Covers syntax constraints, source-of-truth, modular script boundaries, and deployment.
---

# SC2 Galaxy Scripting

## When to Use

Load this skill when the task involves Galaxy script (`.galaxy` files): writing trigger actions, bank persistence, dialog/UI code, unit events, or any custom script block. Also load when debugging "function not found", parse errors, or linker drops.
Do not select standalone Galaxy for a new trigger merely because SC2 compiles GUI triggers to Galaxy. Follow `sc2-map-triggers` for GUI-first authoring; use this skill for an explicitly requested Galaxy implementation, existing script maintenance, or a necessary embedded Custom Script block.

This skill is the **Galaxy router**. It owns project-wide syntax constraints, source-of-truth rules, modular script boundaries, and deployment. For deep Galaxy API work (specific native calls, subsystem APIs, struct/enum references), route to the appropriate `galaxy-*` sub-skill under `skills/galaxy/` after loading this skill.

## Galaxy Sub-Skill Router

For deep Galaxy script API work, load the matching `galaxy-*` sub-skill under `skills/galaxy/`. This skill retains the project-wide **syntax constraints** and **source-of-truth** rules that all sub-skills obey.

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

- **Edit only:** `<SC2_MODS_PATH>/AeonOfIhanrii.SC2Mod/Base.SC2Data/Epi_Main.galaxy` (primary custom script block) or modular scripts under `*.SC2Mod/Base.SC2Data/Scripts/`.
- **Do NOT edit:** `Lib*.galaxy` (compiled library wrappers, auto-generated and overwritten on Editor save) or `MapScript.galaxy` inside maps (auto-generated).
- **Deploy:** In `workspace_copy` mode, preview then use `python tools/deploy-mod.py` to copy component sources to SC2. In `in_place` mode no deployment is needed. The SC2 Editor, not this tool, regenerates compiled wrappers on save.

## Critical Syntax Rules (confirmed compile errors)

```galaxy
// Array declaration — CORRECT:
string[90] arr;
// NOT: string arr[90];

// Dialog/dialogitem variables are primitive int:
int myDialog;
int myButton;

// Global initializers — integer/fixed literals only:
int gMyCount = 0;
// NOT: int gMyDialog = c_invalidDialog;  // compile error

// Trigger action function signature:
bool MyAction(bool testConds, bool runActions) { ... }

// Get triggering unit:
lv_u = EventUnit();
// NOT: UnitFromEvent()  // does not exist

// Call Galaxy function from GUI trigger (use #PARAM):
libMy_SetCurrentMap(#PARAM(name));

// Local variables — MUST be at the TOP of function body, no inline init:
bool MyFunc(bool testConds, bool runActions) {
    trigger orbTrig;   // declared at top, no initializer
    if (!runActions) { return true; }
    orbTrig = TriggerCreate("Foo");  // assigned in body
    // NOT: trigger orbTrig = TriggerCreate("Foo");  // parse error
    // NOT: declared inside if/else/while  // invalid
}

// Unit created event — 4 params:
TriggerAddEventUnitCreated(myTrig, null, null, "");  // any unit
TriggerAddEventUnitCreated(myTrig, null, "Zergling", "");  // specific type
// NOT: TriggerAddEventUnitBirth(myTrig, null)
// NOT: TriggerAddEventUnitCreated(myTrig, null, null)  // needs 4th ""

// Read current max life:
fixed hp = UnitGetPropertyFixed(u, c_unitPropLifeMax, c_unitPropCurrent);
// NOT: c_unitPropMax  // constant does not exist

// Increments/decrements — compound assignment only:
count += 1;
// NOT: count++ or count--  // unsupported

// Loops — while only:
while (i < 10) { i += 1; }
// NOT: for (i=0; i<10; i++)  // unsupported

// Include directives — relative path, no extension:
include "Scripts/libMy_Globals"
// NOT: include "Scripts/libMy_Globals.galaxy"
// NOT: #include "Scripts/libMy_Globals.h"

// Dynamic catalog reflection paths mirror XML element tree:
CatalogFieldValueSet(c_gameCatalogUnit, "Marine", "Armor", player, "1");
CatalogFieldValueSet(c_gameCatalogUnit, "Marine", "CostResource[Minerals]", player, "75");
```

## Modular Script Boundary Rules

1. **Top-level declarations:** Every included `.galaxy` file MUST begin with declarations at brace depth 0 and end with a closed function brace `}`. Splitting a function body across file boundaries produces compilation errors.
2. **No duplicate functions:** Defining the same function name across multiple included scripts fails with `"function already defined: <name>"`.
3. **Forward references:** Functions must be **defined before they are called** within script blocks. GUI trigger calls are linked independently, but script-to-script calls require the callee to appear first in compilation order.

## GUI Include Injection Pattern

`Lib67AA1763.galaxy` is auto-generated and overwrites manual `include` statements on save. To persistently include `Epi_Main.galaxy`:

1. Open `AeonOfIhanrii.SC2Mod` in SC2 Editor → Triggers (F6).
2. Select the `LegacyoftheIhanrii` library.
3. Create a new Custom Script (Ctrl+Alt+T) named `Epi_Include`.
4. Add single line: `include "Epi_Main"`.
5. Save mod (Ctrl+S) — Editor injects `include "Epi_Include"` into `Lib67AA1763.galaxy` after `include "Lib67AA1763_h"`.

Do NOT paste `Epi_Main.galaxy` content directly into a GUI Custom Script block — it contains non-ASCII comments and the GUI block enforces ASCII-only with 4-space line prefixes.

## Map-to-Mod Calls Must Use GUI Actions

The SC2 linker silently drops the mod library unless the map calls a **GUI action** defined in the mod. Custom Script blocks in maps do not count. Define GUI actions in the mod library and call them from map triggers.

## Community Error Triage

| Error | Cause | Fix |
|---|---|---|
| `Can only pass basic types` | Structs/arrays as function args | Pass scalar IDs/indices or use globals |
| `struct forward declaration not supported` | Struct used before definition | Define structs before functions/vars that use them |
| `Bulk copy not supported` | Array/struct assignment by value | Copy scalar elements explicitly |
| `Could not allocate Global Memory` / `e_globalsTooLarge` | Global arrays too big | Keep project state compact |
| `failed: 32k - 1 size limit to local variables` | Huge local arrays | Allocate small globals or split |
| `Registry overflow` | Too many string/text/point refs in one expression | Break into smaller statements |
| `Internal compiler error` | Line or string > ~2046 chars | Split long lines/strings |

## Naming Conventions

- Galaxy function prefix: `libEpi_`
- Galaxy global prefix: `libEpi_g_`
- Bank name: `"AeonOfIhanriiBank"`

## Reference

- Deep syntax primer: `wiki/reference/galaxy-language.md`
- Bank function signatures: `wiki/reference/galaxy-bank.md`
- Gotchas source: `wiki/implementation/galaxy-gotchas.md`
- Bank system design: `wiki/implementation/bank-system.md`

## Chinese Task Knowledge (Merged)

Distilled from `references/galaxy-and-triggers.md` (Galaxy portion) and `references/source-caveats.md`. Duplicates with the syntax rules above omitted.

### Native Lookup Discipline
- Do not guess native names, parameters, or constants. Query `wiki/reference/triggers-native/` by name; for the final Galaxy signature, cross-check actual `natives.galaxy` or Editor-generated output.
- For unit events, query `EventUnit` and the actual target-event API — avoid "nearest unit" style inferences. Plain unit creation, entering the map, training completion, and warp completion are different event semantics; pick the one matching the requirement and verify de-duplication.

### Conservative Loop / Increment Style
- Prefer `i = i + 1;` and `while (...)` over `i += 1;` in hand-written Custom Script when in doubt. Source docs disagree on whether `+=` and `break` are supported across all Galaxy contexts (`galaxy-gotchas.md` recommends `+=`; `triggers-workflow-gotchas.md` reports failures inside `ScriptCode`). Distinguish script contexts and let the Editor compile.

### Local Variable Initialization
- For compatibility with the source-recorded Custom Script environment, separate declaration from runtime initialization — declare at the top of the function body, assign in executable statements.

### Module Compilation Order
- Do not split a function body across files; do not define the same function twice. Arrange project script order so callees appear before callers within script blocks (GUI trigger calls link independently).

### Source Caveats (from `source-caveats.md`)
- **Galaxy operator conflict:** `galaxy-gotchas.md` recommends `+=`; `triggers-workflow-gotchas.md` reports `+=` failing in `ScriptCode` contexts and `break` having context-dependent behavior. For new hand-written Custom Script, use explicit assignment and `while`; distinguish script context, then let the Editor compile.
