# SC2 Native Functions: U

Columns are documented in [../triggers-native-functions.md](../triggers-native-functions.md). Reference in XML as `<FunctionDef Type="FunctionDef" Library="Ntve" Id="<ID>"/>`.

Parameter defaults in `nativelib` do not auto-apply; emit an explicit `<Parameter Type="Param" Id="..."/>` for every slot in generated `<FunctionCall>` XML.

### U

<a id="u"></a>

| Name | ID | Kind | Returns | Params |
|---|---|---|---|---|
| `UIAlert` | `51718A32` | action | `—` | alertType:gamelink<Alert>, player:int, text:text, icon:filepath |
| `UIAlertClear` | `9B013ED1` | action | `—` | player:int |
| `UIAlertPoint` | `7A544B3D` | action | `—` | alertType:gamelink<Alert>, player:int, text:text, icon:filepath, point:point |
| `UIAlertUnit` | `C97F59B9` | action | `—` | alertType:gamelink<Alert>, player:int, text:text, icon:filepath, unit:unit |
| `UIClearBattleNetButtonOffset` | `1DD795D5` | action | `—` | players:playergroup |
| `UIClearCustomMenuItemList` | `C7B2F062` | action | `—` | players:playergroup |
| `UIClearMessages` | `33E26C4B` | action | `—` | players:playergroup, options:preset |
| `UIDisplayMessage` | `0366EE04` | action | `—` | players:playergroup, messageArea:preset, message:text |
| `UIErrorMessage` | `EDB526A6` | action | `—` | players:playergroup, message:text, sound:soundlink |
| `UIFlyerHelperClearOverride` | `8140F183` | action | `—` | players:playergroup |
| `UIFlyerHelperOverride` | `8D70E663` | action | `—` | players:playergroup, display:preset |
| `UIFrameFlagCheck` | `A00A9586` | call | `bool` | uIFrame:preset, flag:preset |
| `UIFrameVisible` | `D155BA6B` | call | `bool` | player:int, uIFrame:preset |
| `UIGetChallengeHighScore` | `DA6CA19C` | call | `int` | player:int, challengeName:string |
| `UIHideCinematicText` | `0667D7EF` | action | `—` | players:playergroup |
| `UIHideTextCrawl` | `2DFC944D` | action | `—` | players:playergroup |
| `UIHotKeyString` | `38D03E80` | call | `text` | hotKey:preset, count:int, abbreviate:bool, addTags:bool |
| `UILaunchNydusLink` | `9DD138E1` | action | `—` | playerGroup:playergroup, nydusLink:preset |
| `UIMessageLogPanelSetVisible` | `AB1E1024` | action | `—` | playerGroup:playergroup, showHide:preset |
| `UISetAchievementToastStyle` | `DD650E92` | action | `—` | players:playergroup, style:preset |
| `UISetAlertTypeVisible` | `D18723EA` | action | `—` | playerGroup:playergroup, alert:gamelink<Alert>, showHide:preset |
| `UISetBattleNetButtonOffset` | `7937AECA` | action | `—` | players:playergroup, offsetX:int, show:int |
| `UISetButtonFaceHighlighted` | `5967E3C2` | action | `—` | players:playergroup, button:gamelink<Button>, highlighted:preset |
| `UISetButtonHighlighted` | `EA56A214` | action | `—` | players:playergroup, command:abilcmd, highlighted:preset |
| `UISetChallengeCompleted` | `30C9D8A9` | action | `—` | playerGroup:playergroup, challengeName:string, completed:bool |
| `UISetChallengeHighScore` | `0020B4C0` | action | `—` | playerGroup:playergroup, challengeName:string, highScore:int |
| `UISetChallengeMode` | `C58C84B5` | action | `—` | players:playergroup, onOff:preset |
| `UISetChallengeScoreText` | `8993E4EE` | action | `—` | playerGroup:playergroup, challenge:string, text:text |
| `UISetCommandAllowed` | `06D19175` | action | `—` | playerGroup:playergroup, commandOption:preset, disable:preset |
| `UISetCommandDisallowedMessage` | `7CD40442` | action | `—` | playerGroup:playergroup, textMessage:text |
| `UISetCursorAutoHide` | `8D181A5F` | action | `—` | players:playergroup, enableDisable:preset, delay:fixed |
| `UISetCursorVisible` | `4333673D` | action | `—` | players:playergroup, showHideState:preset |
| `UISetCustomMenuItemShortcut` | `9A2F6C43` | action | `—` | players:playergroup, menuItem:preset, shortcut:text |
| `UISetCustomMenuItemText` | `D1448757` | action | `—` | players:playergroup, menuItem:preset, show:text |
| `UISetCustomMenuItemVisible` | `A3607EC8` | action | `—` | players:playergroup, menuItem:preset, show:preset |
| `UISetDragSelectEnabled` | `8C4DB610` | action | `—` | players:playergroup, enableDisable:preset |
| `UISetFrameVisible` | `AE5AF605` | action | `—` | players:playergroup, uIFrame:preset, show:preset |
| `UISetGameMenuItemShortcut` | `AE579C3B` | action | `—` | players:playergroup, menuItem:preset, show:text |
| `UISetGameMenuItemText` | `9C868B9D` | action | `—` | players:playergroup, menuItem:preset, show:text |
| `UISetGameMenuItemVisible` | `52711D8B` | action | `—` | players:playergroup, menuItem:preset, show:preset |
| `UISetHotkeyAllowed` | `EF83FDD4` | action | `—` | playerGroup:playergroup, hotkey:preset, disable:preset |
| `UISetHotkeyProfile` | `4AF8B1C6` | action | `—` | players:playergroup, profileName:string |
| `UISetMiniMapBackGroundColor` | `4DCDD7B7` | action | `—` | color:color |
| `UISetMiniMapBounds` | `DA96E713` | action | `—` | players:playergroup, bounds:region |
| `UISetMiniMapCameraFoVVisible` | `C9B85BF3` | action | `—` | showHide:preset |
| `UISetMinimumLetterboxHeight` | `951D3123` | action | `—` | height:int |
| `UISetMode` | `8EDD3557` | action | `—` | players:playergroup, mode:preset, duration:fixed |
| `UISetNextLoadingScreen` | `5954876C` | action | `—` | image:filepath, title:text, subtitle:text, body:text, help:text, waitForInput:bool |
| `UISetNextLoadingScreenImageScale` | `5C7238A8` | action | `—` | scale:preset |
| `UISetNextLoadingScreenTextPosition` | `35E95E4D` | action | `—` | anchor:preset, offsetX:int, offsetY:int, width:int, height:int |
| `UISetResourceTradeCountdownTime` | `6BEEB011` | action | `—` | countdownTime:int |
| `UISetResourceTradingAllowed` | `9B63D84D` | action | `—` | resourceType:preset, allow:preset |
| `UISetResourceTradingMajorStep` | `FD1B01FD` | action | `—` | resourceType:preset, amount:int |
| `UISetResourceTradingMinorStep` | `C96CAF2B` | action | `—` | resourceType:preset, amount:int |
| `UISetResourceVisible` | `02F55C7B` | action | `—` | playerGroup:playergroup, resourceType:preset, showHide:preset |
| `UISetRestartLoadingScreen` | `10C8F1C7` | action | `—` | help:text |
| `UISetSelectionTypeEnabled` | `7161E16B` | action | `—` | playerGroup:playergroup, selectionType:preset, disable:preset |
| `UISetTargetingOrder` | `0B3D8934` | action | `—` | playerGroup:playergroup, unitGroup:unitgroup, order:order, sticky:preset |
| `UISetWorldVisible` | `30ACF7AC` | action | `—` | players:playergroup, isVisible:preset |
| `UIShowCinematicText` | `D3A3FDC0` | action | `—` | players:playergroup, text:text, timeBetweenCharacters:fixed, maxTime:fixed, sound:soundlink |
| `UIShowCustomDialog` | `8DF4D23C` | action | `—` | players:playergroup, type:preset, title:text, text:text, pause:preset |
| `UIShowCustomMenu` | `4A7F9FFE` | action | `—` | players:playergroup, show:text |
| `UIShowStandardMenu` | `F84760A1` | action | `—` | players:playergroup |
| `UIShowTextCrawl` | `CCA8EC70` | action | `—` | players:playergroup, title:text, text:text, maxTime:fixed, birthSound:soundlink, typeSound:soundlink |
| `UIStatusBarClearOverride` | `94C0627E` | action | `—` | players:playergroup |
| `UIStatusBarOverride` | `2ADAFD5D` | action | `—` | players:playergroup, display:preset |
| `UIUnitColorStyleClearOverride` | `00000421` | action | `—` | players:playergroup |
| `UIUnitColorStyleOverride` | `00000420` | action | `—` | players:playergroup, style:preset |
| `UnionOfPlayerGroups` | `9E6A3A6C` | call | `playergroup` | groupA:playergroup, groupB:playergroup |
| `UnitAbilityAdd` | `A03D3C7F` | action | `—` | inUnit:unit, inBehavior:gamelink<Abil> |
| `UnitAbilityAddChargeRegen` | `93C52D6B` | action | `—` | inUnit:unit, inAbil:gamelink<Abil>, inCharge:charge, inVal:fixed |
| `UnitAbilityAddChargeRegenFull` | `6B3B71B3` | action | `—` | inUnit:unit, inAbil:gamelink<Abil>, inCharge:charge, inVal:fixed |
| `UnitAbilityAddChargeRegenRemaining` | `44459AA8` | action | `—` | inUnit:unit, inAbil:gamelink<Abil>, inCharge:charge, inVal:fixed |
| `UnitAbilityAddChargeUsed` | `F14B3F69` | action | `—` | inUnit:unit, inAbil:gamelink<Abil>, inCharge:charge, inVal:fixed |
| `UnitAbilityAddCooldown` | `25B3A05C` | action | `—` | inUnit:unit, inAbil:gamelink<Abil>, inCooldown:cooldown, inVal:fixed |
| `UnitAbilityByFilters` | `0F67DB9A` | call | `gamelink<Abil>` | unit:unit, abilityClass:preset, alias:string |
| `UnitAbilityChangeCardId` | `EC88F295` | action | `—` | unit:unit, ability:gamelink<Abil>, submenuCardId:string |
| `UnitAbilityChangeLevel` | `CCD3C6A0` | action | `—` | unit:unit, ability:gamelink<Abil>, level:int |
| `UnitAbilityChangeLink` | `2A75E8AF` | action | `—` | unit:unit, ability:gamelink<Abil>, newAbility:gamelink<Abil> |
| `UnitAbilityChargeInfo` | `3AA645B4` | call | `fixed` | unit:unit, abilityCommand:abilcmd, type:preset |
| `UnitAbilityCheck` | `00000154` | call | `bool` | u:unit, abil:gamelink<Abil>, enabled:preset |
| `UnitAbilityCount` | `00000384` | call | `int` | unit:unit |
| `UnitAbilityEnable` | `00000152` | action | `—` | u:unit, abil:gamelink<Abil>, enable:preset |
| `UnitAbilityExists` | `00000153` | call | `bool` | u:unit, abil:gamelink<Abil> |
| `UnitAbilityGet` | `00000385` | call | `gamelink<Abil>` | unit:unit, index:int |
| `UnitAbilityGetByType` | `5F3777F3` | call | `gamelink<Abil>` | unit:unit, abilityClass:preset, index:int |
| `UnitAbilityGetCardId` | `877C42EE` | call | `string` | unit:unit, ability:gamelink<Abil> |
| `UnitAbilityGetChargeRegen` | `AD5CD155` | call | `fixed` | inUnit:unit, inAbil:gamelink<Abil>, inCharge:charge |
| `UnitAbilityGetChargeRegenFull` | `E1FF2E2B` | call | `fixed` | inUnit:unit, inAbil:gamelink<Abil>, inCharge:charge, JustDelta:bool |
| `UnitAbilityGetChargeUsed` | `0DCB7E2E` | call | `fixed` | inUnit:unit, inAbil:gamelink<Abil>, inCharge:charge |
| `UnitAbilityGetCooldown` | `56B8B8AF` | call | `fixed` | inUnit:unit, inAbil:gamelink<Abil>, inCooldown:cooldown |
| `UnitAbilityGetLevel` | `0D7D74B4` | call | `int` | unit:unit, ability:gamelink<Abil> |
| `UnitAbilityMaxLevel` | `45E6592C` | call | `int` | unit:unit, ability:gamelink<Abil> |
| `UnitAbilityRemove` | `F7CE0B02` | action | `—` | inUnit:unit, inBehavior:gamelink<Abil> |
| `UnitAbilityRemoveChargeRegen` | `9C41471B` | action | `—` | inUnit:unit, inAbil:gamelink<Abil>, inCharge:charge |
| `UnitAbilityRemoveChargeUsed` | `A72F9A7B` | action | `—` | inUnit:unit, inAbil:gamelink<Abil>, inCharge:charge |
| `UnitAbilityRemoveCooldown` | `DC4D3C51` | action | `—` | inUnit:unit, inAbil:gamelink<Abil>, inCooldown:cooldown |
| `UnitAbilityReset` | `2CFDDDB6` | action | `—` | u:unit, abilityCommand:abilcmd, spendLocation:preset |
| `UnitAbilityShow` | `B5CB5FC8` | action | `—` | u:unit, abil:gamelink<Abil>, show:preset |
| `UnitAbilitySpend` | `C57F2702` | action | `—` | u:unit, abilityCommand:abilcmd, spendLocation:preset |
| `UnitAbilitySpendExplicit` | `6D567C7E` | action | `—` | u:unit, abilityCommand:abilcmd, spendLocation:preset, vitalsFactor:fixed, resourcesFactor:fixed, chargesFactor:fixed, cooldownFactor:fixed |
| `UnitAbilOrderStateFlags` | `AB9FF2DE` | call | `int` | unit:unit, abilityCommand:order |
| `UnitAddChargeRegen` | `4FEC2802` | action | `—` | inUnit:unit, inCharge:charge, inVal:fixed |
| `UnitAddChargeRegenFull` | `3EE9F19D` | action | `—` | inUnit:unit, inCharge:charge, inVal:fixed |
| `UnitAddChargeRegenRemaining` | `417209E7` | action | `—` | inUnit:unit, inCharge:charge, inVal:fixed |
| `UnitAddChargeUsed` | `F1200B76` | action | `—` | inUnit:unit, inCharge:charge, inVal:fixed |
| `UnitAddCooldown` | `6111C017` | action | `—` | inUnit:unit, inCooldown:cooldown, inVal:fixed |
| `UnitAddOnChild` | `E9D2B243` | call | `unit` | parent:unit, index:int |
| `UnitAddOnParent` | `2F7FDD5C` | call | `unit` | child:unit |
| `UnitAgent` | `4B2AE007` | call | `unit` | unit:unit, player:int |
| `UnitBehaviorAdd` | `C47C0524` | action | `—` | inUnit:unit, inBehavior:gamelink<Behavior>, inCaster:unit, inCount:int |
| `UnitBehaviorAddChargeRegen` | `1524735E` | action | `—` | inUnit:unit, inBehavior:gamelink<Behavior>, inCharge:charge, inVal:fixed |
| `UnitBehaviorAddChargeRegenFull` | `A84DED9E` | action | `—` | inUnit:unit, inBehavior:gamelink<Behavior>, inCharge:charge, inVal:fixed |
| `UnitBehaviorAddChargeRegenRemaining` | `2E734680` | action | `—` | inUnit:unit, inBehavior:gamelink<Behavior>, inCharge:charge, inVal:fixed |
| `UnitBehaviorAddChargeUsed` | `887CD3DA` | action | `—` | inUnit:unit, inBehavior:gamelink<Behavior>, inCharge:charge, inVal:fixed |
| `UnitBehaviorAddCooldown` | `669DD68A` | action | `—` | inUnit:unit, inBehavior:gamelink<Behavior>, inCooldown:cooldown, inVal:fixed |
| `UnitBehaviorAddPlayer` | `CB774E72` | action | `—` | inUnit:unit, inBehavior:gamelink<Behavior>, player:int, inCount:int |
| `UnitBehaviorCount` | `00000386` | call | `int` | unit:unit, behavior:gamelink<Behavior> |
| `UnitBehaviorCountAll` | `2560791C` | call | `int` | unit:unit |
| `UnitBehaviorDamageModifyLimit` | `D507B76C` | call | `fixed` | Unit:unit, Behavior:gamelink<Behavior> |
| `UnitBehaviorDamageModifyRemaining` | `0307583A` | call | `fixed` | Unit:unit, Behavior:gamelink<Behavior> |
| `UnitBehaviorDuration` | `09C6C463` | call | `fixed` | unit:unit, behavior:gamelink<Behavior> |
| `UnitBehaviorDurationTotal` | `576B4EA1` | call | `fixed` | unit:unit, behavior:gamelink<Behavior> |
| `UnitBehaviorEffectPlayer` | `3034D381` | call | `int` | unit:unit, behavior:gamelink<Behavior>, player:preset, stackIndex:int |
| `UnitBehaviorEffectTreeSetUserData` | `11DBA81B` | action | `—` | unit:unit, behavior:gamelink<Behavior>, userData:string, value:fixed |
| `UnitBehaviorEffectTreeUserData` | `F65E1732` | call | `fixed` | unit:unit, behavior:gamelink<Behavior>, userData:string |
| `UnitBehaviorEffectTreeUserDataExists` | `898C5A5D` | call | `bool` | unit:unit, behavior:gamelink<Behavior>, userData:string |
| `UnitBehaviorEffectUnit` | `AB47D73B` | call | `unit` | unit:unit, behavior:gamelink<Behavior>, location:preset, stackIndex:int |
| `UnitBehaviorEnabled` | `6C8E411D` | call | `bool` | unit:unit, behavior:gamelink<Behavior> |
| `UnitBehaviorGet` | `00000387` | call | `gamelink<Behavior>` | unit:unit, index:int |
| `UnitBehaviorGetChargeRegen` | `9C98BAC1` | call | `fixed` | inUnit:unit, inBehavior:gamelink<Behavior>, inCharge:charge |
| `UnitBehaviorGetChargeRegenFull` | `49540656` | call | `fixed` | inUnit:unit, inBehavior:gamelink<Behavior>, inCharge:charge, JustDelta:bool |
| `UnitBehaviorGetChargeUsed` | `FC7979E5` | call | `fixed` | inUnit:unit, inBehavior:gamelink<Behavior>, inCharge:charge |
| `UnitBehaviorGetCooldown` | `21D894B0` | call | `fixed` | inUnit:unit, inBehavior:gamelink<Behavior>, inCooldown:cooldown |
| `UnitBehaviorHasFlag` | `222E921E` | call | `bool` | behavior:gamelink<Behavior>, flag:preset |
| `UnitBehaviorRemove` | `09840835` | action | `—` | inUnit:unit, inBehavior:gamelink<Behavior>, inCount:int |
| `UnitBehaviorRemoveCategory` | `47D6D6BB` | action | `—` | inUnit:unit, category:preset |
| `UnitBehaviorRemoveChargeRegen` | `B20BC13F` | action | `—` | inUnit:unit, inBehavior:gamelink<Behavior>, inCharge:charge |
| `UnitBehaviorRemoveChargeUsed` | `4123C5CC` | action | `—` | inUnit:unit, inBehavior:gamelink<Behavior>, inCharge:charge |
| `UnitBehaviorRemoveCooldown` | `979E6CCF` | action | `—` | inUnit:unit, inBehavior:gamelink<Behavior>, inCooldown:cooldown |
| `UnitBehaviorRemovePlayer` | `25B39578` | action | `—` | inUnit:unit, inBehavior:gamelink<Behavior>, inPlayer:int, inCount:int |
| `UnitBehaviorSetDuration` | `5D218339` | action | `—` | unit:unit, behavior:gamelink<Behavior>, duration:fixed |
| `UnitBehaviorSetDurationRemaining` | `0A1BADFB` | action | `—` | unit:unit, behavior:gamelink<Behavior>, durationRemaining:fixed |
| `UnitBehaviorSpawn` | `83BEEF42` | action | `—` | unit:unit, behavior:gamelink<Behavior>, count:int |
| `UnitBehaviorTransfer` | `00000258` | action | `—` | inSource:unit, inDest:unit, inBehavior:gamelink<Behavior>, inCount:int |
| `UnitCanAttackTarget` | `2263B76C` | call | `bool` | u:unit, s:unit |
| `UnitCanAttackUnit` | `40828170` | call | `bool` | u:unit, s:unit |
| `UnitCanCreateEffectAtPoint` | `28CBC59D` | call | `bool` | caster:unit, effect:gamelink<Effect>, point:point |
| `UnitCanCreateEffectOnUnit` | `5EC4874D` | call | `bool` | caster:unit, effect:gamelink<Effect>, target:unit |
| `UnitCargo` | `00000230` | call | `unit` | inUnit:unit, inIndex:int |
| `UnitCargoCreate` | `0C7C13FA` | action | `—` | inUnit:unit, inId:gamelink<Unit>, inCount:int |
| `UnitCargoGroup` | `00000233` | call | `unitgroup` | inUnit:unit |
| `UnitCargoLastCreated` | `FEEC5BBE` | call | `unit` | — |
| `UnitCargoLastCreatedGroup` | `D2239866` | call | `unitgroup` | — |
| `UnitCargoValue` | `0E513B33` | call | `int` | inUnit:unit, valueType:preset |
| `UnitCheckAbilCmdState` | `F8758140` | call | `bool` | unit:unit, abilityCommand:abilcmd, state:preset |
| `UnitCheckProgressState` | `1D771D8A` | call | `bool` | unit:unit, slot:int, state:preset |
| `UnitClearCooldowns` | `4032C693` | action | `—` | unit:unit, reset:preset |
| `UnitClearInfoButtonTooltip` | `7D13FE06` | action | `—` | unit:unit, key:string |
| `UnitClearInfoText` | `F116F8F1` | action | `—` | unit:unit |
| `UnitClearSelection` | `00000176` | action | `—` | player:int |
| `UnitConjoinedGroup` | `652106DC` | call | `unitgroup` | inUnit:unit, inConjoinedBehavior:gamelink<Behavior> |
| `UnitControlGroup` | `74AEC2C4` | call | `unitgroup` | player:int, controlGroup:int |
| `UnitControlGroupAddUnit` | `AB3BC844` | action | `—` | player:int, controlGroup:int, unit:unit |
| `UnitControlGroupAddUnits` | `067344D2` | action | `—` | player:int, controlGroup:int, unitGroup:unitgroup |
| `UnitControlGroupClear` | `164B2FD7` | action | `—` | player:int, controlGroup:int |
| `UnitControlGroupRemoveUnit` | `8F5E4BCA` | action | `—` | player:int, controlGroup:int, unit:unit |
| `UnitControlGroupRemoveUnits` | `A848A5CD` | action | `—` | player:int, controlGroup:int, unitGroup:unitgroup |
| `UnitCount` | `64952742` | call | `int` | type:gamelink<Unit>, player:int, reg:region, unitFilter:unitfilter, count:int |
| `UnitCountAlliance` | `360DF94F` | call | `int` | player:int, alliance:preset, reg:region, unitFilter:unitfilter, count:int |
| `UnitCreate` | `6C39A0DF` | action | `—` | count:int, type:gamelink<Unit>, flags:preset, player:int, pos:point, angle:fixed |
| `UnitCreateEffectPoint` | `6263AB61` | action | `—` | caster:unit, effect:gamelink<Effect>, point:point |
| `UnitCreateEffectUnit` | `73C0339B` | action | `—` | caster:unit, effect:gamelink<Effect>, unit:unit |
| `UnitCreateFacingPoint` | `C835E90F` | action | `—` | count:int, type:gamelink<Unit>, flags:preset, player:int, pos:point, facing:point |
| `UnitCurrentWorkerCount` | `0350F5A4` | call | `int` | Unit:unit |
| `UnitDamage` | `CC9F56A7` | action | `—` | attacker:unit, effect:gamelink<Effect>, victim:unit, bonus:fixed |
| `UnitEffectHistory` | `F00486D5` | call | `effecthistory` | unit:unit, maxCount:int |
| `UnitEventSetNullVariableInvalid` | `4F04D443` | action | `—` | option:preset |
| `UnitFilterGetState` | `00000358` | call | `preset` | filter:unitfilter, type:preset |
| `UnitFilterMatch` | `390C5C49` | call | `bool` | inUnit:unit, inPlayer:int, inFilter:unitfilter |
| `UnitFilterSetState` | `00000357` | action | `—` | filter:unitfilter, type:preset, state:preset |
| `UnitFlashSelection` | `47EA2E7C` | action | `—` | unit:unit, period:fixed |
| `UnitForceStatusBar` | `6D097F01` | action | `—` | unit:unit, value:preset |
| `UnitGetAIOption` | `B2EE2FE1` | call | `bool` | u:unit, option:preset |
| `UnitGetAttachmentPoint` | `E00E7137` | call | `point` | u:unit, attachment:string |
| `UnitGetAttributePoint` | `F0E3F78B` | call | `int` | unit:unit, attribute:gamelink<Behavior>, baseBonus:preset |
| `UnitGetChargeRegen` | `C03FF78B` | call | `fixed` | inUnit:unit, inCharge:charge |
| `UnitGetChargeRegenFull` | `021AED7B` | call | `fixed` | inUnit:unit, inCharge:charge, JustDelta:bool |
| `UnitGetChargeUsed` | `CC1B5055` | call | `fixed` | inUnit:unit, inCharge:charge |
| `UnitGetCooldown` | `EB622569` | call | `fixed` | inUnit:unit, inCooldown:cooldown |
| `UnitGetCustomValue` | `82D826FA` | call | `fixed` | u:unit, index:int |
| `UnitGetDamageDealtTime` | `4CE7F001` | call | `fixed` | unit:unit |
| `UnitGetDamageTakenTime` | `5E68F70D` | call | `fixed` | unit:unit |
| `UnitGetFacing` | `00000085` | call | `fixed` | u:unit |
| `UnitGetGoalPosition` | `F4E5D65D` | call | `point` | u:unit |
| `UnitGetHeight` | `B9B1D01B` | call | `fixed` | u:unit |
| `UnitGetMagazine` | `E8D283F8` | call | `unit` | ammoUnit:unit |
| `UnitGetName` | `FF29FC7A` | call | `text` | unit:unit |
| `UnitGetOriginalCaster` | `E62014FA` | call | `unit` | inUnit:unit |
| `UnitGetOriginalEffect` | `7BB77F9D` | call | `gamelink<Effect>` | inUnit:unit |
| `UnitGetOwner` | `00000081` | call | `int` | u:unit |
| `UnitGetPosition` | `00000083` | call | `point` | u:unit |
| `UnitGetProgressComplete` | `A05A9417` | call | `fixed` | unit:unit, slot:int |
| `UnitGetPropertyFixed` | `C65CC121` | call | `fixed` | u:unit, prop:preset, current:preset |
| `UnitGetPropertyInt` | `15E6A048` | call | `int` | u:unit, prop:preset, current:preset |
| `UnitGetPropertyKills` | `6D10EF52` | call | `int` | u:unit, current:preset |
| `UnitGetPropertyResources` | `05917C7C` | call | `int` | u:unit, current:preset |
| `UnitGetSeed` | `76815403` | call | `int` | u:unit |
| `UnitGetTag` | `AF2CDB5E` | call | `int` | u:unit |
| `UnitGetTrackedUnitGroup` | `6C135AD4` | call | `unitgroup` | inUnit:unit, inConjoinedBehavior:gamelink<Behavior> |
| `UnitGetType` | `00000079` | call | `gamelink<Unit>` | u:unit |
| `UnitGroup` | `00000359` | call | `unitgroup` | type:gamelink<Unit>, player:int, reg:region, unitFilter:unitfilter, count:int |
| `UnitGroupAdd` | `9435D821` | action | `—` | g:unitgroup, u:unit |
| `UnitGroupAddUnitGroup` | `A8732F20` | action | `—` | targetUnitGroup:unitgroup, sourceUnitGroup:unitgroup |
| `UnitGroupAlliance` | `00D4EFCE` | call | `unitgroup` | player:int, alliance:preset, reg:region, unitFilter:unitfilter, count:int |
| `UnitGroupCenterOfGroup` | `F5D30562` | call | `point` | unitGroup:unitgroup |
| `UnitGroupClear` | `00000106` | action | `—` | g:unitgroup |
| `UnitGroupClosestToPoint` | `BC830FBE` | call | `unit` | unitGroup:unitgroup, point:point |
| `UnitGroupCopy` | `00000212` | call | `unitgroup` | group:unitgroup |
| `UnitGroupCount` | `83B4BF45` | call | `int` | g:unitgroup, type:preset |
| `UnitGroupEmpty` | `00000104` | call | `unitgroup` | — |
| `UnitGroupFilter` | `D75553FB` | call | `unitgroup` | type:gamelink<Unit>, player:int, group:unitgroup, unitFilter:unitfilter, count:int |
| `UnitGroupFilterAlliance` | `3AE5AFF3` | call | `unitgroup` | group:unitgroup, player:int, alliance:preset, count:int |
| `UnitGroupFilterPlane` | `E99BA742` | call | `unitgroup` | group:unitgroup, plane:preset, count:int |
| `UnitGroupFilterPlayer` | `8B300062` | call | `unitgroup` | group:unitgroup, player:int, count:int |
| `UnitGroupFilterRegion` | `270BC04D` | call | `unitgroup` | group:unitgroup, region:region, count:int |
| `UnitGroupHasUnit` | `00000110` | call | `bool` | g:unitgroup, u:unit |
| `UnitGroupIdle` | `D3EAB07E` | call | `unitgroup` | player:int, workersOnly:preset |
| `UnitGroupIsDead` | `0D42CF15` | call | `bool` | units:unitgroup |
| `UnitGroupIssueOrder` | `00000108` | action | `—` | g:unitgroup, o:order, queue:preset |
| `UnitGroupLoopCurrent` | `19CE733E` | call | `unit` | — |
| `UnitGroupLoopCurrentDeprecated` | `61C49CC4` | call | `unit` | — |
| `UnitGroupPauseAll` | `3A465076` | action | `—` | g:unitgroup, pause:preset |
| `UnitGroupRandomUnit` | `B91E7832` | call | `unit` | g:unitgroup, type:preset |
| `UnitGroupRemove` | `90CBEC01` | action | `—` | g:unitgroup, u:unit |
| `UnitGroupRemoveUnitGroup` | `EF4E46C6` | action | `—` | targetUnitGroup:unitgroup, sourceUnitGroup:unitgroup |
| `UnitGroupSearch` | `403AA0FB` | call | `unitgroup` | type:gamelink<Unit>, player:int, reg:point, radius:fixed, unitFilter:unitfilter, count:int |
| `UnitGroupSelect` | `00000178` | action | `—` | group:unitgroup, player:int, select:preset |
| `UnitGroupSelected` | `00000179` | call | `unitgroup` | player:int |
| `UnitGroupUnit` | `00000213` | call | `unit` | g:unitgroup, i:int |
| `UnitGroupWaitUntilIdle` | `04955B8F` | action | `—` | group:unitgroup, count:int, idle:preset |
| `UnitHasBehavior` | `ABD41ECF` | call | `bool` | unit:unit, behavior:gamelink<Behavior> |
| `UnitHasBehavior2` | `142FF15A` | call | `bool` | unit:unit, behavior:gamelink<Behavior> |
| `UnitIdealWorkerCount` | `55BC29B4` | call | `int` | Unit:unit |
| `UnitInRangeAndAbleToAttackTarget` | `C191F300` | call | `bool` | u:unit, s:unit |
| `UnitInRegion` | `22E8E351` | call | `bool` | u:unit, regioin:region |
| `UnitInventoryAdd` | `38D634C5` | action | `—` | u:unit, item:unit |
| `UnitInventoryContainer` | `1BC52DDD` | call | `int` | item:unit |
| `UnitInventoryContainerOpen` | `B2ADB754` | action | `—` | players:playergroup, unit:unit, container:int, open:preset |
| `UnitInventoryCount` | `B4F0E8F8` | call | `int` | unit:unit, countType:preset |
| `UnitInventoryCreate` | `544A98EF` | action | `—` | u:unit, itemType:gamelink<Unit> |
| `UnitInventoryGroup` | `B7CC6780` | call | `unitgroup` | unit:unit |
| `UnitInventoryIndex` | `54051DA3` | call | `int` | item:unit |
| `UnitInventoryItem` | `B4BEBD9E` | call | `unit` | unit:unit, index:int |
| `UnitInventoryLastCreated` | `075C97E3` | call | `unit` | — |
| `UnitInventoryMove` | `A4FBCE8E` | action | `—` | item:unit, container:int, slot:int |
| `UnitInventoryRemove` | `221348C5` | action | `—` | item:unit |
| `UnitInventorySlot` | `DF56EA04` | call | `int` | item:unit |
| `UnitInventoryUnit` | `F2BC8E79` | call | `unit` | item:unit |
| `UnitIsAlive` | `00000216` | call | `bool` | u:unit |
| `UnitIsHidden` | `49A95989` | call | `bool` | u:unit |
| `UnitIsInsidePlayerTransport` | `348CCDBA` | call | `bool` | u:unit |
| `UnitIsInsideTransport` | `0D7C0352` | call | `bool` | u:unit |
| `UnitIsInsideUnitTransport` | `F512F82A` | call | `bool` | u:unit |
| `UnitIsInvulnerable` | `EE7AB1E8` | call | `bool` | u:unit |
| `UnitIsPaused` | `8518EA3D` | call | `bool` | u:unit |
| `UnitIsSelected` | `00000177` | call | `bool` | unit:unit, player:int |
| `UnitIsSleepiing` | `F68639E0` | call | `bool` | u:unit |
| `UnitIssueOrder` | `00000089` | action | `—` | u:unit, ord:order, queue:preset |
| `UnitIsUnderConstruction` | `264BD339` | call | `bool` | u:unit |
| `UnitIsValid` | `1A05F1CA` | call | `bool` | u:unit |
| `UnitIsVisibleToPlayer` | `007DF42C` | call | `bool` | unit:unit, player:int |
| `UnitKill` | `00000077` | action | `—` | u:unit |
| `UnitLastCreated` | `00000076` | call | `unit` | — |
| `UnitLastCreatedGroup` | `00000141` | call | `unitgroup` | — |
| `UnitLearnAbilAddLevel` | `C12B1578` | action | `—` | unit:unit, learnAbility:gamelink<Abil>, index:int, level:int |
| `UnitLearnAbilAddPoints` | `A951B49E` | action | `—` | unit:unit, learnAbility:gamelink<Abil>, points:int |
| `UnitLearnAbilGetLevel` | `B6FCFE39` | call | `int` | unit:unit, learnAbility:gamelink<Abil>, index:int |
| `UnitLearnAbilGetPoints` | `B01E0F60` | call | `int` | unit:unit, learnAbility:gamelink<Abil>, currentTotal:preset |
| `UnitLearnAbilResetLevel` | `6D48FFE8` | action | `—` | unit:unit, learnAbility:gamelink<Abil>, index:int |
| `UnitLevel` | `00000352` | call | `int` | unit:unit |
| `UnitLoadModel` | `03DF54FB` | action | `—` | u:unit |
| `UnitLootDropPoint` | `7F1015EA` | action | `—` | dropPlayer:int, dropLocation:point, loot:gamelink<Loot>, killerPlayer:int |
| `UnitLootDropUnit` | `25EE7E07` | action | `—` | dropUnit:unit, loot:gamelink<Loot>, killerPlayer:int |
| `UnitLootLastCreated` | `EB9B0F45` | call | `unit` | — |
| `UnitLootLastCreatedGroup` | `83133F60` | call | `unitgroup` | — |
| `UnitMagazineArm` | `9DBAA1BE` | action | `—` | u:unit, abilcmd:abilcmd, count:int |
| `UnitMagazineCount` | `00000211` | call | `int` | u:unit, abil:gamelink<Abil> |
| `UnitMagazineLastCreated` | `10A82307` | call | `unit` | — |
| `UnitMagazineLastCreatedGroup` | `5E302B9D` | call | `unitgroup` | — |
| `UnitModifyCooldown` | `5ADEFF8E` | action | `—` | inUnit:unit, inCooldown:cooldown, inVal:fixed, inCooldownOperation:preset |
| `UnitMoverExists` | `00000149` | call | `bool` | u:unit, mover:gamelink<Mover> |
| `UnitMoverExists` | `E90538F1` | call | `bool` | unitType:gamelink<Unit>, mover:gamelink<Mover> |
| `UnitObjectGroupCallForHelp` | `D6D8F1FD` | action | `—` | unit:unit, attacker:unit |
| `UnitObjectGroupFromUnitGroup` | `B4C6E2F1` | call | `int` | group:unitgroup, groupLevel:int |
| `UnitOrder` | `1C5B0649` | call | `order` | unit:unit, index:int |
| `UnitOrderCount` | `CD2C7578` | call | `int` | unit:unit |
| `UnitOrderGetProgress` | `7E8105DE` | call | `fixed` | unit:unit |
| `UnitOrderHasAbil` | `FD4B3BB0` | call | `bool` | unit:unit, ability:gamelink<Abil> |
| `UnitOrderIsAcquired` | `4BF769E7` | call | `bool` | unit:unit, index:int |
| `UnitOrderIsValid` | `29AFAB1F` | call | `bool` | unit:unit, order:order |
| `UnitPathableToPoint` | `F2DE967D` | call | `bool` | unit:unit, target:point, range:fixed, maxDistance:fixed |
| `UnitPathableToUnit` | `6CE05436` | call | `bool` | unit:unit, target:unit, range:fixed, maxDistance:fixed |
| `UnitPauseAll` | `00000388` | action | `—` | pause:preset |
| `UnitPutInTransport` | `C67162AE` | action | `—` | inUnit:unit, inTransport:unit |
| `UnitQueueGetProperty` | `44C0972D` | call | `int` | unit:unit, property:preset |
| `UnitQueueItemCount` | `00000398` | call | `int` | unit:unit, slot:int |
| `UnitQueueItemGet` | `A813DBCB` | call | `gamelink` | unit:unit, slot:int, item:int |
| `UnitQueueItemTime` | `0130ACAD` | call | `fixed` | unit:unit, timeType:preset, slot:int |
| `UnitQueueItemTypeCheck` | `00000402` | call | `bool` | unit:unit, slot:int, type:preset |
| `UnitRallyPoint` | `41F9E226` | call | `int` | unit:unit, user:unit |
| `UnitRallyPointCount` | `F4ED4CD8` | call | `int` | unit:unit |
| `UnitRallyPointTargetCount` | `8AD76FFF` | call | `int` | unit:unit, point:int |
| `UnitRallyPointTargetPoint` | `3411EE1A` | call | `point` | unit:unit, point:int, target:int |
| `UnitRallyPointTargetUnit` | `E4BD0151` | call | `unit` | unit:unit, point:int, target:int |
| `UnitRemove` | `00000078` | action | `—` | u:unit |
| `UnitRemoveChargeRegen` | `64412A12` | action | `—` | inUnit:unit, inCharge:charge |
| `UnitRemoveChargeUsed` | `4353C769` | action | `—` | inUnit:unit, inCharge:charge |
| `UnitRemoveCooldown` | `1DB37563` | action | `—` | inUnit:unit, inCooldown:cooldown |
| `UnitResetSeed` | `ED5660CF` | action | `—` | u:unit |
| `UnitResetSpeed` | `70AC193B` | action | `—` | u:unit |
| `UnitRevive` | `9152ECEB` | action | `—` | u:unit |
| `UnitSelect` | `00000175` | action | `—` | unit:unit, player:int, select:preset |
| `UnitSetAIOption` | `DC310587` | action | `—` | u:unit, option:preset, val:preset |
| `UnitSetAttributePoint` | `3EE18973` | action | `—` | unit:unit, attribute:gamelink<Behavior>, baseBonus:preset, count:int |
| `UnitSetCursor` | `6710855E` | action | `—` | unit:unit, cursor:gamelink<Cursor> |
| `UnitSetCustomValue` | `49392C74` | action | `—` | u:unit, index:int, val:fixed |
| `UnitSetFacing` | `00000086` | action | `—` | u:unit, angle:fixed, dur:fixed |
| `UnitSetHeight` | `5B98BEAA` | action | `—` | u:unit, height:fixed, dur:fixed |
| `UnitSetInfoButtonTooltip` | `CA642D45` | action | `—` | unit:unit, key:string, text:text |
| `UnitSetInfoSubTip` | `2919EF94` | action | `—` | unit:unit, subTip:text |
| `UnitSetInfoText` | `02B2BBC6` | action | `—` | unit:unit, text:text, tip:text, subTip:text |
| `UnitSetInfoText2` | `F6DFE3E7` | action | `—` | unit:unit, text:text |
| `UnitSetInfoTip` | `39426421` | action | `—` | unit:unit, tip:text |
| `UnitSetOwner` | `00000082` | action | `—` | u:unit, p:int, cc:preset |
| `UnitSetPingCursor` | `80410686` | action | `—` | unit:unit, cursor:gamelink<Cursor> |
| `UnitSetPosition` | `0E8A5B30` | action | `—` | u:unit, p:point, blend:preset |
| `UnitSetProgressComplete` | `25FDDB2A` | action | `—` | unit:unit, slot:int, percent:int |
| `UnitSetProgressStage` | `D674ADD7` | action | `—` | unit:unit, slot:int, stage:preset |
| `UnitSetPropertyFixed` | `00000087` | action | `—` | u:unit, prop:preset, val:fixed |
| `UnitSetScale` | `00000228` | action | `—` | u:unit, x:fixed, y:fixed, z:fixed |
| `UnitSetSeed` | `685E2758` | action | `—` | unit:unit, seed:int |
| `UnitSetState` | `6B296A7A` | action | `—` | unit:unit, state:preset, value:preset |
| `UnitSetTeamColorIndex` | `8A467CA8` | action | `—` | unit:unit, index:playercolor |
| `UnitSetVariation` | `07C44396` | action | `—` | unit:unit, model:gamelink<Model>, percent:int, textures:string |
| `UnitShowKillDisplay` | `31DBC058` | action | `—` | unit:unit, killDisplaySetting:preset |
| `UnitsInRegionWithAllianceToPlayerMatchingCondition` | `7C654029` | call | `unitgroup` | type:gamelink<Unit>, type2:gamelink<Unit>, type22:gamelink<Unit>, player:int, alliance:preset, reg:region, unitFilter:unitfilter, count:int |
| `UnitsInUnitGroupWithCustomValue` | `295FEC18` | call | `unitgroup` | group:unitgroup, index:int, value:fixed |
| `UnitStatsStart` | `CC8265AD` | action | `—` | testName:text, unitName:text, unitFood:text |
| `UnitStatsStop` | `D2FFF574` | action | `—` | — |
| `UnitStatusBarClearOverride` | `15DDAB3C` | action | `—` | unit:unit |
| `UnitStatusBarOverride` | `2DCE16C1` | action | `—` | unit:unit, display:preset |
| `UnitSubgroupIndexNext` | `32DD830D` | action | `—` | player:int |
| `UnitSubgroupIndexPrevious` | `3512302B` | action | `—` | player:int |
| `UnitSubgroupIndexSelected` | `1DE4F900` | call | `int` | player:int |
| `UnitSubgroupSelected` | `09E9455C` | call | `unitgroup` | player:int |
| `UnitTechTreeBehaviorCount` | `00000260` | call | `int` | inUnit:unit, behaviorType:gamelink<Behavior>, countType:preset |
| `UnitTechTreeUnitCount` | `00000261` | call | `int` | inUnit:unit, unitType:gamelink<Unit>, countType:preset |
| `UnitTechTreeUpgradeCount` | `00000262` | call | `int` | inUnit:unit, upgradeType:gamelink<Upgrade>, countType:preset |
| `UnitTestPlane` | `00000335` | call | `bool` | u:unit, plane:preset |
| `UnitTestState` | `00000191` | call | `bool` | u:unit, s:preset |
| `UnitTransport` | `F7013450` | call | `unit` | unit:unit |
| `UnitTypeAnimationLoad` | `61E6CFB3` | action | `—` | unitType:gamelink<Unit>, animation:filepath |
| `UnitTypeAnimationLoadOverriding` | `DF8E92F0` | action | `—` | unitType:gamelink<Unit>, animation:filepath |
| `UnitTypeAnimationUnload` | `910C6A86` | action | `—` | unitType:gamelink<Unit>, animation:filepath |
| `UnitTypeFromString` | `A0CD12F3` | call | `gamelink<Unit>` | s:string |
| `UnitTypeGetCost` | `DD095653` | call | `int` | inUnitType:gamelink<Unit>, inCostType:preset |
| `UnitTypeGetGenderCode` | `98274AAB` | call | `string` | unitType:gamelink<Unit> |
| `UnitTypeGetName` | `4C8D7F8C` | call | `text` | unitType:gamelink<Unit> |
| `UnitTypeGetProperty` | `607524D8` | call | `fixed` | u:gamelink<Unit>, property:preset |
| `UnitTypeIsAffectedByUpgrade` | `492B580C` | call | `bool` | inUnitType:gamelink<Unit>, upgradeType:gamelink<Upgrade> |
| `UnitTypeIsSelected` | `A66AE70B` | call | `bool` | unitType:gamelink<Unit>, player:int |
| `UnitTypeMoveBlockersFromPoint` | `4802991E` | action | `—` | unitType:gamelink<Unit>, player:int, source:point, range:fixed |
| `UnitTypeMoveBlockersFromUnit` | `DA174129` | action | `—` | unitType:gamelink<Unit>, player:int, source:unit, range:fixed |
| `UnitTypePlacementFromPoint` | `8BF4F8D6` | call | `point` | unitType:gamelink<Unit>, player:int, source:point, range:fixed |
| `UnitTypePlacementFromUnit` | `FD60C2EF` | call | `point` | unitType:gamelink<Unit>, player:int, source:unit, range:fixed |
| `UnitTypePlacementTestsFromPoint` | `576D2D08` | call | `point` | unitType:gamelink<Unit>, player:int, source:point, range:fixed, tests:preset |
| `UnitTypePlacementTestsFromUnit` | `88F27E1E` | call | `point` | unitType:gamelink<Unit>, player:int, source:unit, range:fixed, tests:preset |
| `UnitTypeTestAttribute` | `7A0CB31F` | call | `bool` | u:gamelink<Unit>, attributeType:preset |
| `UnitTypeTestFlag` | `A6058F5C` | call | `bool` | u:gamelink<Unit>, f:preset |
| `UnitUnloadModel` | `E188E0FE` | action | `—` | u:unit |
| `UnitValidateEffectPoint` | `DDC0D455` | call | `int` | caster:unit, effect:gamelink<Effect>, point:point |
| `UnitValidateEffectUnit` | `614EA577` | call | `int` | caster:unit, effect:gamelink<Effect>, unit:unit |
| `UnitWaitUntilIdle` | `31D7ABB2` | action | `—` | u:unit, idle:preset |
| `UnitWeaponAdd` | `CE396866` | action | `—` | unit:unit, weapon:gamelink<Weapon>, turret:gamelink<Turret> |
| `UnitWeaponCheck` | `2E6C3EA6` | call | `bool` | unit:unit, weapon:int, target:preset |
| `UnitWeaponCount` | `7045D649` | call | `int` | unit:unit |
| `UnitWeaponDamage` | `5F3CBC59` | call | `fixed` | unit:unit, index:int, attribute:preset, maximum:preset |
| `UnitWeaponGet` | `E8D948E0` | call | `gamelink<Weapon>` | unit:unit, weapon:int |
| `UnitWeaponIsEnabled` | `981AB385` | call | `bool` | unit:unit, weapon:int |
| `UnitWeaponPeriod` | `92BF3C14` | call | `fixed` | unit:unit, weapon:int |
| `UnitWeaponPeriodRemaining` | `CE962B10` | call | `fixed` | unit:unit, weapon:int |
| `UnitWeaponRange` | `091FEFE6` | call | `fixed` | unit:unit, weapon:int |
| `UnitWeaponRemove` | `843B0E58` | action | `—` | unit:unit, weapon:gamelink<Weapon> |
| `UnitWeaponSetPeriodRemaining` | `A4E0AE63` | action | `—` | u:unit, index:int, remaining:fixed |
| `UnitWeaponSpeedMultiplier` | `F9410656` | call | `fixed` | unit:unit, index:int |
| `UnitXPAddXP` | `9B8C2BCE` | action | `—` | unit:unit, veterancyBehavior:gamelink<Behavior>, xP:fixed |
| `UnitXPGainEnable` | `00000390` | action | `—` | unit:unit, behavior:gamelink<Behavior>, enable:preset |
| `UnitXPGetCurrentLevel` | `6C7EDC40` | call | `int` | unit:unit, veterancyBehavior:gamelink<Behavior> |
| `UnitXPGetCurrentXP` | `1DC3411C` | call | `fixed` | unit:unit, veterancyBehavior:gamelink<Behavior> |
| `UnitXPGetNumLevels` | `925849D7` | call | `int` | unit:unit, veterancyBehavior:gamelink<Behavior> |
| `UnitXPGetXPForLevel` | `8E739839` | call | `int` | unit:unit, veterancyBehavior:gamelink<Behavior>, level:int |
| `UnitXPSetCurrentLevel` | `CE1D487E` | action | `—` | unit:unit, veterancyBehavior:gamelink<Behavior>, level:int |
| `UnitXPSetCurrentXP` | `398A6E5C` | action | `—` | unit:unit, veterancyBehavior:gamelink<Behavior>, xP:fixed |
| `UnitXPSetXPForLevel` | `F712D7BE` | action | `—` | unit:unit, veterancyBehavior:gamelink<Behavior>, level:int, xP:int |
| `UnitXPTotal` | `00000354` | call | `fixed` | unit:unit |
| `UserDataField` | `6481120E` | call | `userfield` | userType:gamelink<User>, index:int |
| `UserDataFieldCount` | `C6A22ECC` | call | `int` | userType:gamelink<User> |
| `UserDataFieldIsModifiable` | `506AE6E3` | call | `bool` | userType:gamelink<User>, field:userfield |
| `UserDataFieldType` | `AF40397B` | call | `preset` | userType:gamelink<User>, field:userfield |
| `UserDataFieldValueCount` | `D6D5CB34` | call | `int` | userType:gamelink<User>, field:userfield |
| `UserDataGetAbilCmd` | `220C20A2` | call | `abilcmd` | userType:gamelink<User>, instance:userinstance, field:userfield, index:int |
| `UserDataGetActor` | `585225C7` | call | `gamelink<Actor>` | userType:gamelink<User>, instance:userinstance, field:userfield, index:int |
| `UserDataGetColor` | `A4E9B3A1` | call | `color` | userType:gamelink<User>, instance:userinstance, field:userfield, index:int |
| `UserDataGetCompare` | `66E7F779` | call | `preset` | userType:gamelink<User>, instance:userinstance, field:userfield, index:int |
| `UserDataGetFixed` | `A6423891` | call | `fixed` | userType:gamelink<User>, instance:userinstance, field:userfield, index:int |
| `UserDataGetGameLink` | `D8DCE241` | call | `gamelink` | userType:gamelink<User>, instance:userinstance, field:userfield, index:int |
| `UserDataGetImageAttachPoint` | `7A847E04` | call | `preset` | userType:gamelink<User>, instance:userinstance, field:userfield, index:int |
| `UserDataGetImageEdge` | `D90FAABF` | call | `preset` | userType:gamelink<User>, instance:userinstance, field:userfield, index:int |
| `UserDataGetImagePath` | `094200DA` | call | `filepath` | userType:gamelink<User>, instance:userinstance, field:userfield, index:int |
| `UserDataGetInt` | `1B79DE77` | call | `int` | userType:gamelink<User>, instance:userinstance, field:userfield, index:int |
| `UserDataGetModel` | `FF4BA99B` | call | `gamelink<Model>` | userType:gamelink<User>, instance:userinstance, field:userfield, index:int |
| `UserDataGetMovie` | `60FC3262` | call | `filepath` | userType:gamelink<User>, instance:userinstance, field:userfield, index:int |
| `UserDataGetSound` | `9A2BEF12` | call | `gamelink<Sound>` | userType:gamelink<User>, instance:userinstance, field:userfield, index:int |
| `UserDataGetString` | `0F7F44F5` | call | `string` | userType:gamelink<User>, instance:userinstance, field:userfield, index:int |
| `UserDataGetText` | `2002EBDA` | call | `text` | userType:gamelink<User>, instance:userinstance, field:userfield, index:int |
| `UserDataGetUnit` | `C30C7198` | call | `gamelink<Unit>` | userType:gamelink<User>, instance:userinstance, field:userfield, index:int |
| `UserDataGetUpgrade` | `CAB7927F` | call | `gamelink<Upgrade>` | userType:gamelink<User>, instance:userinstance, field:userfield, index:int |
| `UserDataGetUserInstance` | `8732457F` | call | `userinstance` | userType:gamelink<User>, instance:userinstance, field:userfield, index:int |
| `UserDataGetUserType` | `63B29BEF` | call | `gamelink<User>` | userType:gamelink<User>, instance:userinstance, field:userfield, index:int |
| `UserDataInstance` | `0805CD83` | call | `userinstance` | userType:gamelink<User>, index:int |
| `UserDataInstanceCount` | `2026602E` | call | `int` | userType:gamelink<User> |
| `UserDataInstanceFromReference` | `F7B7A945` | call | `userinstance` | reference:string |
| `UserDataInstanceGetIndex` | `8955668E` | call | `int` | userType:gamelink<User>, instance:userinstance |
| `UserDataLoadInstance` | `B4A82C25` | action | `—` | userType:gamelink<User>, instance:userinstance, bank:bank, section:string |
| `UserDataLoadType` | `092B0BD9` | action | `—` | userType:gamelink<User>, bank:bank, section:string |
| `UserDataResetAll` | `64E3B90F` | action | `—` | — |
| `UserDataResetInstance` | `643614CC` | action | `—` | userType:gamelink<User>, instance:userinstance |
| `UserDataResetType` | `977B80DD` | action | `—` | userType:gamelink<User> |
| `UserDataResetValue` | `AF5F1505` | action | `—` | userType:gamelink<User>, instance:userinstance, field:userfield, index:int |
| `UserDataSaveInstance` | `536BD1BC` | action | `—` | userType:gamelink<User>, instance:userinstance, bank:bank, section:string |
| `UserDataSaveType` | `F1053158` | action | `—` | userType:gamelink<User>, bank:bank, section:string |
| `UserDataSetAbilCmd` | `8E0202F1` | action | `—` | userType:gamelink<User>, instance:userinstance, field:userfield, index:int, value:abilcmd |
| `UserDataSetActor` | `B2C86A74` | action | `—` | userType:gamelink<User>, instance:userinstance, field:userfield, index:int, value:gamelink<Actor> |
| `UserDataSetColor` | `ECCE2474` | action | `—` | userType:gamelink<User>, instance:userinstance, field:userfield, index:int, value:color |
| `UserDataSetCompare` | `31C99974` | action | `—` | userType:gamelink<User>, instance:userinstance, field:userfield, index:int, value:preset |
| `UserDataSetFixed` | `E2CB27D0` | action | `—` | userType:gamelink<User>, instance:userinstance, field:userfield, index:int, value:fixed |
| `UserDataSetGameLink` | `CFD68787` | action | `—` | userType:gamelink<User>, instance:userinstance, field:userfield, index:int, value:anygamelink |
| `UserDataSetImageAttachPoint` | `450FEADA` | action | `—` | userType:gamelink<User>, instance:userinstance, field:userfield, index:int, value:preset |
| `UserDataSetImageEdge` | `A56E59EF` | action | `—` | userType:gamelink<User>, instance:userinstance, field:userfield, index:int, value:preset |
| `UserDataSetImagePath` | `B53C5B19` | action | `—` | userType:gamelink<User>, instance:userinstance, field:userfield, index:int, value:filepath |
| `UserDataSetInt` | `0C607001` | action | `—` | userType:gamelink<User>, instance:userinstance, field:userfield, index:int, value:int |
| `UserDataSetModel` | `391E911E` | action | `—` | userType:gamelink<User>, instance:userinstance, field:userfield, index:int, value:gamelink<Model> |
| `UserDataSetMovie` | `51B28574` | action | `—` | userType:gamelink<User>, instance:userinstance, field:userfield, index:int, value:filepath |
| `UserDataSetSound` | `4A855A37` | action | `—` | userType:gamelink<User>, instance:userinstance, field:userfield, index:int, value:gamelink<Sound> |
| `UserDataSetString` | `4720DFCB` | action | `—` | userType:gamelink<User>, instance:userinstance, field:userfield, index:int, value:string |
| `UserDataSetText` | `6649CC1C` | action | `—` | userType:gamelink<User>, instance:userinstance, field:userfield, index:int, value:text |
| `UserDataSetUnit` | `3022613D` | action | `—` | userType:gamelink<User>, instance:userinstance, field:userfield, index:int, value:gamelink<Unit> |
| `UserDataSetUpgrade` | `94F956A9` | action | `—` | userType:gamelink<User>, instance:userinstance, field:userfield, index:int, value:gamelink<Upgrade> |
| `UserDataSetUser` | `8DE799A6` | action | `—` | userType:gamelink<User>, instance:userinstance, field:userfield, index:int, valueType:gamelink<User>, valueInstance:userinstance |
| `UserDataTypeFromReference` | `E2520EA5` | call | `gamelink<User>` | reference:string |
