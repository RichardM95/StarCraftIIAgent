# SC2 Native Functions: F

Columns are documented in [../triggers-native-functions.md](../triggers-native-functions.md). Reference in XML as `<FunctionDef Type="FunctionDef" Library="Ntve" Id="<ID>"/>`.

Parameter defaults in `nativelib` do not auto-apply; emit an explicit `<Parameter Type="Param" Id="..."/>` for every slot in generated `<FunctionCall>` XML.

### F

<a id="f"></a>

| Name | ID | Kind | Returns | Params |
|---|---|---|---|---|
| `FixedToInt` | `00000003` | call | `int` | val:fixed |
| `FixedToString` | `00000004` | call | `string` | val:fixed, prec:int |
| `FixedToText` | `0FF0ADD6` | call | `text` | val:fixed, prec:int |
| `FixedToTextAdvanced` | `7D448A6C` | call | `text` | val:fixed, style:preset, groupNumbers:preset, minPrecision:int, maxPrecision:int |
| `FlashScreenButton` | `0531A785` | action | `—` | screenButtonID:int, flashTime:fixed, color1:color, color2:color |
| `Floor` | `6BF56043` | call | `fixed` | x:fixed |
| `FloorI` | `C156C116` | call | `int` | x:fixed |
| `FogSetColor` | `9D5EB505` | action | `—` | color:color |
| `FogSetColorOverTime` | `A6028A5D` | action | `—` | color:color, duration:fixed |
| `FogSetDensity` | `0C83D19F` | action | `—` | density:fixed |
| `FogSetDensityOverTime` | `488858A4` | action | `—` | density:fixed, duration:fixed |
| `FogSetDisableAtUltra` | `A51F12F9` | action | `—` | disable:bool |
| `FogSetEnabled` | `59DA6647` | action | `—` | enable:bool |
| `FogSetFallOff` | `B3D5BF65` | action | `—` | falloff:fixed |
| `FogSetFallOffOverTime` | `B30D9FA1` | action | `—` | falloff:fixed, duration:fixed |
| `FogSetStartHeight` | `10393B26` | action | `—` | startHeight:fixed |
| `FogSetStartHeightOverTime` | `A76B4CEF` | action | `—` | startHeight:fixed, duration:fixed |
| `ForEachAbilityOnUnit` | `E5B89CB1` | action | `—` | abil:anyvariable, unit:unit +1sub |
| `ForEachBehaviorOnUnit` | `958D756B` | action | `—` | var:anyvariable, unit:unit +1sub |
| `ForEachCatalogEntryInCatalog` | `B6E64ADB` | action | `—` | catalog:preset, entry:anyvariable +1sub |
| `ForEachInteger` | `66474248` | action | `—` | var:anyvariable, s:int, e:int, increment:int +1sub |
| `ForEachInteger2` | `119A6AF8` | action | `—` | var:anyvariable, s:fixed, e:fixed, increment:fixed +1sub |
| `ForEachInteger2Deprecated` | `2947E9A0` | action | `—` | var:anyvariable, s:fixed, e:fixed, increment:fixed +1sub |
| `ForEachIntegerDeprecated` | `5693DC73` | action | `—` | var:anyvariable, s:int, e:int, increment:int +1sub |
| `ForEachLearnableAbilityOnUnit` | `9B2E2FB2` | action | `—` | abil:anyvariable, unit:unit +1sub |
| `ForEachPlayerInGroup` | `B525B112` | action | `—` | var:anyvariable, group:playergroup +1sub |
| `ForEachPlayerInGroupDeprecated` | `36876ACF` | action | `—` | var:anyvariable, group:playergroup +1sub |
| `ForEachScopeFieldValueInCatalogFieldScopeArray` | `5FD44C2E` | action | `—` | catalog:preset, entry:catalogentry, field:catalogfieldpath, scope:catalogscope, scopeField:catalogfieldname, player:int, val:anyvariable +1sub |
| `ForEachSetBitInBitMask` | `D16EE5F6` | action | `—` | var:anyvariable, bitMask:bitmask +1sub |
| `ForEachUIFrame` | `0D169C4B` | action | `—` | var:preset +1sub |
| `ForEachUnitInGroup` | `00000327` | action | `—` | var:anyvariable, group:unitgroup +1sub |
| `ForEachUnitInGroupDeprecated` | `BF584949` | action | `—` | var:anyvariable, group:unitgroup +1sub |
| `ForEachUnSetBitInBitMask` | `4DED547D` | action | `—` | var:anyvariable, bitMask:bitmask +1sub |
| `ForEachUserDataInstanceInUserType` | `D1C15067` | action | `—` | instance:anyvariable, userType:gamelink<User> +1sub |
| `ForEachUserDataValueInUserTypeFieldArray` | `2D9F8B59` | action | `—` | userType:gamelink<User>, instance:userinstance, field:userfield, value:anyvariable, var:anyvariable, userDataType:preset +1sub |
| `ForEachValueInCatalogFieldArray` | `224BC9ED` | action | `—` | catalog:preset, entry:catalogentry, fieldPath:catalogfieldpath, player:int, val:anyvariable +1sub |
| `FormatDateTimeasString` | `D0379F0C` | call | `string` | datetime:datetime |
| `FormatDuration` | `A86DD352` | call | `text` | duration:int |
| `FormatNumber` | `1DBD601B` | call | `text` | number:int |
| `FormatTipTitle` | `F38744BA` | call | `text` | title:text, type:preset |
| `FullscreenPortrait` | `9BD2A464` | call | `portrait` | — |
