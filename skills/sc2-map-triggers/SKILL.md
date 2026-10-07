---
name: sc2-map-triggers
description: StarCraft II map trigger XML and wiring for the AeonOfIhanrii campaign. Use when editing .SC2Map Triggers, wiring campaign map initialization, bank preload, victory/defeat hooks, or generating trigger XML. Covers GUI action requirement, trigger element schema, event declarations, and per-map setup.
---

# SC2 Map Triggers & Wiring

## When to Use

Load this skill when editing map trigger XML (`.SC2Map/Triggers`), wiring campaign map initialization, bank preload, victory/defeat hooks, or generating trigger XML externally.

For new triggers, prefer GUI-editable events, conditions, actions, and GUI custom definitions. If a small part cannot reasonably be expressed in GUI, embed only that part as Custom Script within the trigger and keep the surrounding flow in GUI. Do not move the whole feature to a standalone Galaxy script unless the user explicitly requests Galaxy; maintenance of existing Galaxy source is a separate case.

## Critical Rule: Map-to-Mod Calls Must Use GUI Actions

The SC2 linker **silently drops the mod library** unless the map calls a **GUI Action Definition** exported by the mod. Raw Custom Script blocks in maps do NOT count. Define GUI actions in the mod library and call them from map triggers.

Example: In the map init trigger, call `libMy_InitMission("Map01")` as a GUI action, not via Custom Script.

## Standard Map Wiring Checklist

When wiring a vanilla Blizzard campaign map into the custom campaign:

1. **Dependency registration:** SC2 Editor → Modules → Dependencies → Add `MyCampaignMod.SC2Mod`.
2. **Init trigger:** Locate the map's initialization trigger (usually `Map Initialization` or `gt_MapInitialization`).
3. **GUI action call:** Call the mod's custom initialization GUI action (e.g. `libMy_InitMission("Map01")`).
4. **Bank preload:** Add `BankPreLoad("MyCampaignBank")` during early map initialization.
5. **Victory/defeat hooks:** Ensure mission victory triggers call the campaign progression save action before victory cutscenes.

## Campaign Map Locations

Maps live under `paths.campaign_maps_dir` from `agent-config.json`:
- `voidprologue/` — Prologue maps
- `void/` — Campaign maps (paiur, pshakuras, ppurifier, ptaldarim, pkorhal, pmoebius, pulnar, pstory, sc2epilogue)

## Trigger XML Structure

Triggers are stored as XML in `<Map>/Triggers` (maps) or `<Mod>/Triggers` wrapped in `<Library Id="XXXXXXXX">` (mods), plus `<Map>/enUS.SC2Data/LocalizedData/TriggerStrings.txt` for display names.

Every element has an 8-char hex Id. References use `Type+Library+Id`; map-local refs omit `Library`, cross-library refs include it (e.g. `Library="Ntve"` for stock natives).

### Element Structure Rules

- `<FunctionDef>` body = sequence of `<FunctionCall>` children (statements in order). NOT `<ScriptCode>` directly (that form is only for sub-function templates with `<FlagSubFunctions/>`).
- `<FlagCall/>` = returns a value (needs `<ReturnType>`). `<FlagAction/>` = action, returns void. `<FlagEvent/>` = event registration.
- Local variables: declare inside FunctionDef as `<Variable Type="Variable" Id="..."/>` reference, plus a separate top-level `<Element Type="Variable">` with type and initial value.

### Parameter Passing

A `<Param>` element can contain one of:
- Inline literal: `<Value>X</Value>` + `<ValueType Type="int"/>` (or `string`, `fixed`, `bool`)
- Game-link: `<Value>Marine</Value>` + `<ValueType Type="gamelink"/>` + `<ValueGameType Type="Unit"/>`
- Sub-call: `<FunctionCall Type="FunctionCall" Id="..."/>`
- Variable: `<Variable Type="Variable" Id="..."/>` (add `Library=` for cross-lib)
- Preset enum: `<Preset Type="PresetValue" Library="Ntve" Id="..."/>`
- Parent-function parameter: `<Parameter Type="ParamDef" Id="..."/>`

### SubFunctionType Pattern (tricky)

Some natives accept sub-actions (then-branch, loop body, condition). The child FunctionCall declares its role via `<SubFunctionType Library="Ntve" Id="..."/>`. Sub-actions live in the parent's children list, NOT in `<Parameter>` slots.

Key IDs:
- `IfThenElse` (Ntve `00000137`): if=`00000003`, then=`00000004`, else=`00000005`
- `PickEachUnitInGroup` (Ntve `C4DC760C`): body=`9441B8B5`; use `UnitGroupLoopCurrent` (Ntve `19CE733E`) for the picked unit
- `And` (Ntve `00000132`): cond sub-type `00000002`
- `Or` (Ntve `00000133`): cond sub-type `00000001` — **different from And!** Mixing them silently strips Comparisons on save.

## Event Declarations (most common silent-failure)

Events are NOT `<Element Type="Event">`. They are `<Element Type="FunctionCall" Id="X">` (same shape as actions), and the Trigger references them via `<Event Type="FunctionCall" Id="X"/>`. The editor **silently strips** any `<Event Type="Event"/>` refs.

**Layout requirement:** The event `<Element Type="FunctionCall">` MUST be placed immediately after its Trigger's closing `</Element>` (sibling-adjacent). If far away, the `_Init` codegen silently DROPS the `TriggerAddEvent*(...)` call — the trigger registers but never fires. Verify by reading generated `MapScript.galaxy`.

```xml
<Element Type="Trigger" Id="D23DC42E">
    <Event Type="FunctionCall" Id="859460FA"/>
    <Action Type="FunctionCall" Id="47FB5D16"/>
</Element>
<Element Type="FunctionCall" Id="859460FA">      <!-- event, immediately after -->
    <FunctionDef Type="FunctionDef" Library="Ntve" Id="6D565EB4"/>
    <Parameter Type="Param" Id="DurParam"/>
    <Parameter Type="Param" Id="TimeTypeParam"/>
</Element>
```

Conditions follow the same pattern: `<Condition Type="FunctionCall" Id="X"/>`.

## Trigger Parameter Types → Galaxy Mapping

| Trigger Type | Galaxy Primitive | Example |
|---|---|---|
| `gamelink`, `anygamelink` | `string` | Unit types, abilities, weapons |
| `catalogentry`, `catalogfieldpath`, `reference` | `string` | Dynamic catalog reflection |
| `preset` | `int` | Enum values (`c_unitPropLife`) |
| `int`, `fixed`, `bool` | `int`, `fixed`, `bool` | Standard literals |
| `point`, `region`, `unit`, `unitgroup` | Engine handles | Spatial/gameplay entities |

## Map Trigger File Search Rules

Map `Triggers` files are large vanilla trees. **Do not read them start-to-finish.** Use scoped `rg` with `--max-count` for specific terms (e.g. `BankPreLoad`, `BankSave`, `SetCurrentMap`).

## Element Flags

- `Native` (`0x02`): Engine native binding
- `FuncAction` (`0x04`): Action (void return)
- `FuncCall` (`0x08`): Value-returning function
- `Event` (`0x10`): Event registration
- `CustomScript` (`0x100`): Raw Galaxy block
- `Hidden` / `Internal` / `Restricted`: Editor visibility

## Recommended Workflow

Generate working Trigger XML externally and let the SC2 Editor open it. Build trees of native FunctionCalls first. Embedded `customscriptaction` is a narrow fallback for logic the GUI cannot reasonably express; it bypasses the type checker, so keep it small and verify Editor compilation.

After external XML edits, inspect generated `MapScript.galaxy` if behavior is odd.

## Reference

- `wiki/reference/triggers-overview.md` — full trigger XML reference
- `wiki/reference/triggers-cheatsheet.md` — quick function/param IDs
- `wiki/reference/triggers-native-functions.md` — native function signatures
- `wiki/reference/triggers-native/` — per-letter native lookup
- `wiki/implementation/per-map-setup.md` — map wiring checklist & registry
- `wiki/implementation/bank-system.md` — campaign persistence design
- `wiki/reference/galaxy-bank.md` — bank function signatures

## Chinese Task Knowledge (Merged)

Distilled from `references/galaxy-and-triggers.md` (Triggers portion). Duplicates with sections above omitted.

### External Trigger Editing Discipline
- Close the corresponding document in the Editor and back up before external edits — in-memory copies overwrite external changes. Never edit `MapScript.galaxy` directly; it is regenerated on save.

### Parameter & SubFunctionType Caveats
- Parameters must be supplied explicitly — do not assume native defaults fill in. `ValueType` and the gamelink `ValueGameType` must be accurate.
- Native param IDs, Preset IDs, and `SubFunctionType` IDs must be looked up from the native tables: `Or` and `And` use different condition subtypes. Sub-actions are children of the calling tree, not slots inside a normal `<Parameter>`.
- A `<FunctionCall>` subtree must not reuse one ID across multiple parent references — copy to a new ID and remove orphan references.

### Array & Variable Layout
- `ArraySize` is nested inside `VariableType`. Source docs note that GUI `Value=N` represents indices `0..N`, distinct from direct Galaxy array-length syntax — handle them differently.
- For every declared element (especially variables / `ParamDef`), add matching `TriggerStrings.txt` names. `TriggerStrings.txt` is plain text — do NOT HTML-escape characters. `Triggers` XML follows standard XML escaping rules.

### Editor Save & Regeneration Safety
- Source records: triggers with events but no action, or empty `<Comment>` elements, cause mod-Editor save problems. Always give event triggers a valid action; use non-empty `<Comment>` content and a name.
- After save, reopen the map and force one trigger edit to make the Editor regenerate, then verify `InitTriggers` and `TriggerAddEvent*` calls. Visible in the trigger tree does not prove the event is registered.

### Map ↔ Mod Library Wiring
- The map references the target mod in active dependencies and calls the init function via the mod-exported GUI Action Definition. Pure Custom Script references can cause the linker to drop the mod library; verify the actual compiled output.
