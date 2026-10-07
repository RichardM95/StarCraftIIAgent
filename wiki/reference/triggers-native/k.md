# SC2 Native Functions: K

Columns are documented in [../triggers-native-functions.md](../triggers-native-functions.md). Reference in XML as `<FunctionDef Type="FunctionDef" Library="Ntve" Id="<ID>"/>`.

Parameter defaults in `nativelib` do not auto-apply; emit an explicit `<Parameter Type="Param" Id="..."/>` for every slot in generated `<FunctionCall>` XML.

### K

<a id="k"></a>

| Name | ID | Kind | Returns | Params |
|---|---|---|---|---|
| `KickFromGame` | `B06831BB` | action | `—` | playerGroup:playergroup |
| `KillDoodadsInRegion` | `9C8E59A4` | action | `—` | target:region, doodadType:gamelink<Actor> |
| `KillingPlayer` | `CAD5046C` | call | `int` | — |
| `KillingUnit` | `ADB84019` | call | `unit` | — |
| `KillModel` | `04454841` | action | `—` | model:actor |
