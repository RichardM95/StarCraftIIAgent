# SC2 Native Functions: C

Columns are documented in [../triggers-native-functions.md](../triggers-native-functions.md). Reference in XML as `<FunctionDef Type="FunctionDef" Library="Ntve" Id="<ID>"/>`.

Parameter defaults in `nativelib` do not auto-apply; emit an explicit `<Parameter Type="Param" Id="..."/>` for every slot in generated `<FunctionCall>` XML.

### C

<a id="c"></a>

| Name | ID | Kind | Returns | Params |
|---|---|---|---|---|
| `cai_getCustomData` | `690585B3` | call | `string` | player:int |
| `cai_getLastWave` | `D237C756` | call | `wave` | player:int |
| `cai_runall` | `57B35053` | action | `—` | — |
| `cai_setDefGather` | `A9EA580D` | action | `—` | player:int, point:point |
| `cai_start` | `D8A21F36` | action | `—` | ai:aidef, player:int |
| `cai_startall` | `011F85FA` | action | `—` | — |
| `cai_wave_createdUnits` | `4E74D71A` | call | `unitgroup` | wave:aidefwave, player:int |
| `cai_wave_createdWave` | `11CCA676` | call | `wave` | wave:aidefwave, player:int |
| `cai_wave_enable` | `0000EBDB` | action | `—` | wave:aidefwave, player:int, onOff:preset |
| `cai_wave_isEnabled` | `641CFD0F` | call | `bool` | wave:aidefwave, player:int |
| `cai_wave_run` | `810C9533` | action | `—` | wave:aidefwave, player:int, target:playergroup, wait:preset |
| `cai_waves_enable` | `38742BD8` | action | `—` | player:int, onOff:preset |
| `cai_waves_run` | `8CAB163A` | action | `—` | player:int, target:playergroup |
| `cai_waves_stop` | `898E65C3` | action | `—` | ai:aidef |
| `CameraApplyInfo` | `A1037B3E` | action | `—` | player:int, c:camerainfo, duration:fixed, initialVelocity:fixed, decelerate:fixed, useTarget:preset |
| `CameraClearChannel` | `A2798799` | action | `—` | player:int, channel:int |
| `CameraClearChannelOnPortrait` | `8E9C5755` | action | `—` | player:int, portrait:portrait, channel:int |
| `CameraFollowUnitGroup` | `B34FAB70` | action | `—` | player:int, unitGroup:unitgroup, follow:preset, keepCurrentTarget:preset |
| `CameraFollowUnitGroupGet` | `350F6D67` | call | `unitgroup` | player:int |
| `CameraForceFollowUnitGroup` | `E750A66A` | action | `—` | player:int, doDoNot:preset |
| `CameraForceMouseRelative` | `A5CC6797` | action | `—` | player:int, enable:preset |
| `CameraGetDistance` | `041CCAB6` | call | `fixed` | player:int |
| `CameraGetPitch` | `D3A0F4D6` | call | `fixed` | player:int |
| `CameraGetTarget` | `F6460765` | call | `point` | player:int |
| `CameraGetYaw` | `797E4DA3` | call | `fixed` | player:int |
| `CameraInfoDefault` | `00000200` | call | `camerainfo` | — |
| `CameraInfoGetTarget` | `00000207` | call | `point` | c:camerainfo |
| `CameraInfoGetValue` | `00000202` | call | `fixed` | c:camerainfo, type:preset |
| `CameraInfoSetTarget` | `00000203` | action | `—` | c:camerainfo, p:point |
| `CameraInfoSetValue` | `00000201` | action | `—` | c:camerainfo, type:preset, value:fixed |
| `CameraLockInput` | `00000326` | action | `—` | player:int, lock:preset |
| `CameraLookAt` | `20A06660` | action | `—` | player:int, p:point, duration:fixed, initialVelocity:fixed, decelerate:fixed |
| `CameraLookAtActor` | `6474C738` | action | `—` | player:int, actor:actor |
| `CameraLookAtUnit` | `6892B8B1` | action | `—` | player:int, unit:unit |
| `CameraPan` | `DC635AEF` | action | `—` | player:int, p:point, duration:fixed, initialVelocity:fixed, decelerate:fixed, smart:preset |
| `CameraRestore` | `9A0D729F` | action | `—` | player:int, duration:fixed, initialVelocity:fixed, decelerate:fixed |
| `CameraSave` | `503F3DE6` | action | `—` | player:int |
| `CameraSetBounds` | `F470860B` | action | `—` | players:playergroup, bounds:region, minimap:preset |
| `CameraSetChannel` | `8ED9E26A` | action | `—` | player:int, u:unit, name:modelcamera, channel:int, aspectRatio:fixed |
| `CameraSetChannelOnPortrait` | `0F98C681` | action | `—` | player:int, camera:camerainfo, aspectRatio:fixed, portrait:portrait, channel:int |
| `CameraSetData` | `62292946` | action | `—` | players:playergroup, camera:gamelink<Camera> |
| `CameraSetMouseRotates` | `4A0C1B53` | action | `—` | player:int, enable:preset |
| `CameraSetMouseRotationSpeed` | `B7D9F0B0` | action | `—` | player:int, direction:preset, speed:fixed |
| `CameraSetValue` | `9755B9B4` | action | `—` | player:int, type:preset, value:fixed, duration:fixed, initialVelocity:fixed, decelerate:fixed |
| `CameraSetVerticalFieldOfView` | `6CEA924D` | action | `—` | player:int, enable:preset |
| `CameraShake` | `64827F40` | action | `—` | player:int, amplitude:preset, frequency:preset, blendIn:fixed, blendOut:fixed, duration:fixed |
| `CameraShakeStart` | `F813558C` | action | `—` | player:int, position:preset, direction:preset, strength:fixed, frequency:fixed, random:fixed, duration:fixed |
| `CameraShakeStop` | `D6F1B283` | action | `—` | player:int |
| `CameraUseHeightDisplacement` | `EA3823E9` | action | `—` | player:int, enable:preset |
| `CameraUseHeightSmoothing` | `A964CB90` | action | `—` | player:int, enable:preset |
| `CameraUseModel` | `00000360` | action | `—` | player:int, u:unit, name:modelcamera, duration:fixed |
| `CampaignInitAI` | `43BF892E` | action | `—` | — |
| `CampaignMode` | `A88BEB03` | action | `—` | players:playergroup, onOff:preset |
| `CampaignProgressDeleteCampaignSave` | `EA5470DA` | action | `—` | players:playergroup |
| `CampaignProgressEnableCampaignCompletedSaves` | `70818612` | action | `—` | players:playergroup, enable:preset |
| `CampaignProgressEnableCampaignSaves` | `4F034A95` | action | `—` | players:playergroup, enable:preset |
| `CampaignProgressSetCampaignFinished` | `0555A44E` | action | `—` | players:playergroup, campaign:string, finished:bool |
| `CampaignProgressSetImageFilePath` | `93B192B6` | action | `—` | players:playergroup, campaign:string, image:filepath |
| `CampaignProgressSetText` | `B338B8E3` | action | `—` | players:playergroup, campaign:string, text:text |
| `CampaignProgressSetTutorialFinished` | `A7BE1D6B` | action | `—` | players:playergroup, campaign:string, finished:bool |
| `CatalogEntryClass` | `4753BA4E` | call | `int` | catalog:preset, entry:catalogentry |
| `CatalogEntryCount` | `00000377` | call | `int` | catalog:preset |
| `CatalogEntryGet` | `00000378` | call | `catalogentry` | catalog:preset, index:int |
| `CatalogEntryIsDefault` | `ADA0151C` | call | `bool` | catalog:preset, entry:catalogentry |
| `CatalogEntryIsValid` | `E6AB7041` | call | `bool` | catalog:preset, entry:catalogentry |
| `CatalogEntryParent` | `00000379` | call | `catalogentry` | catalog:preset, entry:catalogentry |
| `CatalogEntryScope` | `00000380` | call | `catalogscope` | catalog:preset, entry:catalogentry |
| `CatalogFieldCount` | `00000381` | call | `int` | scope:catalogscope |
| `CatalogFieldExists` | `83B9DED9` | call | `bool` | scope:catalogscope, field:catalogfieldname |
| `CatalogFieldGet` | `00000382` | call | `catalogfieldname` | scope:catalogscope, index:int |
| `CatalogFieldIsArray` | `AD46099F` | call | `bool` | scope:catalogscope, field:catalogfieldname |
| `CatalogFieldIsScope` | `855AF166` | call | `bool` | scope:catalogscope, field:catalogfieldname |
| `CatalogFieldType` | `28E8B577` | call | `string` | scope:catalogscope, field:catalogfieldname |
| `CatalogFieldTypeCategory` | `1728334B` | call | `preset` | scope:catalogscope, field:catalogfieldname |
| `CatalogFieldValueCount` | `4E004004` | call | `int` | catalog:preset, entry:catalogentry, fieldPath:catalogfieldpath, player:int |
| `CatalogFieldValueGet` | `00000383` | call | `string` | catalog:preset, entry:catalogentry, fieldPath:catalogfieldpath, player:int |
| `CatalogFieldValueGetAsInt` | `70AF8BB2` | call | `int` | catalog:preset, entry:catalogentry, fieldPath:catalogfieldpath, player:int |
| `CatalogFieldValueGetAsReal` | `657B90A6` | call | `fixed` | catalog:preset, entry:catalogentry, fieldPath:catalogfieldpath, player:int |
| `CatalogFieldValueGetFlagsAsInt` | `13FCF4F1` | call | `int` | catalog:preset, entry:catalogentry, fieldPath:catalogfieldpath, player:int |
| `CatalogFieldValueModify` | `56331453` | action | `—` | catalog:preset, entry:catalogentry, fieldPath:catalogfieldpath, player:int, value:string, operation:preset |
| `CatalogFieldValueModifyBasedOnDefaultValue` | `16F885F6` | action | `—` | catalog:preset, entry:catalogentry, fieldPath:catalogfieldpath, player:int, value:fixed, operation:preset |
| `CatalogFieldValueSet` | `03D7A0F2` | action | `—` | catalog:preset, entry:catalogentry, fieldPath:catalogfieldpath, player:int, value:string |
| `CatalogFieldValueSetAsReal` | `22AACFEE` | action | `—` | catalog:preset, entry:catalogentry, fieldPath:catalogfieldpath, player:int, value:fixed |
| `CatalogLinkReplace` | `D0BCDC98` | action | `—` | player:int, catalog:preset, value:string, replacement:string |
| `CatalogLinkReplacement` | `0168D226` | call | `string` | player:int, catalog:preset, value:string |
| `CatalogReferenceCount` | `F4AC46C4` | call | `int` | reference:reference, player:int |
| `CatalogReferenceGet` | `4D4B1A99` | call | `string` | reference:reference, player:int |
| `CatalogReferenceGetAsInt` | `AEF40843` | call | `int` | reference:reference, player:int |
| `CatalogReferenceGetAsReal` | `3242F98D` | call | `fixed` | reference:reference, player:int |
| `CatalogReferenceModify` | `CC1B23D8` | action | `—` | reference:reference, player:int, value:string, operation:preset |
| `CatalogReferenceModifyBasedOnDefaultValue` | `7261B967` | action | `—` | reference:reference, player:int, value:fixed, operation:preset |
| `CatalogReferenceSet` | `02E83924` | action | `—` | reference:reference, player:int, value:string |
| `CatalogReferenceSetAsReal` | `804105E9` | action | `—` | reference:reference, player:int, value:fixed |
| `Ceiling` | `CA42A5D8` | call | `fixed` | x:fixed |
| `CeilingI` | `5C9C427F` | call | `int` | x:fixed |
| `CenterOfUnitGroup` | `C16D54CD` | call | `point` | unitGroup:unitgroup |
| `ChangeUnitDamage` | `FF9944FC` | action | `—` | unit:unit, takeDeal:preset, option:preset |
| `CharacterSheetPanelSetDescriptionText` | `F06B4181` | action | `—` | players:playergroup, visible:text |
| `CharacterSheetPanelSetNameText` | `9860149D` | action | `—` | players:playergroup, visible:text |
| `CharacterSheetPanelSetPortraitModelLink` | `99A06E76` | action | `—` | players:playergroup, visible:gamelink<Model> |
| `CinematicDataRun` | `7A4A515F` | action | `—` | cinematic:cinematic, players:playergroup, waitUntilDone:preset |
| `CinematicDataStop` | `F9878BEF` | action | `—` | — |
| `CinematicFade` | `D8A9F49F` | action | `—` | fadeIn:preset, duration:fixed, style:preset, color:color, transparency:fixed, waitUntilDone:preset |
| `CinematicMode` | `90BF49D3` | action | `—` | players:playergroup, cinematicMode:bool, duration:fixed |
| `CinematicMode` | `E92E544E` | action | `—` | onOff:preset, players:playergroup, duration:fixed |
| `CinematicOverlay` | `AB32F40C` | action | `—` | fadeIn:preset, duration:fixed, imagePath:filepath, transparency:fixed, waitUntilDone:preset |
| `CinematicPortrait` | `B8AD02AA` | call | `portrait` | position:preset |
| `ClearAnimation` | `FFBC1D46` | action | `—` | target:actor, identifier:string |
| `ClearAnimationOnDoodadsInRegion` | `FD9B8C07` | action | `—` | target:region, doodadType:gamelink<Actor>, identifier:string |
| `ClearPortraitAnimation` | `A5822235` | action | `—` | portrait:portrait, identifier:string |
| `CliffLevel` | `5CD16E7E` | call | `int` | point:point |
| `ClosestUnitToPoint` | `BA9C71FE` | call | `unit` | point:point, group:unitgroup |
| `Color` | `00000189` | call | `color` | r:fixed, g:fixed, b:fixed |
| `Color255FromFixed` | `8B1FA25C` | call | `int` | colorComponent:fixed |
| `ColorFromIndex` | `B9C9A103` | call | `color` | index:int, type:preset |
| `ColorGetComponent` | `00000040` | call | `fixed` | c:color, component:preset |
| `ColorWithAlpha` | `00000190` | call | `color` | r:fixed, g:fixed, b:fixed, a:fixed |
| `CombineStrings` | `00000131` | call | `string` | str1:string, str2:string |
| `CombineStringsMult` | `00000130` | call | `string` | str:string |
| `CombineText` | `86E40471` | call | `text` | text1:text, text2:text |
| `CombineTextMultiple` | `5A89F099` | call | `text` | inText:text |
| `Comparison` | `C439C375` | ? | `—` | val1:anycompare, op:preset, val2:sameas |
| `ConsoleCommand` | `00000140` | action | `—` | text:string, defaults:preset, macros:preset |
| `Continue` | `268BBACB` | action | `—` | — |
| `ConversationCreate` | `FB8BE4F2` | action | `—` | visible:preset |
| `ConversationDataActiveCamera` | `0B9E950C` | call | `convstateindex` | — |
| `ConversationDataActiveLine` | `7C65EA1E` | call | `convline` | — |
| `ConversationDataActiveSound` | `B93884B7` | call | `gamelink<Sound>` | — |
| `ConversationDataCanRun` | `995D0B63` | call | `bool` | conversation:gamelink<Conversation>, unpickedOnly:preset |
| `ConversationDataChoiceCount` | `2D87461D` | call | `int` | conversation:gamelink<Conversation> |
| `ConversationDataChoiceGetPicked` | `16145DBD` | call | `preset` | conversation:gamelink<Conversation>, choice:string |
| `ConversationDataChoiceGetPickedCount` | `30B91587` | call | `int` | conversation:gamelink<Conversation>, choice:string |
| `ConversationDataChoiceGetState` | `72E4CB68` | call | `preset` | conversation:gamelink<Conversation>, choice:string |
| `ConversationDataChoiceId` | `2762F358` | call | `string` | conversation:gamelink<Conversation>, index:int |
| `ConversationDataChoiceSetPicked` | `04D1BB21` | action | `—` | conversation:gamelink<Conversation>, choice:string, picked:preset |
| `ConversationDataChoiceSetPickedCount` | `46091664` | action | `—` | conversation:gamelink<Conversation>, choice:string, count:int |
| `ConversationDataChoiceSetState` | `E9BC63EC` | action | `—` | conversation:gamelink<Conversation>, choice:string, state:preset |
| `ConversationDataGetSound` | `1CB17B1A` | call | `gamelink<Sound>` | line:convline, conditions:preset |
| `ConversationDataGetSpeaker` | `4F73B77F` | call | `gamelink<Character>` | line:convline |
| `ConversationDataLineCount` | `0261D6DB` | call | `int` | conversation:gamelink<Conversation> |
| `ConversationDataLineGetPickedCount` | `6C372B64` | call | `int` | conversation:gamelink<Conversation>, line:string |
| `ConversationDataLineHideForObservers` | `9226CEAC` | action | `—` | conversation:gamelink<Conversation>, line:string, showHide:preset |
| `ConversationDataLineId` | `0F7F949A` | call | `string` | conversation:gamelink<Conversation>, index:int |
| `ConversationDataLineResetPlayers` | `CDDDE678` | action | `—` | conversation:gamelink<Conversation>, line:string |
| `ConversationDataLineSetPickedCount` | `771DB1E0` | action | `—` | conversation:gamelink<Conversation>, line:string, count:int |
| `ConversationDataLineSetPlayers` | `1852EE72` | action | `—` | conversation:gamelink<Conversation>, line:string, players:playergroup |
| `ConversationDataLoadNodeState` | `492B0420` | action | `—` | conversation:gamelink<Conversation>, bank:bank, section:string |
| `ConversationDataLoadStateValue` | `21AA98D4` | action | `—` | state:convstateindex, bank:bank, section:string |
| `ConversationDataLoadStateValues` | `C89D042F` | action | `—` | state:gamelink<ConversationState>, bank:bank, section:string |
| `ConversationDataPreloadLines` | `79B97088` | action | `—` | conversation:gamelink<Conversation> |
| `ConversationDataPreloadLinesQueue` | `DB9FF4B2` | action | `—` | conversation:gamelink<Conversation> |
| `ConversationDataRegisterCamera` | `AE81B9B9` | action | `—` | cameraStateIndex:convstateindex, characterStateIndex:convcharacter, camera:camerainfo, trigger:trigger, waitOption:preset |
| `ConversationDataRegisterPortrait` | `DAC9B6F4` | action | `—` | stateIndex:convcharacter, portrait:portrait |
| `ConversationDataRegisterUnit` | `980B0F3D` | action | `—` | stateIndex:convcharacter, unit:unit |
| `ConversationDataResetNodeState` | `5655BFB2` | action | `—` | conversation:gamelink<Conversation> |
| `ConversationDataResetStateValues` | `F4A801D6` | action | `—` | state:gamelink<ConversationState> |
| `ConversationDataRun` | `01E8D3AB` | action | `—` | conversation:gamelink<Conversation>, players:playergroup, skipOption:preset, waitUntilDone:preset |
| `ConversationDataSaveNodeState` | `FD5F371E` | action | `—` | conversation:gamelink<Conversation>, bank:bank, section:string |
| `ConversationDataSaveStateValue` | `1BC8CC89` | action | `—` | state:convstateindex, bank:bank, section:string |
| `ConversationDataSaveStateValues` | `D2CACC80` | action | `—` | state:gamelink<ConversationState>, bank:bank, section:string |
| `ConversationDataSetListenerGender` | `A8C803FF` | action | `—` | conversation:gamelink<Conversation>, gender:preset |
| `ConversationDataSimulateRun` | `E167919B` | action | `—` | conversation:gamelink<Conversation> |
| `ConversationDataStateAbilCmd` | `BC670F99` | call | `abilcmd` | stateIndex:convstateindex, infoName:string |
| `ConversationDataStateAttachPoint` | `A6CB6DE1` | call | `preset` | stateIndex:convstateindex |
| `ConversationDataStateFixedValue` | `8E8800DE` | call | `fixed` | stateIndex:convstateindex, infoName:string |
| `ConversationDataStateGetValue` | `3640318E` | call | `int` | stateIndex:convstateindex |
| `ConversationDataStateImageEdge` | `0671F90F` | call | `preset` | stateIndex:convstateindex |
| `ConversationDataStateImagePath` | `D438ACED` | call | `filepath` | stateIndex:convstateindex |
| `ConversationDataStateIndex` | `A8967217` | call | `convstateindex` | state:gamelink<ConversationState>, index:int |
| `ConversationDataStateIndexCount` | `0D536382` | call | `int` | state:gamelink<ConversationState> |
| `ConversationDataStateModel` | `23C055F5` | call | `gamelink<Model>` | stateIndex:convstateindex, infoName:string |
| `ConversationDataStateMoviePath` | `D629F083` | call | `filepath` | stateIndex:convstateindex |
| `ConversationDataStateName` | `03FCA0F4` | call | `text` | stateIndex:convstateindex |
| `ConversationDataStateSetValue` | `6F9EA069` | action | `—` | stateIndex:convstateindex, value:int |
| `ConversationDataStateText` | `7AECAA34` | call | `text` | stateIndex:convstateindex, textName:string |
| `ConversationDataStateUpgrade` | `7F3B8C11` | call | `gamelink<Upgrade>` | stateIndex:convstateindex, infoName:string |
| `ConversationDataStop` | `FE7D2FC2` | action | `—` | — |
| `ConversationDataWasSkipped` | `09743718` | call | `bool` | — |
| `ConversationDestroy` | `00000423` | action | `—` | conversationId:conversation |
| `ConversationDestroyAll` | `0CAAF72B` | action | `—` | — |
| `ConversationLastCreated` | `00000428` | call | `conversation` | — |
| `ConversationReplyCreate` | `00000424` | action | `—` | conversationId:conversation, replyText:text |
| `ConversationReplyDestroy` | `00000425` | action | `—` | conversationId:conversation, replyId:reply |
| `ConversationReplyDestroyAll` | `B74ED594` | action | `—` | conversationId:conversation |
| `ConversationReplyGetIndex` | `DC33CC5B` | call | `int` | conversation:conversation, reply:reply |
| `ConversationReplyGetState` | `7F3583EE` | call | `preset` | conversation:conversation, reply:reply |
| `ConversationReplyGetText` | `27EC1771` | call | `text` | conversation:conversation, reply:reply |
| `ConversationReplyLastCreated` | `00000429` | call | `reply` | — |
| `ConversationReplySetState` | `11E3E4E8` | action | `—` | conversationId:conversation, replyId:reply, state:preset |
| `ConversationReplySetText` | `34032A0C` | action | `—` | conversationId:conversation, replyId:reply, text:text |
| `ConversationShow` | `4EAAEF83` | action | `—` | conversation:conversation, players:playergroup, show:preset |
| `ConversationVisible` | `00000427` | call | `bool` | conversation:conversation, player:int |
| `Convert3DRotationToString` | `B941EEFE` | call | `string` | forwardX:fixed, forwardY:fixed, forwardZ:fixed, upX:fixed, upY:fixed, upZ:fixed |
| `Convert3DVectorToString` | `47E87DB9` | call | `string` | x:fixed, y:fixed, z:fixed |
| `ConvertBearingsToString` | `14FA3995` | call | `string` | positionX:fixed, positionY:fixed, positionZ:fixed, forwardX:fixed, forwardY:fixed, forwardZ:fixed, upX:fixed, upY:fixed, upZ:fixed |
| `ConvertBooleanToString` | `FBC1DB4B` | call | `string` | value:bool |
| `ConvertBooleanToText` | `27F04219` | call | `text` | value:bool |
| `ConvertCatalogEntryToString` | `0DB2052E` | call | `string` | val:catalogentry |
| `ConvertCatalogFieldNameToString` | `7B1F9C97` | call | `string` | val:catalogfieldname |
| `ConvertCatalogFieldPathToString` | `8DC8D5BB` | call | `string` | val:catalogfieldpath |
| `ConvertCatalogReferenceAnyNumeric` | `96DDB210` | call | `reference` | val:reference |
| `ConvertCatalogReferenceAnyUpgrade` | `1DD7C745` | call | `reference` | val:reference |
| `ConvertCatalogReferenceNumericAny` | `72709D7A` | call | `reference` | val:reference |
| `ConvertCatalogReferenceToString` | `8C4A6359` | call | `string` | val:reference |
| `ConvertCatalogReferenceUpgradeAny` | `A9C9ADB0` | call | `reference` | val:reference |
| `ConvertCatalogScopeToString` | `84ED099C` | call | `string` | val:catalogscope |
| `ConvertColorToString` | `92F6A711` | call | `string` | color:color |
| `ConvertIntegerToDebugMessageType` | `525980C8` | call | `preset` | value:int |
| `ConvertPlayerColorToColor` | `386041AD` | call | `color` | playerColor:playercolor |
| `ConvertPointToString` | `403F456B` | call | `string` | value:point |
| `ConvertPresetToColor` | `981D376E` | call | `color` | value:anypreset |
| `ConvertPresetToConversation` | `E8C73178` | call | `conversation` | value:anypreset |
| `ConvertPresetToConversation2` | `D5D8205F` | call | `gamelink<Unit>` | value:anypreset |
| `ConvertPresetToIdentifier` | `31D70B8A` | call | `string` | value:anypreset |
| `ConvertPresetToInteger` | `FC63B7AA` | call | `int` | value:anypreset |
| `ConvertPresetToPoint` | `A75AC637` | call | `point` | value:anypreset |
| `ConvertPresetToPurchasable` | `0AD7E8DB` | call | `void` | value:anypreset |
| `ConvertPresetToReal` | `3152CF4A` | call | `fixed` | value:anypreset |
| `ConvertPresetToRegion` | `D0FF42A7` | call | `region` | value:anypreset |
| `ConvertPresetToReply` | `A207FED9` | call | `reply` | value:anypreset |
| `ConvertPresetToRevealer` | `5A32C171` | call | `revealer` | value:anypreset |
| `ConvertPresetToString` | `3156121D` | call | `string` | value:anypreset |
| `ConvertPresetToTransmission` | `C45B6962` | call | `transmission` | value:anypreset |
| `ConvertPresetToTrigger` | `34F76B31` | call | `trigger` | value:anypreset |
| `ConvertPresetToUnit` | `7FB12E7B` | call | `unit` | value:anypreset |
| `ConvertPresetToUnitFilter` | `439968B0` | call | `unitfilter` | value:anypreset |
| `ConvertStringToBoolean` | `708A367F` | call | `bool` | value:string |
| `ConvertStringToCatalogEntry` | `2FCF6091` | call | `catalogentry` | val:string |
| `ConvertStringToCatalogFieldName` | `3CB80413` | call | `catalogfieldname` | val:string |
| `ConvertStringToCatalogFieldPath` | `AEA77E17` | call | `catalogfieldpath` | val:string |
| `ConvertStringToCatalogReference` | `D61D9AE8` | call | `reference` | val:string |
| `ConvertStringToCatalogScope` | `F916E6BB` | call | `catalogscope` | val:string |
| `ConvertStringToCutsceneFile` | `C9157A77` | call | `filepath` | val:string |
| `ConvertStringToGameLink` | `8051F8E8` | call | `gamelink` | val:string |
| `ConvertStringToImageFile` | `83C46900` | call | `filepath` | val:string |
| `ConvertStringToMovieFile` | `CD9B99A9` | call | `filepath` | val:string |
| `ConvertStringToPoint` | `F4457D8D` | call | `point` | value:string |
| `ConvertStringToUILayoutFrameName` | `F37A4EA9` | call | `layoutframerel` | value:string |
| `ConvertStringToUserDataInstance` | `90D54CA4` | call | `userinstance` | val:string |
| `ConvertTargetFilterStringToUnitFilter` | `3C562CE8` | call | `unitfilter` | targetFilterString:string |
| `ConvertUnitToUnitGroup` | `BAEAC6C3` | call | `unitgroup` | unit:unit |
| `ConvertXYToString` | `3572C7A4` | call | `string` | x:fixed, y:fixed |
| `CopyOfCameraObject` | `40DE9B0A` | call | `camerainfo` | cam:camerainfo |
| `CopyUnitControlGroups` | `C47F05C7` | action | `—` | sourceUnit:unit, targetUnit:unit |
| `Cos` | `00000016` | call | `fixed` | a:fixed |
| `CostOfAbility` | `9A69046F` | call | `fixed` | ability:gamelink<Abil>, costType:preset |
| `Create` | `FF9A25CE` | call | `actormsg` | actor:string, content:string |
| `CreateActorAtPoint` | `6A72FDF0` | action | `—` | actor:gamelink<Actor>, position:point |
| `CreateCopy` | `0EA028E2` | call | `actormsg` | createKey:gamelink<Actor>, sourceKey:gamelink<Actor> |
| `CreateDialogItemAchievement` | `7C10A2B1` | action | `—` | dialog:dialog, width:int, height:int, anchor:preset, offsetX:int, offsetY:int, tooltip:text, achievement:gamelink<Achievement> |
| `CreateDialogItemButton` | `096ADF1D` | action | `—` | dialog:dialog, width:int, height:int, anchor:preset, offsetX:int, offsetY:int, tooltip:text, buttonText:text, hoverImage:filepath |
| `CreateDialogItemCheckBox` | `536FF98E` | action | `—` | dialog:dialog, width:int, height:int, anchor:preset, offsetX:int, offsetY:int, tooltip:text, checked:preset |
| `CreateDialogItemImage` | `CFF28424` | action | `—` | dialog:dialog, width:int, height:int, anchor:preset, offsetX:int, offsetY:int, tooltip:text, image:filepath, imageType:preset, tiled:bool, tintColor:color, blendMode:preset |
| `CreateDialogItemLabel` | `613EA67B` | action | `—` | dialog:dialog, width:int, height:int, anchor:preset, offsetX:int, offsetY:int, text:text, color:color, textWriteout:bool, textWriteoutDuration:fixed |
| `CreateExplosionAtPoint` | `29445666` | action | `—` | size:preset, race:preset, point:point |
| `CreateLookAtTargetAtPoint` | `0DF623B9` | action | `—` | point:point |
| `CreateLookAtTargetAtUnitAttachPoint` | `84C82092` | action | `—` | unit:unit, attachPoint:preset |
| `CreateModelAtPoint` | `9E360BAC` | action | `—` | model:gamelink<Model>, position:point |
| `CreateModelWithPointFacing` | `F9E1F767` | action | `—` | model:gamelink<Model>, position:point |
| `CreatePingFacingAngle` | `F09DDBE5` | action | `—` | players:playergroup, model:gamelink<Model>, position:point, color:color, duration:fixed, angle:fixed |
| `CreateRandomItemLootAtPoint` | `E1934B90` | action | `—` | dropPlayer:int, dropLocation:point, level:int, class:gamelink<ItemClass>, killerPlayer:int |
| `CreateTriggerFromTrigger` | `6876880C` | call | `trigger` | trig:trigger |
| `CreateUnitsAtPoint2` | `F20A0011` | action | `—` | count:int, type:gamelink<Unit>, flags:preset, player:int, p:point |
| `CreateUnitsWithDefaultFacing` | `F247156C` | action | `—` | count:int, type:gamelink<Unit>, style:preset, player:int, p:point |
| `CreepAdjacent` | `00000248` | call | `int` | inPosition:point |
| `CreepIsPresent` | `00000249` | call | `bool` | inPosition:point |
| `CreepModify` | `752159DD` | action | `—` | position:point, radius:fixed, add:preset, permanent:preset |
| `CreepSetSpeed` | `E9307270` | action | `—` | type:preset, speed:fixed |
| `CriticalSection` | `E914D77C` | action | `—` | lock:bool +1sub |
| `CrossCliff` | `616958FB` | call | `bool` | from:point, destination:point |
| `CurrentDateTimeGet` | `FFF0634E` | call | `datetime` | — |
| `CurrentSynchronousGameTimeGet` | `2587CFFD` | call | `int` | — |
| `customscriptaction` | `00000123` | action | `—` | — |
| `CutsceneAddFilter` | `2B0BC614` | action | `—` | inCutscene:preset, inFilter:string |
| `CutsceneAddGlobalFilter` | `8F7789A0` | action | `—` | inFilter:string |
| `CutsceneClearFilters` | `37449FDB` | action | `—` | inCutscene:preset |
| `CutsceneClearGlobalFilters` | `D07F23C9` | action | `—` | — |
| `CutsceneCreate` | `E734B4C9` | action | `—` | inFilePath:filepath, pos:point, players:playergroup, inAutoPlay:bool |
| `CutsceneCreateNew` | `5958C7E2` | action | `—` | inFilePath:filepath, pos:point, inFacing:fixed, players:playergroup, inAutoPlay:bool |
| `CutsceneCreateNoPosition` | `9FEEA352` | action | `—` | inFilePath:filepath, players:playergroup, inAutoPlay:bool |
| `CutsceneFade` | `D27035F2` | action | `—` | fadeIn:preset, duration:fixed, color:color, amount:fixed, players:playergroup, inWaitUntilDone:preset |
| `CutsceneGetTriggerControl` | `E6F8D690` | call | `preset` | dialogItem:control |
| `CutsceneGoToBookmark` | `0E8BB6F9` | action | `—` | inCutscene:preset, inBookmarkName:string |
| `CutsceneGoToNextBookmark` | `78D16252` | action | `—` | inCutscene:preset |
| `CutsceneLastCreated` | `D3945DFC` | call | `preset` | — |
| `CutscenePause` | `255071AA` | action | `—` | inCutscene:preset |
| `CutscenePlay` | `C560675A` | action | `—` | inCutscene:preset |
| `CutscenePlayCutsceneRangeOverTime` | `66D7B3DE` | action | `—` | inCutscene:preset, inBookmarkStart:string, inBookmarkEnd:string, inDuration:fixed |
| `CutsceneRemoveFilter` | `271877CA` | action | `—` | inCutscene:preset, inFilter:string |
| `CutsceneRemoveGlobalFilter` | `306DF22B` | action | `—` | inFilter:string |
| `CutsceneSetFilter` | `4AF94EF5` | action | `—` | inCutscene:preset, inFilter:string |
| `CutsceneSetGlobalFilter` | `F21A4305` | action | `—` | inFilter:string |
| `CutsceneSetTime` | `9372FA34` | action | `—` | inCutscene:preset, inTime:int |
| `CutsceneShow` | `3E451023` | action | `—` | inCutscene:preset, inShow:preset |
| `CutsceneStop` | `C575C576` | action | `—` | inCutscene:preset |
| `Cycle` | `B90251D8` | action | `—` | var:anyvariable, inMin:int, inMax:int |
