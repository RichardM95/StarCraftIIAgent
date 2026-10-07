# SC2 Native Functions: T

Columns are documented in [../triggers-native-functions.md](../triggers-native-functions.md). Reference in XML as `<FunctionDef Type="FunctionDef" Library="Ntve" Id="<ID>"/>`.

Parameter defaults in `nativelib` do not auto-apply; emit an explicit `<Parameter Type="Param" Id="..."/>` for every slot in generated `<FunctionCall>` XML.

### T

<a id="t"></a>

| Name | ID | Kind | Returns | Params |
|---|---|---|---|---|
| `TalentTreeAllowed` | `80135FCD` | call | `bool` | player:int, talentTreeIndex:int |
| `TalentTreeCanSelectHeroTalentTree` | `7B294091` | call | `bool` | player:int, talentTreeIndex:int |
| `TalentTreeClearTier` | `48B91DC9` | action | `—` | player:int, tier:int |
| `TalentTreeGetHeroTalentLink` | `28A2ED75` | call | `gamelink<Talent>` | player:int, index:int |
| `TalentTreeGetSelectedHeroTalentTree` | `C9BEAF14` | call | `int` | player:int, tier:int |
| `TalentTreeGetSelectedHeroTalentTreeColumn` | `3426739F` | call | `int` | player:int, tier:int |
| `TalentTreeSetSelectedHeroTalentTree` | `142DA016` | action | `—` | player:int, talentTreeIndex:int |
| `Tan` | `00000017` | call | `fixed` | a:fixed |
| `TechTreeAbilityAllow` | `0F7C3248` | action | `—` | p:int, abilCmd:abilcmd, allow:preset |
| `TechTreeAbilityCount` | `00000252` | call | `int` | player:int, abilType:gamelink<Abil>, countType:preset |
| `TechTreeAbilityIsAllowed` | `69CE5404` | call | `bool` | p:int, abilCmd:abilcmd |
| `TechTreeBehaviorAllow` | `00000171` | action | `—` | p:int, behavior:gamelink<Behavior>, allow:preset |
| `TechTreeBehaviorCount` | `00000253` | call | `int` | player:int, behaviorType:gamelink<Behavior>, countType:preset |
| `TechTreeBehaviorIsAllowed` | `00000173` | call | `bool` | p:int, behavior:gamelink<Behavior> |
| `TechTreeGetProduceCap` | `697D52F2` | call | `int` | p:int, production:anygamelink, cat:preset |
| `TechTreeRequirementsEnable` | `00000227` | action | `—` | p:int, isEnabled:preset |
| `TechTreeRequirementsEnabled` | `8D939E46` | call | `bool` | inPlayer:int |
| `TechTreeRestrictionsEnable` | `12A2BFA8` | action | `—` | p:int, isEnabled:preset |
| `TechTreeRestrictionsEnabled` | `0640F776` | call | `bool` | inPlayer:int |
| `TechTreeSetProduceCap` | `5FA21D64` | action | `—` | p:int, production:anygamelink, cat:preset, cap:int |
| `TechTreeSpecificRequirementEnable` | `FF56BC56` | action | `—` | p:int, requirementName:gamelink<Requirement>, isEnabled:preset |
| `TechTreeSpecificRequirementEnabled` | `1FABC98B` | call | `bool` | inPlayer:int, requirementName:gamelink<Requirement> |
| `TechTreeUnitAliasCount` | `0800076A` | call | `int` | player:int, unitType:string, countType:preset |
| `TechTreeUnitAllow` | `51A273F5` | action | `—` | inPlayer:int, inUnit:gamelink<Unit>, inAllow:preset |
| `TechTreeUnitCount` | `00000254` | call | `int` | player:int, unitType:gamelink<Unit>, countType:preset |
| `TechTreeUnitHelp` | `34CD42EC` | action | `—` | inPlayer:int, inUnit:gamelink<Unit>, inShow:preset |
| `TechTreeUnitHelpDefault` | `0D6A99D5` | action | `—` | inPlayer:int, inShow:preset |
| `TechTreeUnitIsAllowed` | `DC0FD1CA` | call | `bool` | inPlayer:int, inUnit:gamelink<Unit> |
| `TechTreeUnitProducedAbilCmd` | `8A4F539D` | call | `abilcmd` | unitType:gamelink<Unit>, index:int |
| `TechTreeUnitProducedAbilCmdCount` | `BCBA150D` | call | `int` | unitType:gamelink<Unit> |
| `TechTreeUnitProducesUnit` | `A70A8731` | call | `gamelink<Unit>` | unitType:gamelink<Unit>, index:int |
| `TechTreeUnitProducesUnitCount` | `ED57ADB7` | call | `int` | unitType:gamelink<Unit> |
| `TechTreeUnitProducesUpgrade` | `FBEBD2FF` | call | `gamelink<Upgrade>` | unitType:gamelink<Unit>, index:int |
| `TechTreeUnitProducesUpgradeCount` | `B6C3B420` | call | `int` | unitType:gamelink<Unit> |
| `TechTreeUpgradeAddLevel` | `00000158` | action | `—` | p:int, upgrade:gamelink<Upgrade>, levels:int |
| `TechTreeUpgradeAllow` | `0B0A4FBE` | action | `—` | inPlayer:int, inUpgrade:gamelink<Upgrade>, inAllow:preset |
| `TechTreeUpgradeCount` | `00000255` | call | `int` | player:int, upgradeType:gamelink<Upgrade>, countType:preset |
| `TechTreeUpgradeIsAllowed` | `B0AF7420` | call | `bool` | inPlayer:int, inUpgrade:gamelink<Upgrade> |
| `TechTreeUpgradeProducedAbilCmd` | `3453CD67` | call | `abilcmd` | upgrade:gamelink<Upgrade>, index:int |
| `TechTreeUpgradeProducedAbilCmdCount` | `F13BEA1C` | call | `int` | upgrade:gamelink<Upgrade> |
| `TerrainShowRegion` | `0E7067FD` | action | `—` | area:region, add:preset |
| `TerrainTexture` | `7F47CC53` | call | `gamelink<TerrainTex>` | point:point |
| `TextCase` | `A0732ED7` | call | `text` | t:text, case:preset |
| `TextExpressionAssemble` | `4A5FC206` | call | `text` | expressionId:string |
| `TextExpressionSetToken` | `A7AC2BC1` | action | `—` | expressionId:string, token:string, text:text |
| `TextHasBeenSet` | `B835AED0` | ? | `—` | text:text |
| `TextReplaceWord` | `E9C385D5` | call | `text` | text:text, findText:text, replaceText:text, count:int, sensitivity:preset |
| `TextTagAttachToUnit` | `00000480` | action | `—` | tag:preset, unit:unit, heightOffset:fixed |
| `TextTagAttachToUnitPoint` | `0B8B44C9` | action | `—` | tag:preset, unit:unit, attachment:preset, offsetX:int, offsetY:int |
| `TextTagCreate` | `593FBAF8` | action | `—` | text:text, fontSize:int, point:point, heightOffset:fixed, visible:preset, useFogofWar:bool, players:playergroup |
| `TextTagDestroy` | `0E10EA33` | action | `—` | textTag:preset |
| `TextTagFogofWar` | `6A4E1C7A` | action | `—` | tag:preset, useFogOfWar:bool |
| `TextTagLastCreated` | `00000477` | call | `preset` | — |
| `TextTagPause` | `00000483` | action | `—` | tag:preset, pause:preset |
| `TextTagSetAlignment` | `118AFBB7` | action | `—` | textTag:preset, horizontal:preset, vertical:preset |
| `TextTagSetBackgroundBorderSize` | `64ABC678` | action | `—` | textTag:preset, horizontal:fixed, vertical:fixed |
| `TextTagSetBackgroundImage` | `B7865A0A` | action | `—` | textTag:preset, path:filepath, type:preset |
| `TextTagSetBackgroundOffset` | `3E74ECD1` | action | `—` | textTag:preset, horizontal:fixed, vertical:fixed |
| `TextTagSetColor` | `00000484` | action | `—` | tag:preset, type:preset, color:color |
| `TextTagSetEdgeImage` | `1D8C9244` | action | `—` | textTag:preset, edge:preset, path:filepath, xOffset:int, yOffset:int |
| `TextTagSetFadedTransparency` | `60AE2D46` | action | `—` | tag:preset, type:preset, transparency:fixed |
| `TextTagSetFogVisibility` | `ACDC47E4` | action | `—` | tag:preset, visibility:preset |
| `TextTagSetFontSize` | `35285FED` | action | `—` | tag:preset, fontSize:int |
| `TextTagSetGravity` | `80021754` | action | `—` | tag:preset, gravity:fixed |
| `TextTagSetMaxSize` | `6194C084` | action | `—` | textTag:preset, width:fixed, height:fixed |
| `TextTagSetPosition` | `00000479` | action | `—` | tag:preset, point:point, heightOffset:fixed |
| `TextTagSetText` | `4502CA5D` | action | `—` | tag:preset, text:text |
| `TextTagSetTextAlignment` | `F8AC8C36` | action | `—` | textTag:preset, horizontal:preset, vertical:preset |
| `TextTagSetTextShadow` | `98DD2F6E` | action | `—` | tag:preset, show:preset |
| `TextTagSetTime` | `00000485` | action | `—` | tag:preset, type:preset, time:fixed |
| `TextTagSetVelocity` | `00000481` | action | `—` | tag:preset, speed:fixed, angle:fixed |
| `TextTagShow` | `00000482` | action | `—` | tag:preset, players:playergroup, show:preset |
| `TextTagShowBackground` | `DD59EC03` | action | `—` | tag:preset, show:preset |
| `TextTagVisible` | `BE8E5192` | call | `bool` | textTag:preset, player:int |
| `TextTimeFormat` | `312E45EA` | call | `text` | format:text, seconds:int |
| `TextureDump` | `37F98E03` | call | `actormsg` | — |
| `TextureDumpDB` | `FAB12C79` | call | `actormsg` | — |
| `TextureGetSlotComponent` | `48707541` | call | `int` | texture:gamelink<Texture> |
| `TextureGetSlotName` | `9D56144F` | call | `string` | texture:gamelink<Texture> |
| `TextureGroupApply` | `37CB0A2B` | call | `actormsg` | textureProps:string |
| `TextureGroupRemove` | `6F9BE10D` | call | `actormsg` | textureProps:string |
| `TextureSelectByID` | `7BE74571` | call | `actormsg` | texture:gamelink<Texture> |
| `TextureVideoSetFrame` | `A71B4788` | call | `actormsg` | texture:gamelink<Texture>, frame:int |
| `TextureVideoSetPaused` | `27C61BAC` | call | `actormsg` | texture:gamelink<Texture>, pauseState:bool |
| `TextureVideoSetTime` | `1E22FEA1` | call | `actormsg` | texture:gamelink<Texture>, time:fixed |
| `TextureVideoStop` | `0A994220` | call | `actormsg` | texture:gamelink<Texture> |
| `TextureVideoStopAll` | `2921FDBE` | call | `actormsg` | — |
| `TextWithColor` | `C41602B8` | call | `text` | text:text, color:color |
| `TimerCreate` | `00000193` | call | `timer` | — |
| `TimerGetDuration` | `00000047` | call | `fixed` | t:timer |
| `TimerGetElapsed` | `00000045` | call | `fixed` | t:timer |
| `TimerGetRemaining` | `00000046` | call | `fixed` | t:timer |
| `TimerIsPaused` | `00000194` | call | `bool` | t:timer |
| `TimerKill` | `BF585957` | call | `actormsg` | timerName:string |
| `TimerLastStarted` | `7133B942` | call | `timer` | — |
| `TimerPause` | `00000044` | action | `—` | t:timer, pause:preset |
| `TimerRestart` | `00000043` | action | `—` | t:timer |
| `TimerSet` | `88B927DD` | call | `actormsg` | duration:fixed, timerName:string |
| `TimerStart` | `00000042` | action | `—` | t:timer, dur:fixed, r:preset, timeType:preset |
| `TimerWindowCreate` | `3FCF7471` | action | `—` | timer:timer, title:text, visible:preset, elapsed:preset |
| `TimerWindowDestroy` | `00000470` | action | `—` | window:preset |
| `TimerWindowLastCreated` | `00000469` | call | `preset` | — |
| `TimerWindowResetPosition` | `F5D626D2` | action | `—` | window:preset |
| `TimerWindowSetAnchor` | `46B37AA3` | action | `—` | window:preset, anchor:preset, xOffset:int, yOffset:int |
| `TimerWindowSetColor` | `00000475` | action | `—` | window:preset, component:preset, color:color, transparency:fixed |
| `TimerWindowSetFixedHeight` | `01DB37E9` | action | `—` | window:preset, height:int |
| `TimerWindowSetFormat` | `00000474` | action | `—` | window:preset, format:text |
| `TimerWindowSetGapWidth` | `CBDA955C` | action | `—` | window:preset, width:int |
| `TimerWindowSetImageType` | `8B93ABA7` | action | `—` | window:preset, image:preset, imageType:preset |
| `TimerWindowSetPosition` | `0132CF73` | action | `—` | window:preset, x:int, y:int |
| `TimerWindowSetProgressColor` | `B4CAC0EE` | action | `—` | window:preset, color:color, step:int |
| `TimerWindowSetStyle` | `A8D696A4` | action | `—` | window:preset, style:preset, elapsed:preset |
| `TimerWindowSetTimer` | `00000472` | action | `—` | window:preset, timer:timer |
| `TimerWindowSetTitle` | `00000473` | action | `—` | window:preset, title:text |
| `TimerWindowShow` | `00000471` | action | `—` | window:preset, players:playergroup, show:preset |
| `TimerWindowShowBorder` | `F8CE3E4B` | action | `—` | window:preset, showHide:preset |
| `TimerWindowShowProgressBar` | `C6215151` | action | `—` | window:preset, showHide:preset |
| `TimerWindowVisible` | `59B2676D` | call | `bool` | timerWindow:preset, player:int |
| `TipAlertPanelClear` | `8961130D` | action | `—` | players:playergroup |
| `TransmissionClear` | `F14A27E9` | action | `—` | Transmission:transmission |
| `TransmissionClearAll` | `74A20203` | action | `—` | — |
| `TransmissionClearGroup` | `C99843E9` | action | `—` | Players:playergroup |
| `TransmissionCommentConversation` | `8B09B461` | action | `—` | conversationLine:convline |
| `TransmissionCommentSound` | `B71CCE8B` | action | `—` | sound:soundlink |
| `TransmissionIsComplete` | `C752E622` | action | `—` | Transmission:transmission |
| `TransmissionLastSent` | `FDD4A4BA` | call | `transmission` | — |
| `TransmissionPlayerHasActiveTransmission` | `C3330C0E` | call | `bool` | player:int |
| `TransmissionSend` | `3E151A17` | action | `—` | Players:playergroup, Source:transmissionsource, Target:portrait, PortraitAnim:modelanim, Sound:soundlink, Speaker:text, Subtitle:text, Duration:fixed, DurationType:preset, WaitUntilDone:preset |
| `TransmissionSendAdvanced` | `7C3D2EC1` | action | `—` | Players:playergroup, Source:transmissionsource, Target:portrait, portraitActor:string, PortraitAnim:modelanim, Sound:soundlink, Speaker:text, Subtitle:text, Duration:fixed, DurationType:preset, WaitUntilDone:preset |
| `TransmissionSendForPlayer` | `36030744` | action | `—` | Players:playergroup, Source:transmissionsource, Target:portrait, portraitActor:string, PortraitAnim:modelanim, Sound:soundlink, Speaker:text, Subtitle:text, Duration:fixed, DurationType:preset, WaitUntilDone:preset, player:int |
| `TransmissionSendForPlayerSelect` | `00B542C6` | action | `—` | Players:playergroup, Source:transmissionsource, Target:portrait, portraitActor:string, PortraitAnim:modelanim, Sound:soundlink, Speaker:text, Subtitle:text, Duration:fixed, DurationType:preset, WaitUntilDone:preset, player:int, isSelect:bool |
| `TransmissionSetOption` | `6A8571AA` | action | `—` | option:preset, value:preset |
| `TransmissionSource` | `C551984B` | call | `transmissionsource` | — |
| `TransmissionSourceFromModel` | `A2B4587F` | call | `transmissionsource` | ModelLink:gamelink<Model> |
| `TransmissionSourceFromMovie` | `8EE91657` | call | `transmissionsource` | movie:filepath, Subtitles:preset |
| `TransmissionSourceFromUnit` | `63326FA7` | call | `transmissionsource` | Unit:unit, Flash:preset, overridePortrait:preset, anim:modelanim |
| `TransmissionSourceFromUnitType` | `ED236D9F` | call | `transmissionsource` | UnitType:gamelink<Unit>, overridePortrait:preset |
| `TransmissionSourceSetBypassMessageLog` | `80967F7E` | action | `—` | transmissionSource:transmissionsource, bypassMessageLog:bool |
| `TransmissionSourceSetPauseAllowed` | `05907BE5` | action | `—` | transmissionSource:transmissionsource, allowed:bool |
| `TransmissionSourceSetStreamingAllowed` | `DE6FA654` | action | `—` | transmissionSource:transmissionsource, allowed:bool |
| `TransmissionWait` | `95E0136A` | action | `—` | Transmission:transmission, Offset:fixed |
| `TriggerActiveCount` | `CA944256` | call | `int` | t:trigger |
| `TriggerAddEventAbortMission` | `D118DC34` | event | `—` | player:int |
| `TriggerAddEventAlert` | `5609879F` | event | `—` | player:int, alertType:gamelink<Alert> |
| `TriggerAddEventBattleReportPanelExit` | `04F8A778` | event | `—` | player:int |
| `TriggerAddEventBattleReportPanelPlayMission` | `0D8601D1` | event | `—` | player:int |
| `TriggerAddEventBattleReportPanelPlayScene` | `88DC0BE2` | event | `—` | player:int |
| `TriggerAddEventBattleReportPanelSelectionChanged` | `D6AC1BD1` | event | `—` | player:int |
| `TriggerAddEventButtonPressed` | `4537C855` | event | `—` | player:int, button:gamelink<Button> |
| `TriggerAddEventCameraMove` | `FEC6DC29` | event | `—` | player:int, reason:preset |
| `TriggerAddEventChatMessage` | `00000121` | event | `—` | p:int, s:string, exact:preset |
| `TriggerAddEventCheatUsed` | `EBF1B8BE` | event | `—` | p:int, type:preset |
| `TriggerAddEventCommandError` | `064BA8D5` | event | `—` | player:int, error:preset, ability:abilcmd |
| `TriggerAddEventConversationReplySelected` | `00000430` | event | `—` | player:int, conversationId:conversation, replyId:reply |
| `TriggerAddEventConversationStateChanged` | `1A5B4F15` | event | `—` | state:convstateindex |
| `TriggerAddEventCustomDialogDismissed` | `8ACCD431` | event | `—` | player:int, player2:preset |
| `TriggerAddEventCutsceneBookmarkFired` | `22F7DAC6` | event | `—` | cutscene:preset, bookmark:string |
| `TriggerAddEventCutsceneEndSceneFired` | `2C194B61` | event | `—` | cutscene:preset |
| `TriggerAddEventDialogControl` | `B5222B7D` | event | `—` | player:int, item:control, eventType:preset |
| `TriggerAddEventGameCreditsFinished` | `14463CDD` | event | `—` | player:int |
| `TriggerAddEventGameMenuItemSelected` | `CBC81630` | event | `—` | player:int, gameMenuItem:preset |
| `TriggerAddEventGameTimeEvent` | `548F27E8` | event | `—` | type:preset |
| `TriggerAddEventGeneric` | `B1A02C2E` | event | `—` | eventName:string |
| `TriggerAddEventHeroTalentTreeSelected` | `D6274473` | event | `—` | player:int |
| `TriggerAddEventHeroTalentTreeSelectionPanelHidden` | `8AC9706F` | event | `—` | player:int |
| `TriggerAddEventHeroTalentTreeSelectionPanelShown` | `58B6B999` | event | `—` | player:int |
| `TriggerAddEventHotkeyPressed` | `7603DD9E` | event | `—` | player:int, hotkey:preset, down:preset |
| `TriggerAddEventKeyPressed` | `9A2A3734` | event | `—` | player:int, key:preset, down:preset, s2:preset, c2:preset, a2:preset |
| `TriggerAddEventLoadGameDone` | `7718C008` | event | `—` | — |
| `TriggerAddEventMapInit` | `00000120` | event | `—` | — |
| `TriggerAddEventMercenaryPanelExit` | `D74747BE` | event | `—` | player:int |
| `TriggerAddEventMercenaryPanelPurchase` | `135A1AB6` | event | `—` | player:int |
| `TriggerAddEventMercenaryPanelSelectionChanged` | `31733644` | event | `—` | player:int, mercenaryId:preset |
| `TriggerAddEventMouseClicked` | `9C6C63CD` | event | `—` | player:int, button:preset, down:preset |
| `TriggerAddEventMouseMoved` | `A0A36942` | event | `—` | player:int |
| `TriggerAddEventMouseWheel` | `4EF11807` | event | `—` | player:int |
| `TriggerAddEventMovieFinished` | `797B402B` | event | `—` | player:int |
| `TriggerAddEventMovieFunction` | `368847BB` | event | `—` | player:int, functionName:string |
| `TriggerAddEventMovieStarted` | `2E4B6EB0` | event | `—` | player:int |
| `TriggerAddEventPing` | `A51B0998` | event | `—` | p:int |
| `TriggerAddEventPlanetMissionLaunched` | `4625F7F7` | event | `—` | player:int |
| `TriggerAddEventPlanetMissionSelected` | `33244FA8` | event | `—` | player:int, planet:planet |
| `TriggerAddEventPlanetPanelBirthComplete` | `5DD72CF3` | event | `—` | player:int |
| `TriggerAddEventPlanetPanelCanceled` | `A04EAC0E` | event | `—` | player:int |
| `TriggerAddEventPlanetPanelDeathComplete` | `5738F570` | event | `—` | player:int |
| `TriggerAddEventPlanetPanelReplayPressed` | `46EF10F9` | event | `—` | player:int |
| `TriggerAddEventPlayerAIWave` | `CF629BC0` | event | `—` | p:int |
| `TriggerAddEventPlayerAllianceChange` | `CE6AFC94` | event | `—` | p:int |
| `TriggerAddEventPlayerEffectUsed` | `9FFA06A7` | event | `—` | p:int, effect:gamelink<Effect> |
| `TriggerAddEventPlayerEffectUsedFromScope` | `CD37B8E0` | event | `—` | p:int, scope:catalogscope |
| `TriggerAddEventPlayerJoin` | `057E2485` | event | `—` | p:int |
| `TriggerAddEventPlayerLeft` | `54B13468` | event | `—` | p:int, result:preset |
| `TriggerAddEventPlayerPropChange` | `B83E0A67` | event | `—` | p:int, prop:preset |
| `TriggerAddEventPurchaseExit` | `3F5C4331` | event | `—` | player:int |
| `TriggerAddEventPurchaseMade` | `B1E36454` | event | `—` | player:int, purchaseItem:preset |
| `TriggerAddEventResearchPanelExit` | `9E98A64E` | event | `—` | player:int |
| `TriggerAddEventResearchPanelPurchase` | `6E073E44` | event | `—` | player:int |
| `TriggerAddEventResearchPanelSelectionChanged` | `C3F0EC31` | event | `—` | player:int, researchItem:preset |
| `TriggerAddEventResourceRequest` | `9F7E3DC9` | event | `—` | player:int |
| `TriggerAddEventResourceTrade` | `0DFAE837` | event | `—` | player:int, recipientPlayer:int |
| `TriggerAddEventSaveGame` | `C5D97C07` | event | `—` | — |
| `TriggerAddEventSaveGameDone` | `F488C43D` | event | `—` | — |
| `TriggerAddEventSelectedPurchaseCategoryChanged` | `4555A6F2` | event | `—` | player:int, purchaseCategory:preset |
| `TriggerAddEventSelectedPurchaseCategoryChanged` | `43FD5D89` | event | `—` | player:int, purchaseCategory:preset |
| `TriggerAddEventSelectedPurchaseItemChanged` | `E9556756` | event | `—` | player:int, purchaseItem:preset |
| `TriggerAddEventSelectedPurchaseItemChanged` | `278A6B81` | event | `—` | player:int, purchaseItem:preset |
| `TriggerAddEventTargetModeUpdate` | `098A1488` | event | `—` | player:int, abilityCommand:abilcmd, state:preset |
| `TriggerAddEventTimeElapsed` | `BF7A3439` | event | `—` | dur:fixed, timeType:preset |
| `TriggerAddEventTimePeriodic` | `6D565EB4` | event | `—` | dur:fixed, timeType:preset |
| `TriggerAddEventTimer` | `00000049` | event | `—` | t:timer |
| `TriggerAddEventTriggerSkipped` | `E45431D8` | event | `—` | player:int, trigger:trigger |
| `TriggerAddEventUnitAbility` | `D00F9D6F` | event | `—` | unit:unit, ability:abilcmd, stage:preset, includeSharedAbilities:preset |
| `TriggerAddEventUnitAbilityAutoCastChange` | `791E7DE3` | event | `—` | unit:unit, ability:abilcmd, change:preset, includeSharedAbilities:preset |
| `TriggerAddEventUnitAcquiredTarget` | `20830338` | event | `—` | u:unit |
| `TriggerAddEventUnitArmMagazineProgress` | `8ACFE903` | event | `—` | u:unit, stage:preset |
| `TriggerAddEventUnitAttacked` | `721F018F` | event | `—` | u:unit |
| `TriggerAddEventUnitAttacked2` | `D10A3CBB` | event | `—` | u:unit, weapon:gamelink<Weapon> |
| `TriggerAddEventUnitAttributeChange` | `456ED0A9` | event | `—` | u:unit |
| `TriggerAddEventUnitBecomesIdle` | `44545BCD` | event | `—` | u:unit, idleState:preset |
| `TriggerAddEventUnitBehaviorChange` | `3C0566C4` | event | `—` | unit:unit, behavior:gamelink<Behavior>, type:preset |
| `TriggerAddEventUnitBehaviorChangeFromCategory` | `219341DF` | event | `—` | unit:unit, category:preset, type:preset |
| `TriggerAddEventUnitCargo` | `00000208` | event | `—` | unit:unit, state:preset |
| `TriggerAddEventUnitChangeOwner` | `FF16983A` | event | `—` | u:unit |
| `TriggerAddEventUnitClick` | `00000275` | event | `—` | unit:unit, player:int |
| `TriggerAddEventUnitConstructProgress` | `B0FA20B6` | event | `—` | u:unit, stage:preset |
| `TriggerAddEventUnitCreated` | `18377668` | event | `—` | creator:unit, ability:gamelink<Abil>, behavior:gamelink<Behavior> |
| `TriggerAddEventUnitDamageAbsorbed` | `6D5C96AC` | event | `—` | u:unit, behavior:gamelink<Behavior> |
| `TriggerAddEventUnitDamaged` | `5C010D48` | event | `—` | u:unit, damageType:preset, damageFatalOption:preset, damageEffect:gamelink<Effect> |
| `TriggerAddEventUnitDied` | `00000090` | event | `—` | u:unit |
| `TriggerAddEventUnitGainExperience` | `69D0B7FE` | event | `—` | u:unit |
| `TriggerAddEventUnitGainLevel` | `58A61D51` | event | `—` | u:unit |
| `TriggerAddEventUnitHealed` | `3E814E10` | event | `—` | u:unit, vitalType:preset, healEffect:gamelink<Effect> |
| `TriggerAddEventUnitHighlight` | `00000272` | event | `—` | unit:unit, player:int, state:preset |
| `TriggerAddEventUnitInventoryChange` | `4766099B` | event | `—` | unit:unit, manipulates:preset, item:unit |
| `TriggerAddEventUnitLearnProgress` | `559B4BE2` | event | `—` | u:unit, stage:preset |
| `TriggerAddEventUnitOrder` | `6D29DCBA` | event | `—` | u:unit, command:abilcmd |
| `TriggerAddEventUnitPowerup` | `52B99407` | event | `—` | unit:unit |
| `TriggerAddEventUnitProperty` | `1DE1CB2A` | event | `—` | u:unit, property:preset |
| `TriggerAddEventUnitRange` | `E54B2D20` | event | `—` | u:unit, fromUnit:unit, range:fixed, state:preset |
| `TriggerAddEventUnitRangePoint` | `E267A52A` | event | `—` | u:unit, p:point, distance:fixed, state:preset |
| `TriggerAddEventUnitRegion` | `00000041` | event | `—` | u:unit, r:region, state:preset |
| `TriggerAddEventUnitRemoved` | `3DC1F123` | event | `—` | u:unit |
| `TriggerAddEventUnitResearchProgress` | `D8B5FD69` | event | `—` | u:unit, stage:preset |
| `TriggerAddEventUnitRevive` | `565520E9` | event | `—` | u:unit |
| `TriggerAddEventUnitReviveProgress` | `008A1B94` | event | `—` | u:unit, stage:preset |
| `TriggerAddEventUnitSelected` | `00000222` | event | `—` | unit:unit, player:int, state:preset |
| `TriggerAddEventUnitSpecializeProgress` | `0C94C58C` | event | `—` | u:unit, stage:preset |
| `TriggerAddEventUnitSpendVital` | `2CA8C1EF` | event | `—` | u:unit, vitalType:preset |
| `TriggerAddEventUnitStartedAttack` | `B81FF416` | event | `—` | u:unit |
| `TriggerAddEventUnitStartedAttack2` | `2BC92977` | event | `—` | u:unit, weapon:gamelink<Weapon> |
| `TriggerAddEventUnitTrainProgress` | `82E80323` | event | `—` | u:unit, stage:preset |
| `TriggerAddEventUpgradeLevelChanged` | `1F2B8F70` | event | `—` | p:int |
| `TriggerAddEventVictoryPanelExit` | `827F4805` | event | `—` | player:int |
| `TriggerAddEventVictoryPanelPlayMissionAgain` | `33503427` | event | `—` | player:int |
| `TriggerCreate` | `C63F5A47` | call | `trigger` | functionName:string |
| `TriggerCurrentTriggerThreadSetFlags` | `612A3F70` | action | `—` | flags:preset, t:bool |
| `TriggerDebugEnableType` | `259797B8` | action | `—` | type:preset, enableDisable:preset |
| `TriggerDebugOutput` | `00000118` | action | `—` | type:preset, msg:text, ui:preset |
| `TriggerDebugOutputEnable` | `A9921F0F` | action | `—` | ui:preset |
| `TriggerDebugSetTypeColor` | `0F9CD9A4` | action | `—` | type:preset, color:color |
| `TriggerDebugSetTypeFile` | `FF5B38CA` | action | `—` | type:preset, file:string |
| `TriggerDebugSetTypeFilter` | `59BBA48B` | action | `—` | type:preset, filter:preset, enabled:preset |
| `TriggerDebugSetTypeName` | `56DA3DF0` | action | `—` | type:preset, name:text |
| `TriggerDebugWindowOpen` | `00000117` | action | `—` | open:preset |
| `TriggerDestroy` | `F97DA2B8` | action | `—` | t:trigger |
| `TriggerEnable` | `00000111` | action | `—` | t:trigger, state:preset |
| `TriggerEvaluate` | `00000115` | call | `bool` | t:trigger |
| `TriggerEventParamName` | `1ABFD783` | call | `string` | eventName:string, parameterName:string |
| `TriggerExecute` | `00000116` | action | `—` | t:trigger, check:preset, wait:preset |
| `TriggerExecuteByName` | `D9049991` | action | `—` | t:string, check:preset, wait:preset |
| `TriggerGetCurrent` | `00000217` | call | `trigger` | — |
| `TriggerGetEvalCount` | `00000113` | call | `int` | t:trigger |
| `TriggerGetExecCount` | `00000114` | call | `int` | t:trigger |
| `TriggerGetFunction` | `6E925AFA` | call | `string` | t:trigger |
| `TriggeringProgressAbility` | `0489C434` | call | `gamelink<Abil>` | — |
| `TriggeringProgressEffect` | `00000269` | call | `gamelink<Effect>` | — |
| `TriggeringProgressUnitType` | `00000271` | call | `gamelink<Unit>` | — |
| `TriggeringProgressUpgrade` | `00000270` | call | `gamelink<Upgrade>` | — |
| `TriggerIsEnabled` | `00000112` | call | `bool` | t:trigger |
| `TriggerQueueClear` | `D1E6BE06` | action | `—` | activeOption:preset |
| `TriggerQueueIsEmpty` | `00000342` | call | `bool` | — |
| `TriggerQueuePause` | `FB4C094A` | action | `—` | pause:preset |
| `TriggerSendEvent` | `9B76E7C9` | action | `—` | eventName:string |
| `TriggerSkippableBegin` | `00000410` | action | `—` | players:playergroup, requiredCount:int, onSkip:trigger, check:preset, wait:preset |
| `TriggerStop` | `698FE891` | action | `—` | t:trigger |
| `TriggerWaitForTrigger` | `81F08ADC` | action | `—` | t:trigger, waitUntilDone:preset |
| `Trunc` | `81617BA8` | call | `fixed` | x:fixed |
| `TruncI` | `3D9AC30F` | call | `int` | x:fixed |
| `TurnAllAnimationPropertiesOff` | `35920A8D` | action | `—` | target:actor |
| `TurnAnimationPropertiesOff` | `62BF86AB` | action | `—` | target:actor, prop:modelanim |
| `TurnAnimationPropertiesOn` | `DA979564` | action | `—` | target:actor, prop:modelanim |
| `TurnAnimationPropertiesOnWithBlendInOut` | `A91CB770` | action | `—` | target:actor, prop:modelanim, blendInAnimation:modelanim, blendOutAnimation:modelanim |
