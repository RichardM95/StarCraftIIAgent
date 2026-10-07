# SC2 Native Functions: I

Columns are documented in [../triggers-native-functions.md](../triggers-native-functions.md). Reference in XML as `<FunctionDef Type="FunctionDef" Library="Ntve" Id="<ID>"/>`.

Parameter defaults in `nativelib` do not auto-apply; emit an explicit `<Parameter Type="Param" Id="..."/>` for every slot in generated `<FunctionCall>` XML.

### I

<a id="i"></a>

| Name | ID | Kind | Returns | Params |
|---|---|---|---|---|
| `IfThen` | `BB1891ED` | action | `—` | — +2sub |
| `IfThenElse` | `00000137` | action | `—` | — +3sub |
| `IfThenMultiple` | `C0083258` | action | `—` | — +1sub |
| `ImageToString` | `00FEA644` | call | `string` | val:filepath |
| `IncrementInteger` | `A0F31305` | action | `—` | var:anyvariable, operator:preset, val:int |
| `IncrementReal` | `DB01ECDC` | action | `—` | var:anyvariable, operator:preset, val:fixed |
| `InitialDateTimeGet` | `CF3C0572` | call | `datetime` | — |
| `InShrub` | `2489EDDB` | call | `bool` | point:point |
| `IntersectionOfPlayerGroups` | `0DE37AD9` | call | `playergroup` | groupA:playergroup, groupB:playergroup |
| `IntLoopCurrent` | `D02F7ACF` | call | `int` | — |
| `IntLoopCurrentDeprecated` | `A66EFCA4` | call | `int` | — |
| `IntToDateTime` | `406A7727` | call | `datetime` | uNIXEpoch:int |
| `IntToFixed` | `00000001` | call | `fixed` | val:int |
| `IntToFixed` | `3EA2DE0F` | call | `int` | val:preset |
| `IntToString` | `00000002` | call | `string` | val:int |
| `IntToText` | `EAC465A1` | call | `text` | val:int |
| `ItemGetChargeCount` | `D9E5A4D3` | call | `fixed` | inItem:unit, remainingMax:preset |
| `ItemSetChargeCount` | `E8D281F2` | action | `—` | inItem:unit, inVal:fixed |
