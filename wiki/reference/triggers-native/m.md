# SC2 Native Functions: M

Columns are documented in [../triggers-native-functions.md](../triggers-native-functions.md). Reference in XML as `<FunctionDef Type="FunctionDef" Library="Ntve" Id="<ID>"/>`.

Parameter defaults in `nativelib` do not auto-apply; emit an explicit `<Parameter Type="Param" Id="..."/>` for every slot in generated `<FunctionCall>` XML.

### M

<a id="m"></a>

| Name | ID | Kind | Returns | Params |
|---|---|---|---|---|
| `MainActorofUnit` | `3EC64613` | call | `actor` | unit:unit |
| `MakeModelFaceAngle` | `1AECAFA1` | action | `—` | model:actor, angle:fixed |
| `MakeMsgAnimBracketResume` | `BD1A4B1B` | call | `actormsg` | animName:string, animTransitionFlags:int, timeVariant:fixed, timeType:int |
| `MakeMsgAnimBracketStart` | `A0515E2B` | call | `actormsg` | animName:string, openingProps:modelanim, contentProps:modelanim, closingProps:modelanim, animBracketStartFlags:int, timeVariant:fixed, timeType:preset |
| `MakeMsgAnimBracketStop` | `FA920336` | call | `actormsg` | animName:string, animTransitionFlags:int, timeVariant:fixed, timeType:preset |
| `MakeMsgAnimGroupApply` | `BB55CA40` | call | `actormsg` | props:string, atApply:string, atRemove:string, flags:int, timeVariant:fixed, timeType:preset |
| `MakeMsgAnimGroupRemove` | `ED6A6613` | call | `actormsg` | props:string, flags:int, timeVariant:fixed, timeType:preset |
| `MakeMsgAnimPlay` | `6EB4CCC9` | call | `actormsg` | animName:string, props:string, flags:int, blendIn:fixed, blendOut:fixed, timeVariant:fixed, timeType:preset |
| `MakeMsgRefCreate` | `20C84C20` | call | `actormsg` | actorRefName:string |
| `MakeMsgRefSetFromRequest` | `EC829255` | call | `actormsg` | refName:string, subject:string, effectName:string, requestScope:int, requestActor:int |
| `MakeMsgRefTableDump` | `4F763EBD` | call | `actormsg` | space:int |
| `MakeMsgSetPhysicsState` | `2B1990F3` | call | `actormsg` | state:int, delayLow:fixed, delayHigh:fixed |
| `MakeMsgTextureSelectByMatch` | `50D2D614` | call | `actormsg` | slotName:string, slotComponent:int, sourceSlotName:string, sourceSlotComponent:int |
| `MakeMsgTextureSelectBySlot` | `A6ED7BDA` | call | `actormsg` | slotName:string, slotComponent:int, textureExpression:string |
| `MakeMsgTextureVideoPlay` | `03E24F00` | call | `actormsg` | slotName:string, slotComponent:int, fPS:int, textureVideoPlayFlags:int, soundType:int, attachQuery:string |
| `MakeMsgTextureVideoPlay` | `E758567E` | call | `actormsg` | texture:gamelink<Texture>, fPS:int, textureVideoPlayFlags:int, soundType:int, attachQuery:string |
| `MakeMsgTextureVideoSetFrame` | `F39DC67E` | call | `actormsg` | slotName:string, slotComponent:int, frame:int |
| `MakeMsgTextureVideoSetPaused` | `DB263E75` | call | `actormsg` | slotName:string, slotComponent:int, pauseState:bool |
| `MakeMsgTextureVideoSetTime` | `698068EA` | call | `actormsg` | slotName:string, slotComponent:int, time:fixed |
| `MakeMsgTextureVideoStop` | `7BE4C0B6` | call | `actormsg` | slotName:string, slotComponent:int |
| `MakeMsgTransition` | `09D4CE38` | call | `actormsg` | transitionType:int, durationBase:fixed, durationRange:fixed |
| `MakeUnitFacePoint` | `D5445D96` | action | `—` | unit:unit, point:point, duration:fixed |
| `MakeUnitInvulnerable` | `50000000` | action | `—` | unit:unit, option:preset |
| `MakeUnitLookAtPoint` | `893DBB6D` | action | `—` | unit:unit, type:preset, point:point |
| `MakeUnitLookAtUnit` | `752DBBCA` | action | `—` | unit:unit, type:preset, lookAtTargetUnit:unit, attachPoint:preset |
| `MakeUnitUncommandable` | `02FA0FB6` | action | `—` | unit:unit, option:preset |
| `MaxF` | `8CD87612` | call | `fixed` | value1:fixed, value2:fixed |
| `MaxI` | `D7C3FBC2` | call | `int` | value1:int, value2:int |
| `MeleeGetOption` | `00000147` | call | `bool` | player:int, option:preset |
| `MeleeInitAI` | `00000150` | action | `—` | — |
| `MeleeInitOptions` | `00000148` | action | `—` | — |
| `MeleeInitResources` | `00000143` | action | `—` | — |
| `MeleeInitResourcesForPlayer` | `00000142` | action | `—` | player:int, race:gamelink<Race> |
| `MeleeInitUnits` | `00000145` | action | `—` | — |
| `MeleeInitUnitsForPlayer` | `00000144` | action | `—` | player:int, race:gamelink<Race>, position:point |
| `MeleeSetOption` | `00000146` | action | `—` | player:int, option:preset, value:preset |
| `MercenaryCreate` | `2B7D8F16` | action | `—` | playerGroup:playergroup, state:preset |
| `MercenaryDestroy` | `C207359F` | action | `—` | mercenaryId:preset |
| `MercenaryGetSelected` | `EF89DD5C` | call | `preset` | player:int |
| `MercenaryIsRecentlyPurchased` | `41D8CB23` | call | `bool` | mercenaryId:preset |
| `MercenaryLastCreated` | `44CDDA9F` | call | `preset` | — |
| `MercenaryPanelSetCloseButtonEnabled` | `A1799B8B` | action | `—` | playerGroup:playergroup, enable:preset |
| `MercenaryPanelSetDismissButtonEnabled` | `56FC881F` | action | `—` | playerGroup:playergroup, enable:preset |
| `MercenaryPurchase` | `F2A3CE0B` | action | `—` | mercenaryId:preset |
| `MercenarySetAvailabilityText` | `21C9FBA2` | action | `—` | mercenaryId:preset, text:text |
| `MercenarySetCost` | `D5F8F800` | action | `—` | mercenaryId:preset, cost:int |
| `MercenarySetCostText` | `F1E13097` | action | `—` | mercenaryId:preset, text:text |
| `MercenarySetDescriptionText` | `D0326678` | action | `—` | mercenaryId:preset, text:text |
| `MercenarySetImageFilePath` | `2810F013` | action | `—` | mercenaryId:preset, file:filepath |
| `MercenarySetModelLink` | `66998AC0` | action | `—` | mercenaryId:preset, model:gamelink<Model> |
| `MercenarySetPlayerGroup` | `C77C4644` | action | `—` | mercenaryId:preset, playerGroup:playergroup |
| `MercenarySetRecentlyPurchased` | `FD8E7170` | action | `—` | mercenaryId:preset, recentlyPurchased:bool |
| `MercenarySetScenePath` | `0136DB78` | action | `—` | mercenaryId:preset, scenePath:filepath |
| `MercenarySetSelected` | `C1F1F6F4` | action | `—` | players:playergroup, mercenaryId:preset |
| `MercenarySetSpecialText` | `51AB9E30` | action | `—` | mercenaryId:preset, text:text |
| `MercenarySetState` | `5F4CAE0C` | action | `—` | mercenaryId:preset, state:preset |
| `MercenarySetTitleText` | `C4977CE8` | action | `—` | mercenaryId:preset, text:text |
| `MercenarySetUnitText` | `15B13A85` | action | `—` | mercenaryId:preset, text:text |
| `MidPoint` | `44B227B6` | call | `point` | sourcePoint:point, targetPoint:point |
| `MinF` | `CC8AC2DC` | call | `fixed` | value1:fixed, value2:fixed |
| `MinI` | `7AE49F4E` | call | `int` | value1:int, value2:int |
| `MinimapPing` | `00000199` | action | `—` | players:playergroup, pos:point, dur:fixed, color:color |
| `MinimapPingPossibleEnemyStartLocations` | `747352A6` | action | `—` | dur:fixed, modelLink:gamelink<Model>, color:color |
| `MissileTentacleReturn` | `D9339BB5` | call | `actormsg` | — |
| `ModelAnimationLoad` | `153AEC4D` | action | `—` | model:filepath, animation:filepath |
| `ModelAnimationLoadOverriding` | `44BDDDF8` | action | `—` | model:filepath, animation:filepath |
| `ModelAnimationUnload` | `E8A7971D` | action | `—` | model:filepath, animation:filepath |
| `ModelEventSuppress` | `ED17978F` | call | `actormsg` | value:int, event:string |
| `ModelSwap` | `C1374D79` | call | `actormsg` | model:gamelink<Model>, variation:int |
| `ModF` | `00000014` | call | `fixed` | x:fixed, y:fixed |
| `ModI` | `EEDB2448` | call | `int` | x:int, y:int |
| `MoveBossBar` | `6B027921` | action | `—` | bossBarID:int, anchor:preset, offsetX:int, offsetY:int |
| `MoverMove` | `B78EB09C` | call | `actormsg` | — |
| `MoverSetAcceleration` | `07AE20F9` | call | `actormsg` | value:fixed |
| `MoverSetDeceleration` | `35657B65` | call | `actormsg` | value:fixed |
| `MoverSetDestination2D` | `5B8AEB0F` | call | `actormsg` | x:fixed, y:fixed |
| `MoverSetDestinationFrom` | `A96A3C0D` | call | `actormsg` | actorRefName:string |
| `MoverSetDestinationH` | `B0951308` | call | `actormsg` | value:fixed |
| `MoverSetDestinationZ` | `24BDA990` | call | `actormsg` | value:fixed |
| `MoverSetSpeed` | `0CA0580A` | call | `actormsg` | value:fixed |
| `MoverSetSpeedFromDuration` | `4DA2F9A8` | call | `actormsg` | value:fixed |
| `MoverSetSpeedMax` | `D348380E` | call | `actormsg` | value:fixed |
| `MoverStop` | `FF497CED` | call | `actormsg` | — |
| `MoverStopNow` | `BED7C7FE` | call | `actormsg` | — |
| `MovieAddSubTitle` | `734836A8` | action | `—` | title:string, duration:int, timeStamp:int |
| `MovieAddSubTitleText` | `D4E8CABF` | action | `—` | title:text, duration:int, timeStamp:int |
| `MovieAddTriggerFunction` | `3515E6EC` | action | `—` | function:string, timeStamp:int |
| `MovieDynamicSubtitlesandDuration` | `8ADA537A` | action | `—` | soundFile:gamelink<Sound> |
| `MoviePlayAfterGame` | `76E7054D` | action | `—` | players:playergroup, movie:filepath |
| `MovieStartRecording` | `5589BD13` | action | `—` | filename:string |
| `MovieStopRecording` | `0AF0A8DA` | action | `—` | — |
| `MultiplyScale` | `FB726C91` | call | `actormsg` | x:fixed, y:fixed, z:fixed, duration:fixed |
