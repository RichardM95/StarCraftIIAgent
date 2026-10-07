# SC2 Native Functions: Q

Columns are documented in [../triggers-native-functions.md](../triggers-native-functions.md). Reference in XML as `<FunctionDef Type="FunctionDef" Library="Ntve" Id="<ID>"/>`.

Parameter defaults in `nativelib` do not auto-apply; emit an explicit `<Parameter Type="Param" Id="..."/>` for every slot in generated `<FunctionCall>` XML.

### Q

<a id="q"></a>

| Name | ID | Kind | Returns | Params |
|---|---|---|---|---|
| `QueryPersistent` | `06FA2BA0` | call | `actormsg` | enterResponseActor:gamelink<Actor>, leaveResponeActor:gamelink<Actor> |
| `QueryRadius` | `B26FF700` | call | `actormsg` | radius:fixed, responseActor:gamelink<Actor> |
| `QueryRegion` | `8782BEB2` | call | `actormsg` | regionActor:gamelink<Actor>, responseActor:gamelink<Actor> |
| `QueuedBehaviorTypeInTrainingQueueSlot` | `51E35D58` | call | `gamelink<Behavior>` | unit:unit, slot:int, item:int |
| `QueuedUnitTypeInTrainingQueueSlot` | `36426157` | call | `gamelink<Unit>` | unit:unit, slot:int, item:int |
| `QueuedUpgradeTypeInTrainingQueueSlot` | `B97B1F15` | call | `gamelink<Upgrade>` | unit:unit, slot:int, item:int |
