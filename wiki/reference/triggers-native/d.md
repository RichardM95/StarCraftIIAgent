# SC2 Native Functions: D

Columns are documented in [../triggers-native-functions.md](../triggers-native-functions.md). Reference in XML as `<FunctionDef Type="FunctionDef" Library="Ntve" Id="<ID>"/>`.

Parameter defaults in `nativelib` do not auto-apply; emit an explicit `<Parameter Type="Param" Id="..."/>` for every slot in generated `<FunctionCall>` XML.

### D

<a id="d"></a>

| Name | ID | Kind | Returns | Params |
|---|---|---|---|---|
| `DataConversationLinesWithTag` | `F32154E6` | call | `string` | tag:conversationtag |
| `DataTableClear` | `E372DF5E` | action | `—` | scope:preset |
| `DataTableGetAbilCmd` | `1705C120` | call | `abilcmd` | scope:preset, name:string |
| `DataTableGetActor` | `054715B3` | call | `actor` | scope:preset, name:string |
| `DataTableGetActorScope` | `113A6867` | call | `actorscope` | scope:preset, name:string |
| `DataTableGetAIFilter` | `111EBCCB` | call | `aifilter` | scope:preset, name:string |
| `DataTableGetBank` | `076E14D7` | call | `bank` | scope:preset, name:string |
| `DataTableGetBool` | `80FB2D14` | call | `bool` | scope:preset, name:string |
| `DataTableGetByte` | `AF0A2657` | call | `byte` | scope:preset, name:string |
| `DataTableGetCameraInfo` | `C40F9A7F` | call | `camerainfo` | scope:preset, name:string |
| `DataTableGetCinematic` | `C7585651` | call | `cinematic` | scope:preset, name:string |
| `DataTableGetColor` | `480FDD3B` | call | `color` | scope:preset, name:string |
| `DataTableGetControl` | `0F452BF3` | call | `control` | scope:preset, name:string |
| `DataTableGetConversation` | `CD08C2B5` | call | `conversation` | scope:preset, name:string |
| `DataTableGetDialog` | `C1701A01` | call | `dialog` | scope:preset, name:string |
| `DataTableGetDoodad` | `D472352C` | call | `doodad` | scope:preset, name:string |
| `DataTableGetFixed` | `FE600745` | call | `fixed` | scope:preset, name:string |
| `DataTableGetInt` | `16ACDFBC` | call | `int` | scope:preset, name:string |
| `DataTableGetMarker` | `AD0845D4` | call | `marker` | scope:preset, name:string |
| `DataTableGetObjective` | `67FA5117` | call | `objective` | scope:preset, name:string |
| `DataTableGetOrder` | `D8167AFB` | call | `order` | scope:preset, name:string |
| `DataTableGetPing` | `C92B4DA6` | call | `ping` | scope:preset, name:string |
| `DataTableGetPlanet` | `0CD778A0` | call | `planet` | scope:preset, name:string |
| `DataTableGetPlayerGroup` | `4059D12A` | call | `playergroup` | scope:preset, name:string |
| `DataTableGetPoint` | `2D3B3E5C` | call | `point` | scope:preset, name:string |
| `DataTableGetPortrait` | `34012595` | call | `portrait` | scope:preset, name:string |
| `DataTableGetRegion` | `8CAC58DA` | call | `region` | scope:preset, name:string |
| `DataTableGetReply` | `4716D604` | call | `reply` | scope:preset, name:string |
| `DataTableGetRevealer` | `B9F42727` | call | `revealer` | scope:preset, name:string |
| `DataTableGetSound` | `64B8A655` | call | `sound` | scope:preset, name:string |
| `DataTableGetSoundLink` | `D111DD0F` | call | `soundlink` | scope:preset, name:string |
| `DataTableGetString` | `D5B3C452` | call | `string` | scope:preset, name:string |
| `DataTableGetText` | `38298AA5` | call | `text` | scope:preset, name:string |
| `DataTableGetTimer` | `85B069E2` | call | `timer` | scope:preset, name:string |
| `DataTableGetTransmission` | `C373C664` | call | `transmission` | scope:preset, name:string |
| `DataTableGetTransmissionSource` | `F669283F` | call | `transmissionsource` | scope:preset, name:string |
| `DataTableGetTrigger` | `DC194B0E` | call | `trigger` | scope:preset, name:string |
| `DataTableGetUnit` | `22669CAF` | call | `unit` | scope:preset, name:string |
| `DataTableGetUnitFilter` | `AFCC55F4` | call | `unitfilter` | scope:preset, name:string |
| `DataTableGetUnitGroup` | `A94BD42E` | call | `unitgroup` | scope:preset, name:string |
| `DataTableGetUnitRef` | `57C5AA00` | call | `unit` | scope:preset, name:string |
| `DataTableGetWave` | `F11E9493` | call | `wave` | scope:preset, name:string |
| `DataTableGetWaveInfo` | `B92E10F9` | call | `waveinfo` | scope:preset, name:string |
| `DataTableGetWaveTarget` | `45802373` | call | `wavetarget` | scope:preset, name:string |
| `DataTableInstanceClear` | `44D7E523` | action | `—` | instance:datatable |
| `DataTableInstanceCopy` | `47AAD0B8` | action | `—` | targetInstance:datatable, sourceInstance:datatable, inReqPrefix:string |
| `DataTableInstanceCreate` | `815B1F09` | action | `—` | — |
| `DataTableInstanceGetAbilCmd` | `A39C58F9` | call | `abilcmd` | instance:datatable, name:string |
| `DataTableInstanceGetActor` | `D64DA2D9` | call | `actor` | instance:datatable, name:string |
| `DataTableInstanceGetActorScope` | `7BE375A5` | call | `actorscope` | instance:datatable, name:string |
| `DataTableInstanceGetAIFilter` | `8E4E195A` | call | `aifilter` | instance:datatable, name:string |
| `DataTableInstanceGetBank` | `1C385650` | call | `bank` | instance:datatable, name:string |
| `DataTableInstanceGetBool` | `177D51E4` | call | `bool` | instance:datatable, name:string |
| `DataTableInstanceGetByte` | `19454A6F` | call | `byte` | instance:datatable, name:string |
| `DataTableInstanceGetCameraInfo` | `23B04FE6` | call | `camerainfo` | instance:datatable, name:string |
| `DataTableInstanceGetCinematic` | `6F889A58` | call | `cinematic` | instance:datatable, name:string |
| `DataTableInstanceGetColor` | `F1126912` | call | `color` | instance:datatable, name:string |
| `DataTableInstanceGetControl` | `3BB330DD` | call | `control` | instance:datatable, name:string |
| `DataTableInstanceGetConversation` | `B35DFB8C` | call | `conversation` | instance:datatable, name:string |
| `DataTableInstanceGetDialog` | `F0E3D0B4` | call | `dialog` | instance:datatable, name:string |
| `DataTableInstanceGetDoodad` | `F31B91A4` | call | `doodad` | instance:datatable, name:string |
| `DataTableInstanceGetFixed` | `8116BC09` | call | `fixed` | instance:datatable, name:string |
| `DataTableInstanceGetInt` | `256B019E` | call | `int` | instance:datatable, name:string |
| `DataTableInstanceGetMarker` | `E9FDAC22` | call | `marker` | instance:datatable, name:string |
| `DataTableInstanceGetObjective` | `F03BD5B4` | call | `objective` | instance:datatable, name:string |
| `DataTableInstanceGetOrder` | `C3F14AC6` | call | `order` | instance:datatable, name:string |
| `DataTableInstanceGetPing` | `4E7EC34D` | call | `ping` | instance:datatable, name:string |
| `DataTableInstanceGetPlanet` | `92B1EC05` | call | `planet` | instance:datatable, name:string |
| `DataTableInstanceGetPlayerGroup` | `7A2DE110` | call | `playergroup` | instance:datatable, name:string |
| `DataTableInstanceGetPoint` | `BFA0E4FA` | call | `point` | instance:datatable, name:string |
| `DataTableInstanceGetPortrait` | `1CF02020` | call | `portrait` | instance:datatable, name:string |
| `DataTableInstanceGetRegion` | `32062490` | call | `region` | instance:datatable, name:string |
| `DataTableInstanceGetReply` | `8F1FF80F` | call | `reply` | instance:datatable, name:string |
| `DataTableInstanceGetRevealer` | `A6D20484` | call | `revealer` | instance:datatable, name:string |
| `DataTableInstanceGetSound` | `74E05D5A` | call | `sound` | instance:datatable, name:string |
| `DataTableInstanceGetSoundLink` | `A7131F13` | call | `soundlink` | instance:datatable, name:string |
| `DataTableInstanceGetString` | `CA3E0459` | call | `string` | instance:datatable, name:string |
| `DataTableInstanceGetText` | `CBB4CE53` | call | `text` | instance:datatable, name:string |
| `DataTableInstanceGetTimer` | `EA1BBA5C` | call | `timer` | instance:datatable, name:string |
| `DataTableInstanceGetTransmission` | `5F5A6541` | call | `transmission` | instance:datatable, name:string |
| `DataTableInstanceGetTransmissionSource` | `56726146` | call | `transmissionsource` | instance:datatable, name:string |
| `DataTableInstanceGetTrigger` | `7289D44A` | call | `trigger` | instance:datatable, name:string |
| `DataTableInstanceGetUnit` | `E2A3FB5C` | call | `unit` | instance:datatable, name:string |
| `DataTableInstanceGetUnitFilter` | `9965647A` | call | `unitfilter` | instance:datatable, name:string |
| `DataTableInstanceGetUnitGroup` | `0D4BA821` | call | `unitgroup` | instance:datatable, name:string |
| `DataTableInstanceGetUnitRef` | `0D2096D1` | call | `unit` | instance:datatable, name:string |
| `DataTableInstanceGetWave` | `C1BC20D7` | call | `wave` | instance:datatable, name:string |
| `DataTableInstanceGetWaveInfo` | `148B522E` | call | `waveinfo` | instance:datatable, name:string |
| `DataTableInstanceGetWaveTarget` | `961B2240` | call | `wavetarget` | instance:datatable, name:string |
| `DataTableInstanceLastCreated` | `A4D517A6` | call | `datatable` | — |
| `DataTableInstanceSetAbilCmd` | `B33C59BC` | action | `—` | instance:datatable, name:string, value:abilcmd |
| `DataTableInstanceSetActor` | `129B2486` | action | `—` | instance:datatable, name:string, value:actor |
| `DataTableInstanceSetActorScope` | `0349310F` | action | `—` | instance:datatable, name:string, value:actorscope |
| `DataTableInstanceSetAIFilter` | `56BCF8B8` | action | `—` | instance:datatable, name:string, value:aifilter |
| `DataTableInstanceSetBank` | `64AAD587` | action | `—` | instance:datatable, name:string, value:bank |
| `DataTableInstanceSetBool` | `D4025EAB` | action | `—` | instance:datatable, name:string, value:bool |
| `DataTableInstanceSetByte` | `28CC4E7A` | action | `—` | instance:datatable, name:string, value:byte |
| `DataTableInstanceSetCameraInfo` | `BB156BD3` | action | `—` | instance:datatable, name:string, value:camerainfo |
| `DataTableInstanceSetCinematic` | `396AD0DC` | action | `—` | instance:datatable, name:string, value:cinematic |
| `DataTableInstanceSetColor` | `E696C52F` | action | `—` | instance:datatable, name:string, value:color |
| `DataTableInstanceSetControl` | `A1F9887A` | action | `—` | instance:datatable, name:string, value:control |
| `DataTableInstanceSetConversation` | `B38A90AA` | action | `—` | instance:datatable, name:string, value:conversation |
| `DataTableInstanceSetDialog` | `9D35C1FB` | action | `—` | instance:datatable, name:string, value:dialog |
| `DataTableInstanceSetDoodad` | `7A2671E2` | action | `—` | instance:datatable, name:string, value:doodad |
| `DataTableInstanceSetFixed` | `353ACE2B` | action | `—` | instance:datatable, name:string, value:fixed |
| `DataTableInstanceSetInt` | `EAF28BDC` | action | `—` | instance:datatable, name:string, value:int |
| `DataTableInstanceSetMarker` | `D4DFAE2E` | action | `—` | instance:datatable, name:string, value:marker |
| `DataTableInstanceSetObjective` | `ABB05E48` | action | `—` | instance:datatable, name:string, value:objective |
| `DataTableInstanceSetOrder` | `EC55EE53` | action | `—` | instance:datatable, name:string, value:order |
| `DataTableInstanceSetPing` | `842B82CB` | action | `—` | instance:datatable, name:string, value:ping |
| `DataTableInstanceSetPlanet` | `3B5F2A2A` | action | `—` | instance:datatable, name:string, value:planet |
| `DataTableInstanceSetPlayerGroup` | `50D705B5` | action | `—` | instance:datatable, name:string, value:playergroup |
| `DataTableInstanceSetPoint` | `864C1F71` | action | `—` | instance:datatable, name:string, value:point |
| `DataTableInstanceSetPortrait` | `81D865F1` | action | `—` | instance:datatable, name:string, value:portrait |
| `DataTableInstanceSetRegion` | `93669118` | action | `—` | instance:datatable, name:string, value:region |
| `DataTableInstanceSetReply` | `F23650FB` | action | `—` | instance:datatable, name:string, value:reply |
| `DataTableInstanceSetRevealer` | `3ADB0FD2` | action | `—` | instance:datatable, name:string, value:revealer |
| `DataTableInstanceSetSound` | `24907DFE` | action | `—` | instance:datatable, name:string, value:sound |
| `DataTableInstanceSetSoundLink` | `A860B705` | action | `—` | instance:datatable, name:string, value:soundlink |
| `DataTableInstanceSetString` | `B5870A1F` | action | `—` | instance:datatable, name:string, value:string |
| `DataTableInstanceSetText` | `C8569EC7` | action | `—` | instance:datatable, name:string, value:text |
| `DataTableInstanceSetTimer` | `373A733E` | action | `—` | instance:datatable, name:string, value:timer |
| `DataTableInstanceSetTransmission` | `A6599410` | action | `—` | instance:datatable, name:string, value:transmission |
| `DataTableInstanceSetTransmissionSource` | `3194A541` | action | `—` | instance:datatable, name:string, value:transmissionsource |
| `DataTableInstanceSetTrigger` | `9D2A66A1` | action | `—` | instance:datatable, name:string, value:trigger |
| `DataTableInstanceSetUnit` | `8BB3A9B1` | action | `—` | instance:datatable, name:string, value:unit |
| `DataTableInstanceSetUnitFilter` | `04098589` | action | `—` | instance:datatable, name:string, value:unitfilter |
| `DataTableInstanceSetUnitGroup` | `1C90F954` | action | `—` | instance:datatable, name:string, value:unitgroup |
| `DataTableInstanceSetUnitRef` | `D05E76CD` | action | `—` | instance:datatable, name:string, value:unit |
| `DataTableInstanceSetWave` | `00F644A5` | action | `—` | instance:datatable, name:string, value:wave |
| `DataTableInstanceSetWaveInfo` | `F259D772` | action | `—` | instance:datatable, name:string, value:waveinfo |
| `DataTableInstanceSetWaveTarget` | `B6D4C05F` | action | `—` | instance:datatable, name:string, value:wavetarget |
| `DataTableInstanceValueCount` | `2F8BDCC4` | call | `int` | instance:datatable |
| `DataTableInstanceValueExists` | `397C9EE5` | call | `bool` | instance:datatable, name:string |
| `DataTableInstanceValueName` | `3A597FE4` | call | `string` | instance:datatable, index:int |
| `DataTableInstanceValueType` | `09582BE9` | call | `preset` | instance:datatable, name:string |
| `DataTableSetAbilCmd` | `EB63284E` | action | `—` | scope:preset, name:string, value:abilcmd |
| `DataTableSetActor` | `31638492` | action | `—` | scope:preset, name:string, value:actor |
| `DataTableSetActorScope` | `A6DA11A3` | action | `—` | scope:preset, name:string, value:actorscope |
| `DataTableSetAIFilter` | `36633A08` | action | `—` | scope:preset, name:string, value:aifilter |
| `DataTableSetBank` | `4254ED57` | action | `—` | scope:preset, name:string, value:bank |
| `DataTableSetBool` | `B57B9FA4` | action | `—` | scope:preset, name:string, value:bool |
| `DataTableSetByte` | `7CB14337` | action | `—` | scope:preset, name:string, value:byte |
| `DataTableSetCameraInfo` | `7D23B5EB` | action | `—` | scope:preset, name:string, value:camerainfo |
| `DataTableSetCinematic` | `1B379644` | action | `—` | scope:preset, name:string, value:cinematic |
| `DataTableSetColor` | `829CAFCA` | action | `—` | scope:preset, name:string, value:color |
| `DataTableSetControl` | `CBC4C799` | action | `—` | scope:preset, name:string, value:control |
| `DataTableSetConversation` | `0638B1AC` | action | `—` | scope:preset, name:string, value:conversation |
| `DataTableSetDialog` | `E9275334` | action | `—` | scope:preset, name:string, value:dialog |
| `DataTableSetDoodad` | `A129DD3F` | action | `—` | scope:preset, name:string, value:doodad |
| `DataTableSetFixed` | `C54A5DFC` | action | `—` | scope:preset, name:string, value:fixed |
| `DataTableSetInt` | `F1C17BBA` | action | `—` | scope:preset, name:string, value:int |
| `DataTableSetMarker` | `100F730E` | action | `—` | scope:preset, name:string, value:marker |
| `DataTableSetObjective` | `73EFF926` | action | `—` | scope:preset, name:string, value:objective |
| `DataTableSetOrder` | `450241ED` | action | `—` | scope:preset, name:string, value:order |
| `DataTableSetPing` | `5CFEE28D` | action | `—` | scope:preset, name:string, value:ping |
| `DataTableSetPlanet` | `82EDE1E7` | action | `—` | scope:preset, name:string, value:planet |
| `DataTableSetPlayerGroup` | `09ECDA3D` | action | `—` | scope:preset, name:string, value:playergroup |
| `DataTableSetPoint` | `60F83155` | action | `—` | scope:preset, name:string, value:point |
| `DataTableSetPortrait` | `095204A4` | action | `—` | scope:preset, name:string, value:portrait |
| `DataTableSetRegion` | `968E0468` | action | `—` | scope:preset, name:string, value:region |
| `DataTableSetReply` | `BBA1B2FA` | action | `—` | scope:preset, name:string, value:reply |
| `DataTableSetRevealer` | `A12F9B32` | action | `—` | scope:preset, name:string, value:revealer |
| `DataTableSetSound` | `13594A7E` | action | `—` | scope:preset, name:string, value:sound |
| `DataTableSetSoundLink` | `10C35C63` | action | `—` | scope:preset, name:string, value:soundlink |
| `DataTableSetString` | `67CE2CB7` | action | `—` | scope:preset, name:string, value:string |
| `DataTableSetText` | `F47B2511` | action | `—` | scope:preset, name:string, value:text |
| `DataTableSetTimer` | `EA9A54D6` | action | `—` | scope:preset, name:string, value:timer |
| `DataTableSetTransmission` | `840738C1` | action | `—` | scope:preset, name:string, value:transmission |
| `DataTableSetTransmissionSource` | `E211322A` | action | `—` | scope:preset, name:string, value:transmissionsource |
| `DataTableSetTrigger` | `96B5B57B` | action | `—` | scope:preset, name:string, value:trigger |
| `DataTableSetUnit` | `1B4F4A6A` | action | `—` | scope:preset, name:string, value:unit |
| `DataTableSetUnitFilter` | `3AADA6D4` | action | `—` | scope:preset, name:string, value:unitfilter |
| `DataTableSetUnitGroup` | `CD680534` | action | `—` | scope:preset, name:string, value:unitgroup |
| `DataTableSetUnitRef` | `BC4DF423` | action | `—` | scope:preset, name:string, value:unit |
| `DataTableSetWave` | `1FB739CA` | action | `—` | scope:preset, name:string, value:wave |
| `DataTableSetWaveInfo` | `506D2B4B` | action | `—` | scope:preset, name:string, value:waveinfo |
| `DataTableSetWaveTarget` | `9B57622F` | action | `—` | scope:preset, name:string, value:wavetarget |
| `DataTableValueCount` | `1701531E` | call | `int` | scope:preset |
| `DataTableValueExists` | `5C8D51C9` | call | `bool` | scope:preset, name:string |
| `DataTableValueName` | `749A9FF9` | call | `string` | scope:preset, index:int |
| `DataTableValueRemove` | `655042C4` | action | `—` | scope:preset, name:string |
| `DataTableValueType` | `DB46735B` | call | `preset` | scope:preset, name:string |
| `DateTimeIsAfter` | `E5DEE105` | call | `bool` | dateTimeA:datetime, dateTimeB:datetime |
| `DateTimeIsBefore` | `F814386A` | call | `bool` | dateTimeA:datetime, dateTimeB:datetime |
| `DateTimeToInt` | `0A91CF53` | call | `int` | dateTime:datetime |
| `DateTimeToString` | `3D69F2B8` | call | `string` | dateTime:datetime |
| `DeathCustomize` | `70AEFF69` | call | `actormsg` | subname:string |
| `DeclareNextTown` | `CBDF8A17` | action | `—` | player:int, center:point |
| `Destroy` | `543901A7` | call | `actormsg` | — |
| `DialogClearSubtitlePositionOverride` | `04330DDC` | action | `—` | — |
| `DialogClearSubtitlePositionOverrideControl` | `3685232E` | action | `—` | — |
| `DialogControlAddDataPoint` | `2C3EAB5B` | action | `—` | graph:control, players:playergroup, xValue:fixed, yValue:fixed, index:int |
| `DialogControlAddItem` | `35C389F3` | action | `—` | list:control, players:playergroup, text:text |
| `DialogControlAdvanceAnimation` | `82EDF7A9` | action | `—` | dialogItem:control, players:playergroup, animationName:string, delta:fixed |
| `DialogControlClearSelectedItem` | `D04BCBEA` | action | `—` | list:control, players:playergroup |
| `DialogControlCreate` | `1005DE91` | action | `—` | dialog:dialog, type:preset |
| `DialogControlCreateFromTemplate` | `5C08CD1C` | action | `—` | dialog:dialog, type:preset, template:layoutframe |
| `DialogControlCreateInPanel` | `570478C9` | action | `—` | dialogItemPanel:control, type:preset |
| `DialogControlCreateInPanelFromTemplate` | `7319128A` | action | `—` | dialogItemPanel:control, type:preset, template:layoutframe |
| `DialogControlDestroy` | `6BA3F195` | action | `—` | dialogItem:control |
| `DialogControlDestroyAll` | `B75B1326` | action | `—` | dialog:dialog |
| `DialogControlFadeTransparency` | `C609209E` | action | `—` | dialogItem:control, players:playergroup, time:fixed, targetTransparency:fixed |
| `DialogControlForceTransition` | `342F1C36` | action | `—` | dialogItem:control, players:playergroup, visible:bool, instant:bool |
| `DialogControlGetAnchor` | `D26648E6` | call | `preset` | dialogItem:control, player:int |
| `DialogControlGetDialog` | `F7C6C3E7` | call | `dialog` | dialogItem:control |
| `DialogControlGetHeight` | `D4857D65` | call | `int` | dialogItem:control, player:int |
| `DialogControlGetItemCount` | `EE46E4CC` | call | `int` | list:control, player:int |
| `DialogControlGetMaxXValue` | `2CEAB967` | call | `fixed` | graph:control, players:playergroup |
| `DialogControlGetMaxYValue` | `F895BE1D` | call | `fixed` | graph:control, players:playergroup |
| `DialogControlGetMinXValue` | `52CF87A8` | call | `fixed` | graph:control, players:playergroup |
| `DialogControlGetMinYValue` | `71AF213C` | call | `fixed` | graph:control, players:playergroup |
| `DialogControlGetOffsetX` | `AA595FFF` | call | `int` | dialogItem:control, player:int |
| `DialogControlGetOffsetY` | `60BBC8A4` | call | `int` | dialogItem:control, player:int |
| `DialogControlGetPropertyAsBool` | `7779E0F6` | call | `bool` | dialogItem:control, property:preset, player:int |
| `DialogControlGetPropertyAsColor` | `17830DA3` | call | `color` | dialogItem:control, property:preset, player:int |
| `DialogControlGetPropertyAsControl` | `0117EADD` | call | `control` | dialogItem:control, property:preset, player:int |
| `DialogControlGetPropertyAsFixed` | `91EDB049` | call | `fixed` | dialogItem:control, property:preset, player:int |
| `DialogControlGetPropertyAsInt` | `BF167817` | call | `int` | dialogItem:control, property:preset, player:int |
| `DialogControlGetPropertyAsString` | `3323B46B` | call | `string` | dialogItem:control, property:preset, player:int |
| `DialogControlGetPropertyAsText` | `354DA625` | call | `text` | dialogItem:control, property:preset, player:int |
| `DialogControlGetPropertyAsUnit` | `693DB7D0` | call | `unit` | dialogItem:control, property:preset, player:int |
| `DialogControlGetPropertyAsUnitGroup` | `A96FAAD6` | call | `unitgroup` | dialogItem:control, property:preset, player:int |
| `DialogControlGetRelativeAnchor` | `4EF445A6` | call | `preset` | dialogItem:control, player:int |
| `DialogControlGetRelativeControl` | `7AC85B23` | call | `control` | dialogItem:control, player:int |
| `DialogControlGetSelectedItem` | `032C70E7` | call | `int` | list:control, player:int |
| `DialogControlGetType` | `6999196C` | call | `preset` | dialogItem:control |
| `DialogControlGetWidth` | `D8957FF3` | call | `int` | dialogItem:control, player:int |
| `DialogControlHookup` | `397B15D6` | action | `—` | dialogItem:control, type:preset, name:layoutframerel |
| `DialogControlHookupStandard` | `CC29332F` | action | `—` | type:preset, name:string |
| `DialogControlHookupUnitStatus` | `CABF8271` | action | `—` | type:preset, name:string, unit:unit |
| `DialogControlInvokeAsString` | `0A7AD7B4` | action | `—` | flash:control, players:playergroup, method:string, parameter1:string, parameter2:string, parameter3:string, parameter4:string |
| `DialogControlInvokeAsText` | `4D9F304A` | action | `—` | flash:control, players:playergroup, method:string, parameter1:text, parameter2:text, parameter3:text, parameter4:text |
| `DialogControlIsEnabled` | `FA3926E1` | call | `bool` | dialogItem:control, player:int |
| `DialogControlIsFullDialog` | `759172B1` | call | `bool` | dialogItem:control, player:int |
| `DialogControlIsVisible` | `2CDA7454` | call | `bool` | dialogItem:control, player:int |
| `DialogControlLastCreated` | `4AB42F83` | call | `control` | — |
| `DialogControlRemoveAllDataPoints` | `CC31BA1F` | action | `—` | graph:control, players:playergroup |
| `DialogControlRemoveAllItems` | `E4F31187` | action | `—` | list:control, players:playergroup |
| `DialogControlRemoveItem` | `4555558B` | action | `—` | list:control, players:playergroup, index:int |
| `DialogControlRequestFocus` | `C849642E` | action | `—` | dialogItem:control, players:playergroup |
| `DialogControlSelectItem` | `34BACF98` | action | `—` | list:control, players:playergroup, index:int |
| `DialogControlSendAnimationEvent` | `4F8CE2E5` | action | `—` | dialogItem:control, players:playergroup, eventName:string |
| `DialogControlSetAnimationSpeed` | `D94F6F9C` | action | `—` | dialogItem:control, players:playergroup, animationName:string, speed:fixed |
| `DialogControlSetAnimationState` | `5708FBB9` | action | `—` | dialogItem:control, players:playergroup, animationStateName:string, eventName:string |
| `DialogControlSetAnimationTime` | `EE08EB84` | action | `—` | dialogItem:control, players:playergroup, animationName:string, time:fixed |
| `DialogControlSetDataColor` | `F76330E2` | action | `—` | graph:control, players:playergroup, color:color, index:int |
| `DialogControlSetDataName` | `541CBAFE` | action | `—` | graph:control, players:playergroup, text:text, index:int |
| `DialogControlSetEnabled` | `CF9D5789` | action | `—` | dialogItem:control, players:playergroup, enableOption:preset |
| `DialogControlSetFullDialog` | `96B15E03` | action | `—` | dialogItem:control, players:playergroup, sizetoParent:bool |
| `DialogControlSetMaxXVisible` | `2F4AB828` | action | `—` | graph:control, players:playergroup, maxXValue:fixed |
| `DialogControlSetMaxYVisible` | `2880A9B8` | action | `—` | graph:control, players:playergroup, maxYValue:fixed |
| `DialogControlSetMinXVisible` | `7065657E` | action | `—` | graph:control, players:playergroup, minXValue:fixed |
| `DialogControlSetMinYVisible` | `FE927D97` | action | `—` | graph:control, players:playergroup, minYValue:fixed |
| `DialogControlSetObservedType` | `EED3AF00` | action | `—` | dialogItem:control, observedType:preset |
| `DialogControlSetPosition` | `A2C9BF0F` | action | `—` | control:control, players:playergroup, anchor:preset, offsetX:int, offsetY:int |
| `DialogControlSetPositionRelative` | `A36F87CD` | action | `—` | item:control, players:playergroup, anchor:preset, relativeItem:control, relativeAnchor:preset, offsetX:int, offsetY:int |
| `DialogControlSetPropertyAsBool` | `BC8EE8F6` | action | `—` | dialogItem:control, property:preset, players:playergroup, value:bool |
| `DialogControlSetPropertyAsColor` | `BB078836` | action | `—` | dialogItem:control, property:preset, players:playergroup, value:color |
| `DialogControlSetPropertyAsControl` | `3AD41DC2` | action | `—` | dialogItem:control, property:preset, players:playergroup, value:control |
| `DialogControlSetPropertyAsFixed` | `0F43A72A` | action | `—` | dialogItem:control, property:preset, players:playergroup, value:fixed |
| `DialogControlSetPropertyAsInt` | `5DEFD2A0` | action | `—` | dialogItem:control, property:preset, players:playergroup, value:int |
| `DialogControlSetPropertyAsString` | `532D2F6A` | action | `—` | dialogItem:control, property:preset, players:playergroup, value:string |
| `DialogControlSetPropertyAsText` | `6D32EA83` | action | `—` | dialogItem:control, property:preset, players:playergroup, value:text |
| `DialogControlSetPropertyAsUnit` | `D9B07209` | action | `—` | dialogItem:control, property:preset, players:playergroup, value:unit |
| `DialogControlSetPropertyAsUnitGroup` | `2AB72DD7` | action | `—` | dialogItem:control, property:preset, players:playergroup, value:unitgroup |
| `DialogControlSetSize` | `B71342F4` | action | `—` | dialogItem:control, players:playergroup, width:int, height:int |
| `DialogControlSetVisible` | `E37ACA0E` | action | `—` | dialogItem:control, players:playergroup, visible:preset |
| `DialogCreate` | `BD9AF7D6` | action | `—` | width:int, height:int, anchor:preset, offsetX:int, offsetY:int, modal:preset |
| `DialogDestroy` | `F4B5BEE7` | action | `—` | dialog:dialog |
| `DialogDestroyAll` | `A87DDC9C` | action | `—` | — |
| `DialogGetAnchor` | `38DAE229` | call | `preset` | dialog:dialog |
| `DialogGetChannel` | `C931461D` | call | `int` | dialog:dialog |
| `DialogGetHeight` | `63CFA859` | call | `int` | dialog:dialog |
| `DialogGetImage` | `978F1411` | call | `string` | dialog:dialog |
| `DialogGetOffsetX` | `A5CFFBC4` | call | `int` | dialog:dialog |
| `DialogGetOffsetY` | `396B475C` | call | `int` | dialog:dialog |
| `DialogGetRelativeAnchor` | `06DB63F1` | call | `preset` | dialog:dialog |
| `DialogGetRelativeDialog` | `5B78FBAF` | call | `dialog` | dialog:dialog |
| `DialogGetRenderPriority` | `3743D63E` | call | `int` | dialog:dialog |
| `DialogGetTitle` | `8DD03F0F` | call | `text` | dialog:dialog |
| `DialogGetTransparency` | `3911A1BC` | call | `fixed` | dialog:dialog |
| `DialogGetWidth` | `EEF62377` | call | `int` | dialog:dialog |
| `DialogIsEnabled` | `BB5C711A` | call | `bool` | dialog:dialog |
| `DialogIsFullscreen` | `BD0825D6` | call | `bool` | dialog:dialog |
| `DialogIsImageVisible` | `D952C4FA` | call | `bool` | dialog:dialog |
| `DialogIsModal` | `BEC7A9EF` | call | `bool` | dialog:dialog |
| `DialogIsOffscreen` | `0F8565A7` | call | `bool` | dialog:dialog |
| `DialogIsVisible` | `A8105988` | call | `bool` | dialog:dialog, player:int |
| `DialogItemColor` | `D9E07DD4` | call | `color` | dialogItem:control, player:int |
| `DialogItemEditValue` | `C9AD8352` | call | `string` | dialogItem:control, player:int |
| `DialogItemImage` | `61F6BBB3` | call | `string` | dialogItem:control, player:int |
| `DialogItemImageType` | `B08314FE` | call | `preset` | dialogItem:control, player:int |
| `DialogItemIsChecked` | `5DDB3E82` | call | `bool` | dialogItem:control, player:int |
| `DialogItemMaximumValue` | `01234601` | call | `fixed` | dialogItem:control, player:int |
| `DialogItemMinimumValue` | `15EB84BE` | call | `fixed` | dialogItem:control, player:int |
| `DialogItemStyle` | `59DBCD9D` | call | `fontstyle` | dialogItem:control, player:int |
| `DialogItemText` | `C3BBBF67` | call | `text` | dialogItem:control, player:int |
| `DialogItemTooltip` | `58D4683D` | call | `text` | dialogItem:control, player:int |
| `DialogItemValue` | `A9266B9E` | call | `fixed` | dialogItem:control, player:int |
| `DialogLastCreated` | `20E3B9BE` | call | `dialog` | — |
| `DialogSetChannel` | `405A17BA` | action | `—` | dialog:dialog, channel:int |
| `DialogSetEnabled` | `BFF3DF9C` | action | `—` | dialog:dialog, enabled:bool |
| `DialogSetFullscreen` | `7E8F82B1` | action | `—` | dialog:dialog, fullscreen:bool |
| `DialogSetImage` | `D1667A7B` | action | `—` | dialog:dialog, image:filepath |
| `DialogSetImageVisible` | `9C391799` | action | `—` | dialog:dialog, visible:preset |
| `DialogSetObservedType` | `85F9DF2E` | action | `—` | dialog:dialog, observedType:preset |
| `DialogSetOffscreen` | `C97E1546` | action | `—` | dialog:dialog, offscreen:bool |
| `DialogSetPosition` | `00E1B2D9` | action | `—` | dialog:dialog, anchor:preset, offsetX:int, offsetY:int |
| `DialogSetPositionRelative` | `7A5DF994` | action | `—` | dialog:dialog, anchor:preset, relativeDialog:dialog, relativeAnchor:preset, offsetX:int, offsetY:int |
| `DialogSetPositionRelativeToUnit` | `CF27B0C8` | action | `—` | dialog:dialog, unit:unit, attachment:preset, offsetX:int, offsetY:int |
| `DialogSetPositionRelativeToUnitWithAnchor` | `1692203C` | action | `—` | dialog:dialog, unit:unit, attachment:preset, anchor:preset, offsetX:int, offsetY:int |
| `DialogSetRenderPriority` | `37AF2CF0` | action | `—` | dialog:dialog, renderPriority:int |
| `DialogSetSize` | `26888592` | action | `—` | dialog:dialog, width:int, height:int |
| `DialogSetSubtitlePositionOverride` | `D379E6CD` | action | `—` | dialog:dialog |
| `DialogSetSubtitlePositionOverrideControl` | `23FCE320` | action | `—` | dialogItem:control |
| `DialogSetTitle` | `E6B89FE1` | action | `—` | dialog:dialog, title:text |
| `DialogSetTransparency` | `7B3EB706` | action | `—` | dialog:dialog, transparency:fixed |
| `DialogSetVisible` | `72C1FB76` | action | `—` | dialog:dialog, players:playergroup, visible:preset |
| `DifficultyAPM` | `52FE5912` | call | `int` | difficulty:difficulty |
| `DifficultyEnabled` | `2B28BF2F` | call | `bool` | difficulty:difficulty |
| `DifficultyHigh` | `68CB92EB` | call | `bool` | difficulty:difficulty |
| `DifficultyIsone` | `BD0E4598` | call | `bool` | difficulty:difficulty |
| `DifficultyIstwo` | `3A3B8C53` | call | `bool` | difficulty1:difficulty, difficulty2:difficulty |
| `DifficultyLow` | `DD754C85` | call | `bool` | difficulty:difficulty |
| `DifficultyName` | `643F49E4` | call | `text` | difficulty:difficulty |
| `DifficultyNameCampaign` | `44564204` | call | `text` | difficulty:difficulty |
| `DifficultyValueFixed` | `83DDFCCA` | call | `fixed` | easy:fixed, normal:fixed, advanced:fixed, expert:fixed |
| `DifficultyValueInt` | `7703744B` | call | `int` | easy:int, normal:int, advanced:int, expert:int |
| `DifficultyValueUnitType` | `BC487BC6` | call | `gamelink<Unit>` | easy:gamelink<Unit>, normal:gamelink<Unit>, advanced:gamelink<Unit>, expert:gamelink<Unit> |
| `DisplayBossBar` | `9925F414` | action | `—` | bossBarID:int, portrait:filepath, title:text, max:int, players:playergroup |
| `DisplayScreenButton` | `83263181` | action | `—` | screenButtonID:int, text:text, width:int, height:int, anchor:preset, offsetX:int, offsetY:int, callback:trigger |
| `DisplayScreenImage` | `BACFFC3C` | action | `—` | screenImageID:int, image:filepath, blendMode:preset, width:int, height:int, anchor:preset, offsetX:int, offsetY:int |
| `DisplayScreenLabel` | `C199FB04` | action | `—` | screenLabelID:int, label:text, style:fontstyle, width:int, height:int, anchor:preset, offsetX:int, offsetY:int |
| `DistanceBetweenPoints` | `00000027` | call | `fixed` | p1:point, p2:point |
| `DistanceSquaredBetweenPoints` | `F4291BF5` | call | `fixed` | p1:point, p2:point |
