# SC2 Native Functions: Other

Columns are documented in [../triggers-native-functions.md](../triggers-native-functions.md). Reference in XML as `<FunctionDef Type="FunctionDef" Library="Ntve" Id="<ID>"/>`.

Parameter defaults in `nativelib` do not auto-apply; emit an explicit `<Parameter Type="Param" Id="..."/>` for every slot in generated `<FunctionCall>` XML.

### _other

<a id="other"></a>

| Name | ID | Kind | Returns | Params |
|---|---|---|---|---|
| `(unnamed_1069D06E)` | `1069D06E` | call | `int` | dateTime:datetime |
| `(unnamed_146F334E)` | `146F334E` | call | `preset` | datetime:datetime |
| `(unnamed_22688BC7)` | `22688BC7` | call | `actormsg` | msgName:string, param1:string |
| `(unnamed_28C77D31)` | `28C77D31` | action | `—` | u:unit, targetPoint:point, queue:preset |
| `(unnamed_2D009905)` | `2D009905` | action | `—` | player:int, onOff:preset |
| `(unnamed_2F8A67F1)` | `2F8A67F1` | action | `—` | player:int, fog:bool |
| `(unnamed_32EB26E3)` | `32EB26E3` | call | `int` | dateTime:datetime |
| `(unnamed_3B7FC013)` | `3B7FC013` | action | `—` | players:playergroup, onOff:preset |
| `(unnamed_4359F428)` | `4359F428` | action | `—` | players:playergroup, mask:bool |
| `(unnamed_4499EFA9)` | `4499EFA9` | call | `int` | dateTime:datetime |
| `(unnamed_45CE88A7)` | `45CE88A7` | action | `—` | — |
| `(unnamed_4F54AC74)` | `4F54AC74` | call | `actormsg` | msgName:string, param1:string, param2:string, param3:string, param4:string |
| `(unnamed_500D0579)` | `500D0579` | call | `int` | dateTime:datetime |
| `(unnamed_59F1433D)` | `59F1433D` | call | `bool` | datetime:datetime |
| `(unnamed_5A8C1442)` | `5A8C1442` | action | `—` | unit:unit, height:fixed, rate:fixed |
| `(unnamed_6185D17C)` | `6185D17C` | call | `int` | — |
| `(unnamed_64B9796C)` | `64B9796C` | call | `bool` | player:int |
| `(unnamed_6814AAE0)` | `6814AAE0` | call | `bool` | player:int |
| `(unnamed_71C65781)` | `71C65781` | action | `—` | players:playergroup, onOff:preset |
| `(unnamed_7B417FFD)` | `7B417FFD` | action | `—` | sourcePlayer:int, targetPlayer:int |
| `(unnamed_7CAF43B4)` | `7CAF43B4` | call | `actormsg` | msgName:string, param1:string, param2:string, param3:string |
| `(unnamed_7E379969)` | `7E379969` | action | `—` | player:int, mask:bool |
| `(unnamed_7F2F662B)` | `7F2F662B` | call | `int` | dateTime:datetime |
| `(unnamed_80A5084A)` | `80A5084A` | call | `bool` | datetime:datetime |
| `(unnamed_818063A2)` | `818063A2` | action | `—` | — |
| `(unnamed_83B90C8A)` | `83B90C8A` | call | `int` | dateTime:datetime |
| `(unnamed_8835BE18)` | `8835BE18` | action | `—` | players:playergroup |
| `(unnamed_89AE2997)` | `89AE2997` | call | `bool` | datetime:datetime |
| `(unnamed_8EEDA0D8)` | `8EEDA0D8` | action | `—` | sourcePlayer:int, targetPlayer:int |
| `(unnamed_91D28CB2)` | `91D28CB2` | action | `—` | players:playergroup |
| `(unnamed_9C5820F2)` | `9C5820F2` | action | `—` | — |
| `(unnamed_A29DCB5C)` | `A29DCB5C` | call | `int` | — |
| `(unnamed_A39DD51A)` | `A39DD51A` | call | `bool` | datetime:datetime |
| `(unnamed_B731B542)` | `B731B542` | action | `—` | — |
| `(unnamed_C3E7DC19)` | `C3E7DC19` | call | `text` | u:unit |
| `(unnamed_C407C01A)` | `C407C01A` | action | `—` | players:playergroup, fog:bool |
| `(unnamed_C4F70B3B)` | `C4F70B3B` | action | `—` | players:playergroup |
| `(unnamed_D9C1C903)` | `D9C1C903` | action | `—` | — |
| `(unnamed_DC02AB11)` | `DC02AB11` | action | `—` | players:playergroup |
| `(unnamed_E01096C8)` | `E01096C8` | call | `preset` | datetime:datetime |
| `(unnamed_E213E139)` | `E213E139` | call | `bool` | dateTime:datetime, beginning:datetime, end:datetime |
| `(unnamed_E79AE4CF)` | `E79AE4CF` | call | `actormsg` | msgName:string, param1:string, param2:string |
| `(unnamed_EDCDFAE1)` | `EDCDFAE1` | action | `—` | player:int, onOff:preset |
| `(unnamed_F7FF960E)` | `F7FF960E` | call | `preset` | — |
| `_BB_HPBarChange` | `9D77AF06` | action | `—` | barID:int |
| `_BB_HPBarCurrentWidth` | `ABC3E694` | call | `int` | barID:int |
| `_BB_HPBarFormatLabel` | `8D88CAF8` | call | `text` | barID:int |
| `_BB_HPBarHeight` | `2B68490D` | call | `int` | barID:int |
| `_BB_HPBarWidth` | `AED32C52` | call | `int` | barID:int |
| `_BB_HPBorderHeight` | `9C8BE313` | call | `int` | barID:int |
| `_BB_HPBorderWidth` | `16F8560B` | call | `int` | barID:int |
| `_BB_PortraitBorderHeight` | `610817D6` | call | `int` | barID:int |
| `_BB_PortraitBorderWidth` | `DB1CF08B` | call | `int` | barID:int |
| `_BB_PortraitHeight` | `A4A5DAA8` | call | `int` | barID:int |
| `_BB_PortraitWidth` | `98ACB4BB` | call | `int` | barID:int |
| `_BB_TitleBarHeight` | `77DE85D2` | call | `int` | barID:int |
| `_BB_TitleBarWidth` | `7B112D4D` | call | `int` | barID:int |
| `_CineModeRestoreCheatStatus` | `E63F1C1A` | action | `—` | — |
| `_CineModeStoreCheatStatus` | `DFB54E13` | action | `—` | — |
| `_StoreGameUIVisibleStates` | `06E98602` | action | `—` | storeRestore:preset, players:playergroup, index:preset |

---

_Generated from `Core.SC2Mod/base.sc2data/triggerlibs/nativelib.triggerlib`: 3196 functions, 6554 ParamDefs, 447 Presets, 2994 PresetValues._
