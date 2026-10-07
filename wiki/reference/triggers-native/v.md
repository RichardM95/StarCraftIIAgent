# SC2 Native Functions: V

Columns are documented in [../triggers-native-functions.md](../triggers-native-functions.md). Reference in XML as `<FunctionDef Type="FunctionDef" Library="Ntve" Id="<ID>"/>`.

Parameter defaults in `nativelib` do not auto-apply; emit an explicit `<Parameter Type="Param" Id="..."/>` for every slot in generated `<FunctionCall>` XML.

### V

<a id="v"></a>

| Name | ID | Kind | Returns | Params |
|---|---|---|---|---|
| `ValidatorExecute` | `98E048E5` | call | `preset` | validatorLink:gamelink<Validator>, sourceUnit:unit, targetUnit:unit |
| `ValueFromDataTableDialogItem` | `2CB55863` | call | `control` | scope:preset, name:string |
| `ValueFromDataTableDifficultyLevel` | `4626E6E9` | call | `difficulty` | scope:preset, name:string |
| `ValueFromDataTableInstanceDialogItem` | `CC3F9AB1` | call | `control` | instance:datatable, name:string |
| `ValueFromDataTableInstanceDifficultyLevel` | `48C2A0C5` | call | `difficulty` | instance:datatable, name:string |
| `ValueFromDataTableInstancePlayerColor` | `418D6539` | call | `playercolor` | instance:datatable, name:string |
| `ValueFromDataTableInstanceTextTag` | `72412092` | call | `preset` | instance:datatable, name:string |
| `ValueFromDataTablePlayerColor` | `C4714C0B` | call | `playercolor` | scope:preset, name:string |
| `ValueFromDataTableTextTag` | `B61E7630` | call | `preset` | scope:preset, name:string |
| `VictoryPanelAddAchievement` | `D0FE305D` | action | `—` | achievement:gamelink<Achievement> |
| `VictoryPanelAddCustomStatisticLine` | `A717C45B` | action | `—` | statItem:text, value:text |
| `VictoryPanelAddTrackedStatistic` | `1CC3A1D3` | action | `—` | scoreLink:gamelink<ScoreValue> |
| `VictoryPanelClearCustomStatisticTable` | `6C200B16` | action | `—` | — |
| `VictoryPanelSetAchievementsTitle` | `220D9B2C` | action | `—` | text:text |
| `VictoryPanelSetBackgroundFilePath` | `2867C119` | action | `—` | filePath:filepath |
| `VictoryPanelSetCustomStatisticText` | `93004CF2` | action | `—` | text:text |
| `VictoryPanelSetCustomStatisticValue` | `124B6DE8` | action | `—` | text:text |
| `VictoryPanelSetMissionText` | `E40313DC` | action | `—` | text:text |
| `VictoryPanelSetMissionTimeText` | `73EA7278` | action | `—` | text:text |
| `VictoryPanelSetMissionTimeTitle` | `45115EBD` | action | `—` | text:text |
| `VictoryPanelSetMissionTitle` | `01881AC1` | action | `—` | text:text |
| `VictoryPanelSetPlanetModelLink` | `07DE37C6` | action | `—` | model:gamelink<Model> |
| `VictoryPanelSetRewardCredits` | `8AAB5EB3` | action | `—` | credits:int |
| `VictoryPanelSetRewardText` | `CCAA1CE6` | action | `—` | text:text |
| `VictoryPanelSetRewardTitle` | `964C41C7` | action | `—` | text:text |
| `VictoryPanelSetStatisticsTitle` | `50B9A382` | action | `—` | text:text |
| `VictoryPanelSetSummaryBackgroundFilePath` | `69812AF8` | action | `—` | filePath:filepath |
| `VictoryPanelSetVictoryText` | `431D8309` | action | `—` | text:text |
| `VisEnable` | `00000162` | action | `—` | type:preset, enable:preset |
| `VisExploreArea` | `D463A836` | action | `—` | player:int, area:region, state:preset, cliffLevel:preset |
| `VisFillArea` | `9A321718` | action | `—` | player:int, area:region, state:preset, cliffLevel:preset |
| `VisGetFoWAlpha` | `4DE06797` | call | `fixed` | player:int |
| `VisIsEnabled` | `00000163` | call | `bool` | type:preset |
| `VisIsVisibleForPlayer` | `8B533CBD` | call | `bool` | player:int, point:point |
| `VisResetFoWAlpha` | `1E7539AD` | action | `—` | player:int |
| `VisRevealArea` | `685AF92D` | action | `—` | player:int, area:region, duration:fixed, cliffLevel:preset |
| `VisRevealerCreate` | `00000166` | action | `—` | player:int, area:region |
| `VisRevealerDestroy` | `00000168` | action | `—` | r:revealer |
| `VisRevealerEnable` | `00000169` | action | `—` | r:revealer, enable:preset |
| `VisRevealerLastCreated` | `00000167` | call | `revealer` | — |
| `VisRevealerUpdate` | `00000170` | action | `—` | r:revealer |
| `VisSetFoWAlpha` | `B975E43B` | action | `—` | player:int, alpha:fixed |
