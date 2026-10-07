# SC2 Native Functions: H

Columns are documented in [../triggers-native-functions.md](../triggers-native-functions.md). Reference in XML as `<FunctionDef Type="FunctionDef" Library="Ntve" Id="<ID>"/>`.

Parameter defaults in `nativelib` do not auto-apply; emit an explicit `<Parameter Type="Param" Id="..."/>` for every slot in generated `<FunctionCall>` XML.

### H

<a id="h"></a>

| Name | ID | Kind | Returns | Params |
|---|---|---|---|---|
| `HasCustomCellAttribute` | `2AD78D79` | call | `bool` | point:point, attribute:int |
| `HeightOfRegion` | `DEBF6EB9` | call | `fixed` | region:region |
| `HelpPanelAddHint` | `E5FF78D8` | action | `—` | players:playergroup, tipTitle:text, tipDescription:text, icon:filepath |
| `HelpPanelAddMessage` | `FE9383E0` | action | `—` | players:playergroup, speakerText:text, subtitleText:text, modelLink:gamelink<Model>, soundLink:soundlink |
| `HelpPanelAddTip` | `D2D484F9` | action | `—` | players:playergroup, title:text, description:text, alertText:text, icon:filepath |
| `HelpPanelAddTutorial` | `9870E390` | action | `—` | players:playergroup, title:text, description:text, icon:filepath, movie:filepath, flashing:bool |
| `HelpPanelDestroyAllTips` | `942E099B` | action | `—` | — |
| `HelpPanelDestroyAllTutorials` | `0EEB744E` | action | `—` | — |
| `HelpPanelDestroyHelpItem` | `93E50871` | action | `—` | helpItem:preset |
| `HelpPanelDisplayPage` | `04120251` | action | `—` | players:playergroup, page:preset |
| `HelpPanelEnableTechGlossaryButton` | `FA71311B` | action | `—` | players:playergroup, showHide:preset |
| `HelpPanelEnableTechTreeButton` | `DF393ABA` | action | `—` | players:playergroup, showHide:preset |
| `HelpPanelLastCreatedHelpItem` | `F524C907` | call | `preset` | — |
| `HelpPanelSetHelpItemDarkenedWhenViewed` | `EFE15B3B` | action | `—` | helpItem:preset, darkened:bool |
| `HelpPanelShowTechTreeRace` | `23FE04F5` | action | `—` | players:playergroup, race:gamelink<Race>, showHide:preset |
| `HideAllCinematicPortraits` | `0BEF17C2` | action | `—` | players:playergroup |
| `HideGameUI` | `643E0E9C` | action | `—` | showHide:preset, players:playergroup |
| `HideScreenButton` | `48E1B45F` | action | `—` | showHide:preset, screenButtonID:int |
| `HideScreenImage` | `162B8A0B` | action | `—` | showHideOption:preset, screenImageID:int |
| `HideScreenImage2` | `EF294846` | action | `—` | showHideOption:preset, screenLabelID:int |
| `HostSiteOpsSet` | `A7079E20` | call | `actormsg` | hostName:string, ops:string, holdPosition:int, holdRotation:int |
