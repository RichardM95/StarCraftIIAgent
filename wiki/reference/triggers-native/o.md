# SC2 Native Functions: O

Columns are documented in [../triggers-native-functions.md](../triggers-native-functions.md). Reference in XML as `<FunctionDef Type="FunctionDef" Library="Ntve" Id="<ID>"/>`.

Parameter defaults in `nativelib` do not auto-apply; emit an explicit `<Parameter Type="Param" Id="..."/>` for every slot in generated `<FunctionCall>` XML.

### O

<a id="o"></a>

| Name | ID | Kind | Returns | Params |
|---|---|---|---|---|
| `ObjectiveCreate` | `1D6F1270` | action | `—` | name:text, description:text, state:preset, primary:preset |
| `ObjectiveCreateForPlayers` | `0CFF1A69` | action | `—` | name:text, description:text, state:preset, primary:preset, players:playergroup |
| `ObjectiveDestroy` | `00000434` | action | `—` | objective:objective |
| `ObjectiveDestroyAll` | `0A043554` | action | `—` | players:playergroup |
| `ObjectiveGetDescription` | `9A4C5A17` | call | `text` | objective:objective |
| `ObjectiveGetName` | `4A60BD83` | call | `text` | objective:objective |
| `ObjectiveGetPlayerGroup` | `2FA5DA72` | call | `playergroup` | objective:objective |
| `ObjectiveGetPrimary` | `B5337352` | call | `bool` | objective:objective |
| `ObjectiveGetPriority` | `98959816` | call | `int` | objective:objective |
| `ObjectiveGetState` | `E44DBA40` | call | `preset` | objective:objective |
| `ObjectiveLastCreated` | `00000433` | call | `objective` | — |
| `ObjectiveSetAfter` | `89A5FC49` | action | `—` | objective:objective, afterObjective:objective |
| `ObjectiveSetBefore` | `309B1E32` | action | `—` | objective:objective, beforeObjective:objective |
| `ObjectiveSetDescription` | `00000436` | action | `—` | objective:objective, description:text |
| `ObjectiveSetFirst` | `58931983` | action | `—` | objective:objective |
| `ObjectiveSetLast` | `5A412508` | action | `—` | objective:objective |
| `ObjectiveSetName` | `00000435` | action | `—` | objective:objective, text:text |
| `ObjectiveSetPlayerGroup` | `0CB4FA5D` | action | `—` | objective:objective, players:playergroup |
| `ObjectiveSetPrimary` | `E0D9530C` | action | `—` | objective:objective, primary:preset |
| `ObjectiveSetPriority` | `471E57AD` | action | `—` | objective:objective, priority:int |
| `ObjectiveSetState` | `00000440` | action | `—` | objective:objective, state:preset |
| `ObjectiveShow` | `19BA63F9` | action | `—` | objective:objective, players:playergroup, show:preset |
| `ObjectiveVisible` | `AABFD861` | call | `bool` | objective:objective, player:int |
| `OnlineMapToMapLoad` | `79225E96` | action | `—` | mapSlot:int, victoryPlayers:playergroup, defeatPlayers:playergroup |
| `Or` | `00000133` | ? | `—` | — +1sub |
| `Order` | `59BA1DDF` | call | `order` | abilCmd:abilcmd |
| `OrderGetAbilityCommand` | `E4A06F0A` | call | `abilcmd` | o:order |
| `OrderGetFlag` | `00000348` | call | `bool` | order:order, flag:preset |
| `OrderGetPlayer` | `00000334` | call | `int` | o:order |
| `OrderGetTargetItem` | `14D0FF13` | call | `unit` | o:order |
| `OrderGetTargetPoint` | `00000071` | call | `point` | o:order |
| `OrderGetTargetPosition` | `CF8D6291` | call | `point` | o:order |
| `OrderGetTargetType` | `47BB7BFF` | call | `preset` | o:order |
| `OrderGetTargetUnit` | `00000073` | call | `unit` | o:order |
| `OrderSetAutoCast` | `8F55F540` | call | `order` | abilCmd:abilcmd, autocastOn:preset |
| `OrderSetFlag` | `F4325823` | action | `—` | order:order, flag:preset, value:bool |
| `OrderSetTargetItem` | `4BB72410` | action | `—` | inOrder:order, inItem:unit |
| `OrderSetTargetPassenger` | `34EEF4C0` | action | `—` | inOrder:order, inPassenger:unit |
| `OrderSetTargetPoint` | `5E8E4EAA` | action | `—` | inOrder:order, inPoint:point |
| `OrderSetTargetUnit` | `612A012A` | action | `—` | inOrder:order, inUnit:unit |
| `OrderTargetingItem` | `C360B251` | call | `order` | abilCmd:abilcmd, item:unit |
| `OrderTargetingPoint` | `43F16BA5` | call | `order` | abilCmd:abilcmd, p:point |
| `OrderTargetingRelativePoint` | `0537DF83` | call | `order` | abilCmd:abilcmd, p:point |
| `OrderTargetingUnit` | `F6F9120D` | call | `order` | abilCmd:abilcmd, u:unit |
| `OrderTargetingUnitGroup` | `984B8065` | call | `order` | abilCmd:abilcmd, unitGroup:unitgroup |
