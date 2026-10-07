# SC2 Trigger XML Reference

> Generated from `Core.SC2Mod/base.sc2data/triggerlibs/nativelib.triggerlib` (3,196 native functions, library `Ntve`) plus empirically validated workflow notes for generating Trigger XML externally.

Use this page first when generating or editing `.SC2Map` / `.SC2Mod` Trigger XML. For quick function IDs and parameter IDs, use [triggers-cheatsheet.md](triggers-cheatsheet.md). For the full native lookup table, use [triggers-native-functions.md](triggers-native-functions.md).
For external Trigger Editor orientation, see [external-sc2-resources.md](external-sc2-resources.md).

## Quick orientation

SC2 triggers are stored as XML in `<Map>/Triggers` (maps) or
`<Mod>/Triggers` wrapped in `<Library Id="XXXXXXXX">` (mods), plus a
plain-text `<Map>/enUS.SC2Data/LocalizedData/TriggerStrings.txt` with
display names. Every element has an 8-char hex Id (e.g. `A1B2C3D4`).
References use `Type+Library+Id`; map-local refs omit `Library`,
cross-library refs include it (e.g. `Library="Ntve"` for stock natives).

Recommended workflow: generate working Trigger XML externally and let the
SC2 Editor open it as if hand-built. **Avoid `customscriptaction` for
non-trivial logic** — raw Galaxy inside a `<ScriptCode>` block is hard
to read in the editor and bypasses the type checker. Build trees of
native FunctionCalls instead.

For AI personality attack-wave migration, pure GUI is mandatory: use
`skills/sc2-attack-wave-scaling/scripts/convert_custom_ai_to_gui.py` and
deliver only `FunctionCall`/`Param` trees. The compatibility script-stage
helper must never be applied directly to the user's map. Validate parameter
ownership across libraries before Editor handoff: LotV difficulty parameter
definitions use `Library="Lotv"`; the default profile's
`AttackWaveModifier` input `4D4D221F` uses `Library="67AA1763"`.
Migrated personality triggers are eventless workers. Wire them into the
map's existing AI orchestration trigger (commonly `Start AI`) with ordinary,
non-waiting GUI `Run Trigger` actions. Do not attach separate map-initialization
events to each migrated personality. Do not create empty `FlagNative` wrappers
for AI natives that the Trigger Editor does not expose; the Editor may retain
the visual definition while silently omitting its calls from generated Galaxy.

Reference files (paths relative to an extracted Core mod / SC2 install):
- Native catalog XML: `core.sc2mod/base.sc2data/triggerlibs/nativelib.triggerlib` — the source for the 3,196 functions documented below.
- Galaxy native signatures: `core.sc2mod/base.sc2data/triggerlibs/natives.galaxy` — type signatures in Galaxy syntax (useful when generating `<ScriptCode>`).
- Stock SC2 mods for example dialogs, textures, and layouts: `{core,liberty,swarm,void}.sc2mod/` — extract these from the SC2 install with an MPQ tool (e.g. MPQEditor, CASCExplorer).
- For dependency resolution, the SC2 Editor may need a copy of a mod under the SC2 install's `Mods/` folder. Keep this workspace's component folder as the source of truth and document any external copy/sync step for the project.
- Stock unit-portrait textures: `Assets\Textures\btn-{unit|building|ability|upgrade}-{terran|zerg|protoss}-{name}.dds` (e.g. `btn-unit-terran-marine.dds`). Available in every SC2 map.

## GUI Editor Orientation

SC2Mapster's Trigger overview is useful for human Editor work; this page stays focused on XML shape. Key concepts to remember when moving between GUI and XML:

- Trigger files are converted to Galaxy when the map/mod runs. After external XML edits, inspect generated `MapScript.galaxy` if behavior is odd.
- Library triggers from dependencies are visible through the Trigger Editor libraries panel and can run when their events/conditions match. If an imported/library trigger must be suppressed, use trigger on/off logic rather than assuming a right-click disable works across libraries.
- Local variables are per trigger execution/thread. Global variables are shared across triggers and threads.
- Custom Definitions can hide repetitive GUI action trees behind named actions/functions. Mark mod-internal helper definitions `Internal` when maps should not call them directly.
- Presets are enum-like integers with display text. They are good for static options, but generated XML still needs the underlying preset/library IDs.

---

## Element structure rules

- A `<FunctionDef>` body = a sequence of `<FunctionCall>` children
  (statements in order). NOT `<ScriptCode>` directly on the FunctionDef —
  that form is only valid for *sub-function templates* with
  `<FlagSubFunctions/>` like `ForEachMission`.
- `<FlagCall/>` = the function returns a value (needs `<ReturnType>`).
  `<FlagAction/>` = action, returns void. `<FlagEvent/>` = event registration.
- Local variables: declare inside FunctionDef as a `<Variable Type="Variable" Id="..."/>`
  reference, plus a separate top-level `<Element Type="Variable">` with
  type and initial value.
- Parameter passing in a `<Param>` element — one of:
  - Inline literal: `<Value>X</Value> + <ValueType Type="int"/>`
    (or `string`, `fixed`, `bool`)
  - Game-link (catalog ref): `<Value>Marine</Value> +
    <ValueType Type="gamelink"/> + <ValueGameType Type="Unit"/>`
  - Sub-call: `<FunctionCall Type="FunctionCall" Id="..."/>`
  - Variable: `<Variable Type="Variable" Id="..."/>` (add `Library=` for
    cross-lib)
  - Preset enum: `<Preset Type="PresetValue" Library="Ntve" Id="..."/>`
  - Parent-function parameter: `<Parameter Type="ParamDef" Id="..."/>`

### The SubFunctionType pattern (the tricky one)

Some natives accept *sub-actions* (then-branch, loop body, condition).
The child FunctionCall declares its role via
`<SubFunctionType Library="Ntve" Id="..."/>`. Sub-actions live in the
parent's children list, NOT in `<Parameter>` slots.

Validated examples:

- `IfThenElse` (Ntve `00000137`) — sub-types:
  `00000003` = if (condition), `00000004` = then, `00000005` = else.
- `PickEachUnitInGroup` (Ntve `C4DC760C`) — body sub-type `9441B8B5`;
  inside the body, use `UnitGroupLoopCurrent` (Ntve `19CE733E`) for the
  picked unit.
- **`Or` (Ntve `00000133`) vs `And` (Ntve `00000132`)** use DIFFERENT
  cond sub-type IDs: `And` cond = `00000002`; `Or` cond = `00000001`.
  Mixing them silently strips Comparisons on save. Always read the
  parent's `<SubFunctionType>` declarations in nativelib first.

---

## Event declarations (most common silent-failure)

Events are NOT declared as `<Element Type="Event">` siblings. They are
declared as `<Element Type="FunctionCall" Id="X">` (same shape as actions)
and the Trigger references them via `<Event Type="FunctionCall" Id="X"/>`.
The editor SILENTLY STRIPS any `<Event Type="Event"/>` refs and any
`<Element Type="Event">` declarations on save — that type doesn't exist in
the schema.

**Layout requirement:** the event `<Element Type="FunctionCall">` MUST be
placed immediately after its Trigger's closing `</Element>` (sibling-
adjacent), not later in the file. If the referenced FunctionCall is far
away (e.g. end-of-file), the editor's `_Init` codegen silently DROPS the
`TriggerAddEvent*(...)` registration call — the trigger appears to register
but never fires. Verify by reading `MapScript.galaxy`.

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

---

## Trigger Parameter Schema & Galaxy Type Mapping

In StarCraft II's trigger compiler, GUI trigger parameter types map directly to underlying Galaxy primitive types. When generating or inspecting Trigger XML and Galaxy bindings:

| Trigger Parameter Type (`Type="..."`) | Galaxy Primitive | Example Engine Usage |
|---|---|---|
| `gamelink`, `anygamelink` | `string` | Unit types (`"Marine"`), abilities, weapons, upgrades |
| `catalogentry`, `catalogfieldpath`, `reference` | `string` | Dynamic catalog reflection (`CatalogFieldValueSet`) |
| `filepath`, `modelanim`, `actormsg` | `string` | Asset paths, animation names, actor messages |
| `charge`, `cooldown` | `string` | Shared ability charge/cooldown link IDs |
| `convcharacter`, `convline`, `conversationtag` | `string` | Campaign story and transmission engine strings |
| `layoutframe`, `layoutframerel` | `string` | UI layout frame path strings |
| `userfield`, `userinstance` | `string` | User data tables and custom instances |
| `preset` | `int` | Preset enumeration values (e.g. `c_unitPropLife`) |
| `int`, `fixed`, `bool` | `int`, `fixed`, `bool` | Standard numerical and boolean literals |
| `point`, `region`, `unit`, `playergroup`, `unitgroup` | Engine Object handles | Spatial and gameplay entities |

### Element Flags

Trigger XML elements support bitfield flags controlling compiler and editor visibility:
- `Native` (`0x02`): Engine native function binding.
- `FuncAction` (`0x04`): Action definition (void return).
- `FuncCall` (`0x08`): Value-returning function call.
- `Event` (`0x10`): Event registration function.
- `Template` (`0x20`): Sub-function action template.
- `CustomScript` (`0x100`): Raw custom Galaxy script block.
- `SubFunctions` (`0x800`): Container for nested sub-actions.
- `Hidden` / `Internal` / `Restricted`: Editor visibility and scope restrictions.
