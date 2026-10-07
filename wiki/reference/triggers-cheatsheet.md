# SC2 Trigger XML Cheat Sheet

Hand-validated native IDs, parameter IDs, and common preset values. For full native function lookup, see [triggers-native-functions.md](triggers-native-functions.md).

## Validated cheat-sheet (small set, with full param IDs)

This is the hand-verified subset. The huge auto-generated table at the
bottom has every native, but only the function ID — for parameter IDs of
anything not on this list, look it up in `nativelib.triggerlib` directly.

### Events

- `TriggerAddEventMapInit` = Ntve `00000120` (no params)
- `TriggerAddEventTimePeriodic` = Ntve `6D565EB4`
  - param `4AB413B8` dur (fixed)
  - param `3E8E573F` timeType (preset `00000006`; values `00000013`=game default, `00000012`=real, `EC544EA4`=ai)
- `TriggerAddEventUnitRegion` = Ntve `00000041` (preferred over
  `TriggerAddEventUnitCreated` for "any unit spawn"; pass Entire Map
  region + default Enter state; remember rule #11: emit ALL params
  explicitly, the documented defaults do NOT auto-apply)

### Control flow

- `IfThenElse` = Ntve `00000137` (SubFuncTypes: `00000003`=if,
  `00000004`=then, `00000005`=else)
- `Return` = Ntve `00000097` (param `00000488` val, return-typed)
- `PickEachUnitInGroup` = Ntve `C4DC760C` (param `F96B466D` group,
  SubFuncType `9441B8B5` body)
- `Comparison` = Ntve `C439C375` (params `ABB380C4` val1 anycompare,
  `51567265` op preset, `4A15EC5F` val2 sameas val1)
  - Op preset `4FAE2F8A`; values `1E7A4625`=eq, `500677B2`=ne,
    `684CA9CE`=lt
- `Or` = Ntve `00000133`; cond sub-type `00000001`
- `And` = Ntve `00000132`; cond sub-type `00000002`
- `customscriptaction` = Ntve `00000123` (FlagCustomScript; body is
  `<ScriptCode>` inside the FunctionCall — escape hatch)

### Variables / arithmetic

- `SetVariable` = Ntve `00000136` (params `00000219` var anyvariable,
  `00000220` val sameas var)
- `ArithmeticInt` = Ntve `00000128` (params `00000205` val1, `00000206`
  op preset `00000027`, `00000207` val2)
- `ArithmeticReal` = Ntve `00000129` (params `00000208` val1, `00000209`
  op, `00000210` val2)
  - Shared op values: `00000085`=+, `00000086`=-, `00000087`=*, `00000088`=/

### Units

- `UnitGroup` (builder) = Ntve `00000359` (params `00000691` type,
  `00000692` player, `00000693` region, `00000695` unitfilter,
  `00000694` count)
  - Defaults: type `00000231` Any Unit, player `2999701E` Any Player,
    region = `RegionEntireMap` call, count `1468BD55`
- `UnitGroupLoopCurrent` = Ntve `19CE733E` (returns unit — the picked
  iterator)
- `UnitGetType` = Ntve `00000079` (param `00000138` u unit; returns
  gamelink Unit)
- `UnitTypeTestAttribute` = Ntve `7A0CB31F` (tests attribute on a
  unit-TYPE not a unit instance; call as
  `UnitTypeTestAttribute(UnitGetType(u), attribute)`)

### Players

- `PlayerIsEnemy` = Ntve `CA3AB9A9` — signature `(source, target,
  relation)` where `relation` is from preset `PlayerRelation`
  (`2D9EC843`) with values `Enemy`/`Ally`/`Neutral`.

### Regions

- `RegionEntireMap` = Ntve `00000356` (no params, returns region)
- `RegionPlayableMap` = Ntve `46F2D5B8`

### UI / text

- `UIDisplayMessage` = Ntve `0366EE04` (params `0D120C33` players
  playergroup, `A4C19F41` messageArea preset, `78A54B52` message text)
  - MessageArea preset `08050A84`; values `89CC0A21`=Chat (use for
    debug!), `875889C8`=Subtitle (campaign-hidden), `818777CD`=Objective,
    `A1F3F135`=Directive, `DDCB86EF`=Error, `F282A60A`=Cinematic,
    `18995805`=Debug
- `PlayerGroupAll` = Ntve `00000192` (no params, returns playergroup)
- `StringToText` = Ntve `55C79F96` (param `30693AA2` val string)
- `IntToText` = Ntve `EAC465A1` (param `D125FE97` val int)
- `CombineText` = Ntve `86E40471` (params `174E8B8C` text1, `BD48D330`
  text2)

### Dialogs (high-level)

- `CreateDialogItemImage` = Ntve `CFF28424` — single call that creates
  an Image control AND sets size/position/texture/tint/blend in one
  shot. 12 params: dialog, w, h, anchor preset, offX, offY, tooltip,
  filepath, imageType preset, tiled bool, tintColor, blendMode preset.
  Strongly preferred over raw `DialogControlCreate(Image) +
  SetPropertyAsImage` chain.
- Image filepath Param XML: `<Value>Assets\Textures\btn-unit-terran-marine.dds</Value><ValueType Type="filepath"/><ValueTypeInfo Value="5"/>` — the `ValueTypeInfo Value="5"` is required for filepath params.
- Stock unit-portrait textures: `Assets\Textures\btn-{unit|building|ability|upgrade}-{terran|zerg|protoss}-{name}.dds` (e.g. `btn-unit-terran-marine.dds`). Available in all SC2 maps.

### Per-card dialog design

For card-style dialogs: create one Dialog **per card** (not one big
dialog with child controls). Typical dimensions ~220×340, anchor screen
Bottom, offset Y positive above the command card area. Skip
`DialogSetImageVisible` — the default SC2 dialog frame IS the card
border. Use `CreateDialogItemImage` for the portrait at Top-center; one
Button at Bottom-center with rich text (colored name + description) for
the click handler. The common mistake is using a single Dialog with N
buttons + N background Image controls as "card frames" — an Image
control with no texture renders as bright white and looks terrible.
Per-card dialogs give proper frames for free.


---

## Common Presets (enum-style param values)

There are 447 presets in nativelib totaling 2,994 named values. The full
list is too long to inline, but every preset is in
`nativelib.triggerlib` under `<Element Type="Preset" Id="…">` — its
`<Item Type="PresetValue" Id="…"/>` children list the values. The
`PresetValue` element with the same `Id` carries the `<Identifier>` name
and the `<Value>` literal.

The presets you reach for most often:

| Preset | ID | Used in | Common values (name = Id) |
|---|---|---|---|
| MessageArea | `08050A84` | `UIDisplayMessage` | Chat=`89CC0A21`, Subtitle=`875889C8`, Objective=`818777CD`, Directive=`A1F3F135`, Error=`DDCB86EF`, Cinematic=`F282A60A`, Debug=`18995805` |
| TimeType | `00000006` | `TriggerAddEventTimePeriodic`, timers | Game=`00000013` (default), Real=`00000012`, AI=`EC544EA4` |
| ComparisonOp | `4FAE2F8A` | `Comparison` | Eq=`1E7A4625`, Ne=`500677B2`, Lt=`684CA9CE`, Gt, Le, Ge (look up by name) |
| ArithmeticOp | `00000027` | `ArithmeticInt`, `ArithmeticReal` | +=`00000085`, -=`00000086`, *=`00000087`, /=`00000088` |
| PlayerRelation | `2D9EC843` | `PlayerIsEnemy` | Enemy, Ally, Neutral (look up by name in nativelib) |

To find a preset's full value list, grep nativelib for the preset's Id
and follow the `<Item Type="PresetValue" Id="…"/>` references.


---
