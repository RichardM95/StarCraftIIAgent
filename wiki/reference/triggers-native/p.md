# SC2 Native Functions: P

Columns are documented in [../triggers-native-functions.md](../triggers-native-functions.md). Reference in XML as `<FunctionDef Type="FunctionDef" Library="Ntve" Id="<ID>"/>`.

Parameter defaults in `nativelib` do not auto-apply; emit an explicit `<Parameter Type="Param" Id="..."/>` for every slot in generated `<FunctionCall>` XML.

### P

<a id="p"></a>

| Name | ID | Kind | Returns | Params |
|---|---|---|---|---|
| `PathAddNoFlyZone` | `BE0F6AB0` | action | `—` | center:point, innerRadius:fixed, outerRadius:fixed |
| `PathAddWayPoint` | `1CD72A70` | action | `—` | pathDisplay:path, wayPoint:point |
| `PathClearWayPoints` | `0FC9D43B` | action | `—` | pathDisplay:path |
| `PathCreateForUnit` | `BF008209` | action | `—` | players:playergroup, unit:unit |
| `PathCreateForUnitType` | `1017BD97` | action | `—` | players:playergroup, unitType:gamelink<Unit>, p:int, source:point |
| `PathDestroy` | `05691991` | action | `—` | pathDisplay:path |
| `PathDestroyAll` | `D59211C0` | action | `—` | players:playergroup |
| `PathGetColor` | `DA6498E2` | call | `color` | pathDisplay:path, location:preset |
| `PathGetDestinationPoint` | `3223FAE5` | call | `point` | pathDisplay:path |
| `PathGetDestinationUnit` | `E3158D39` | call | `unit` | pathDisplay:path |
| `PathGetLineTexture` | `B1FC0A5E` | call | `filepath` | pathDisplay:path, location:preset |
| `PathGetLineTileLength` | `D4D7CBDD` | call | `fixed` | pathDisplay:path, location:preset |
| `PathGetLineWidth` | `3B2F056B` | call | `fixed` | pathDisplay:path, location:preset |
| `PathGetMinimumLinearDistance` | `41665764` | call | `fixed` | pathDisplay:path |
| `PathGetMinimumStepCount` | `A734BA14` | call | `int` | pathDisplay:path |
| `PathGetMinimumTravelDistance` | `5F676AE0` | call | `fixed` | pathDisplay:path |
| `PathGetSourcePoint` | `0050269D` | call | `point` | pathDisplay:path |
| `PathGetSourceUnit` | `6BAC1C63` | call | `unit` | pathDisplay:path |
| `PathGetStepMidpoint` | `A4D081B5` | call | `fixed` | pathDisplay:path, location:preset |
| `PathGetStepModel` | `4E0246F4` | call | `filepath` | pathDisplay:path, location:preset |
| `PathGetStepModelScale` | `BE61468D` | call | `fixed` | pathDisplay:path, location:preset |
| `PathGetUnit` | `16D2169B` | call | `unit` | pathDisplay:path |
| `PathGetUnitType` | `68FB7332` | call | `gamelink<Unit>` | pathDisplay:path |
| `PathGetVisible` | `E201830F` | call | `preset` | pathDisplay:path, location:preset |
| `PathingType` | `F0C49951` | call | `preset` | p1:point |
| `PathLastCreated` | `4FED6B87` | call | `path` | — |
| `PathRemoveNoFlyZonesInRegion` | `3A2B888E` | action | `—` | region:region |
| `PathSetAbilClassFilter` | `3CF55EBF` | action | `—` | pathDisplay:path, abilClass:preset, filter:preset |
| `PathSetColor` | `B07FBC86` | action | `—` | pathDisplay:path, location:preset, color:color |
| `PathSetDestinationPoint` | `C765351D` | action | `—` | pathDisplay:path, destination:point |
| `PathSetDestinationUnit` | `DEB2D50B` | action | `—` | pathDisplay:path, destination:unit |
| `PathSetLineTexture` | `07C5FA2D` | action | `—` | pathDisplay:path, location:preset, texture:filepath |
| `PathSetLineTileLength` | `77877287` | action | `—` | pathDisplay:path, location:preset, tileLength:fixed |
| `PathSetLineWidth` | `87D1FBA5` | action | `—` | pathDisplay:path, location:preset, width:fixed |
| `PathSetMinimumLinearDistance` | `5B57CA27` | action | `—` | pathDisplay:path, distance:fixed |
| `PathSetMinimumStepCount` | `2EB2DDB1` | action | `—` | pathDisplay:path, turnCount:int |
| `PathSetMinimumTravelDistance` | `55941BDF` | action | `—` | pathDisplay:path, distance:fixed |
| `PathSetSourcePoint` | `D46705E8` | action | `—` | pathDisplay:path, source:point |
| `PathSetSourceUnit` | `38A77E51` | action | `—` | pathDisplay:path, source:unit |
| `PathSetStepMidpoint` | `F25FBCA5` | action | `—` | pathDisplay:path, location:preset, midpoint:fixed |
| `PathSetStepModel` | `E4BE9CB7` | action | `—` | pathDisplay:path, location:preset, model:filepath |
| `PathSetStepModelScale` | `9203F453` | action | `—` | pathDisplay:path, location:preset, scale:fixed |
| `PathSetVisible` | `B2382E36` | action | `—` | pathDisplay:path, location:preset, visibility:preset |
| `PauseUnit` | `30000000` | action | `—` | unit:unit, pauseUnpause:preset |
| `PerfTestGetFPS` | `DE95E136` | action | `—` | — |
| `PerfTestStart` | `DDC4330E` | action | `—` | inTestName:text |
| `PerfTestStop` | `3186E4A3` | action | `—` | — |
| `PickEachBackupBank` | `247BCDF4` | action | `—` | originalBank:bank, descending:bool +1sub |
| `PickEachInteger` | `9DE705AA` | action | `—` | s:int, e:int +1sub |
| `PickEachIntegerDeprecated` | `A00A7B2F` | action | `—` | s:int, e:int +1sub |
| `PickEachPlayerInGroup` | `5084725D` | action | `—` | group:playergroup +1sub |
| `PickEachPlayerInGroupDeprecated` | `0155FBC1` | action | `—` | group:playergroup +1sub |
| `PickEachUnitInGroup` | `C4DC760C` | action | `—` | group:unitgroup +1sub |
| `PickEachUnitInGroupDeprecated` | `A6E334F9` | action | `—` | group:unitgroup +1sub |
| `PingCreate` | `1A51D70F` | action | `—` | players:playergroup, model:gamelink<Model>, position:point, color:color, duration:fixed |
| `PingCreateFromData` | `61BEDAD5` | action | `—` | players:playergroup, pingData:gamelink<Ping>, position:point |
| `PingCreateWithPlayerId` | `4F553268` | action | `—` | players:playergroup, model:gamelink<Model>, position:point, color:color, duration:fixed, playerId:int |
| `PingDestroy` | `6395B1F2` | action | `—` | ping:ping |
| `PingDestroyAll` | `04644E36` | action | `—` | — |
| `PingGetColor` | `F994897E` | call | `color` | ping:ping |
| `PingGetDepth` | `E22343C7` | call | `fixed` | ping:ping |
| `PingGetDuration` | `FFE4A881` | call | `fixed` | ping:ping |
| `PingGetPlayerGroup` | `027124D8` | call | `playergroup` | ping:ping |
| `PingGetPosition` | `24AF481F` | call | `point` | ping:ping |
| `PingGetRotation` | `495914FD` | call | `fixed` | ping:ping |
| `PingGetScale` | `780A3562` | call | `fixed` | ping:ping |
| `PingGetTooltip` | `77B0CBF3` | call | `text` | ping:ping |
| `PingGetUnit` | `348B2771` | call | `unit` | ping:ping |
| `PingIsVisible` | `F47E52DA` | call | `bool` | ping:ping |
| `PingLastCreated` | `6A7E59D3` | call | `ping` | — |
| `PingSetColor` | `A89BD9B9` | action | `—` | ping:ping, color:color |
| `PingSetDepth` | `B1CFA480` | action | `—` | ping:ping, depth:fixed |
| `PingSetDuration` | `FBDAE819` | action | `—` | ping:ping, duration:fixed |
| `PingSetModel` | `3B7925CF` | action | `—` | ping:ping, model:gamelink<Model> |
| `PingSetObserver` | `838182D6` | action | `—` | ping:ping, observerDisplay:bool |
| `PingSetPlayerGroup` | `C245D884` | action | `—` | ping:ping, players:playergroup |
| `PingSetPlayerPingsShown` | `A03A4CC4` | action | `—` | players:playergroup, show:preset |
| `PingSetPosition` | `1D8FF628` | action | `—` | ping:ping, position:point |
| `PingSetRotation` | `F713CAF4` | action | `—` | ping:ping, rotation:fixed |
| `PingSetScale` | `160D3874` | action | `—` | ping:ping, scale:fixed |
| `PingSetTooltip` | `01BF32CA` | action | `—` | ping:ping, tooltip:text |
| `PingSetUnit` | `137A7BD8` | action | `—` | ping:ping, unit:unit |
| `PingSetUsePlayerVision` | `FDD9B85C` | action | `—` | ping:ping, usePlayerVision:bool |
| `PingSetUseUnitTeamColor` | `63083C14` | action | `—` | ping:ping, useUnitTeamColor:bool |
| `PingSetUseUnitVisibility` | `80A31841` | action | `—` | ping:ping, useUnitVisibility:bool |
| `PingSetVisible` | `14E7EDA5` | action | `—` | ping:ping, visible:preset |
| `PlanetClearSelected` | `1BDD412A` | action | `—` | playerGroup:playergroup |
| `PlanetCreate` | `BDA978A3` | action | `—` | playerGroup:playergroup, state:preset |
| `PlanetDestroy` | `A4514899` | action | `—` | planet:planet |
| `PlanetDestroyAll` | `B4A6A5B4` | action | `—` | playerGroup:playergroup |
| `PlanetGetSelected` | `4F98822C` | call | `planet` | player:int |
| `PlanetLastCreated` | `59E2C6BA` | call | `planet` | — |
| `PlanetPanelGetContactButtonState` | `9148F568` | call | `preset` | player:int |
| `PlanetPanelSetBackButtonEnabled` | `D3D9E2FF` | action | `—` | playerGroup:playergroup, enable:preset |
| `PlanetPanelSetBackButtonShortcut` | `30B2D029` | action | `—` | playerGroup:playergroup, text:text |
| `PlanetPanelSetBackButtonText` | `A7380A9D` | action | `—` | playerGroup:playergroup, text:text |
| `PlanetPanelSetBackButtonTooltip` | `801DDCC7` | action | `—` | playerGroup:playergroup, text:text |
| `PlanetPanelSetBackgroundImage` | `03E8CE6D` | action | `—` | playerGroup:playergroup, image:filepath |
| `PlanetPanelSetContactButtonState` | `6BA3777F` | action | `—` | playerGroup:playergroup, state:preset |
| `PlanetPanelSetDismissButtonEnabled` | `151FE05D` | action | `—` | playerGroup:playergroup, enable:preset |
| `PlanetSetBackgroundModelLink` | `4D14B15E` | action | `—` | planet:planet, backgroundModel:gamelink<Model> |
| `PlanetSetBonusText` | `9201E14B` | action | `—` | planet:planet, text:text |
| `PlanetSetBonusTitle` | `9FA4C724` | action | `—` | planet:planet, text:text |
| `PlanetSetContactActorLink` | `1998FE49` | action | `—` | planet:planet, contactActor:gamelink<Actor> |
| `PlanetSetContactModelLink` | `7A143A7E` | action | `—` | planet:planet, contactModel:gamelink<Model> |
| `PlanetSetContactName` | `F38805FC` | action | `—` | planet:planet, contactName:text |
| `PlanetSetContactTitle` | `ED219560` | action | `—` | planet:planet, text:text |
| `PlanetSetContactTooltipText` | `C58C1BAE` | action | `—` | planet:planet, text:text |
| `PlanetSetDescriptionText` | `EFCAAF54` | action | `—` | planet:planet, text:text |
| `PlanetSetMissionName` | `FE96FB00` | action | `—` | planet:planet, missionName:text |
| `PlanetSetMissionTitle` | `03738586` | action | `—` | planet:planet, text:text |
| `PlanetSetPlanetModelLink` | `E4236D69` | action | `—` | planet:planet, model:gamelink<Model> |
| `PlanetSetPlanetName` | `B9237D66` | action | `—` | planet:planet, name:text |
| `PlanetSetPlanetText` | `9E135D06` | action | `—` | planet:planet, text:text |
| `PlanetSetPlayerGroup` | `C9A82E1C` | action | `—` | planet:planet, players:playergroup |
| `PlanetSetPrimaryObjectiveText` | `B0E8C066` | action | `—` | planet:planet, objectiveText:text |
| `PlanetSetPrimaryObjectiveTitle` | `ECE714B6` | action | `—` | planet:planet, text:text |
| `PlanetSetResearchText` | `CE116FDF` | action | `—` | planet:planet, researchText:text |
| `PlanetSetResearchTitle` | `AEFE21C9` | action | `—` | planet:planet, text:text |
| `PlanetSetRewardText` | `D98E6C3C` | action | `—` | planet:planet, rewardText:text |
| `PlanetSetRewardTitle` | `56C6AAD2` | action | `—` | planet:planet, text:text |
| `PlanetSetSecondaryObjectiveText` | `A5C61E11` | action | `—` | planet:planet, objectiveText:text |
| `PlanetSetSecondaryObjectiveTitle` | `AAD78637` | action | `—` | planet:planet, text:text |
| `PlanetSetSelected` | `76D6BC75` | action | `—` | playerGroup:playergroup, planet:planet |
| `PlanetSetState` | `7FA89636` | action | `—` | planet:planet, state:preset |
| `PlanetSetTechnologyIconFilePath` | `395E3579` | action | `—` | planet:planet, icon:filepath |
| `PlanetSetTechnologyName` | `217449C0` | action | `—` | planet:planet, technologyName:text |
| `PlanetSetTechnologyText` | `3DD9B176` | action | `—` | planet:planet, technologyText:text |
| `PlanetSetTechnologyTitle` | `14A18B2C` | action | `—` | planet:planet, text:text |
| `PlanetSetTechnologyTooltipText` | `31C6C91E` | action | `—` | planet:planet, text:text |
| `PlanetSetTechnologyUnitLink` | `62B17FF5` | action | `—` | planet:planet, unitLink:gamelink<Unit> |
| `PlanetSetTooltipText` | `DD1756B5` | action | `—` | planet:planet, text:text |
| `PlayAnimation` | `6ECCAD6C` | action | `—` | target:actor, identifier:string, animation:modelanim, flags:preset, blendTime:fixed |
| `PlayAnimationOnDoodadsInRegion` | `5DE3374D` | action | `—` | target:region, doodadType:gamelink<Actor>, identifier:string, animation:modelanim, flags:preset, blendTime:fixed |
| `PlayerACEnemyWaveType` | `43A0D2F6` | call | `int` | p:int |
| `PlayerAddChargeRegen` | `CDFB6082` | action | `—` | inPlayer:int, inCharge:string, inVal:fixed |
| `PlayerAddChargeRegenFull` | `C2C6163D` | action | `—` | inPlayer:int, inCharge:string, inVal:fixed |
| `PlayerAddChargeRegenRemaining` | `E8E2A8ED` | action | `—` | inPlayer:int, inCharge:string, inVal:fixed |
| `PlayerAddChargeUsed` | `1D502AEE` | action | `—` | inPlayer:int, inCharge:string, inVal:fixed |
| `PlayerAddCooldown` | `95EAE029` | action | `—` | inPlayer:int, inCooldown:string, inVal:fixed |
| `PlayerAddLabel` | `2AB8173B` | action | `—` | player:int, label:string |
| `PlayerAddResponse` | `22A8F646` | action | `—` | player:int, response:gamelink<PlayerResponse> |
| `PlayerAddReward` | `275E6E7C` | action | `—` | player:int, reward:string |
| `PlayerAddTalent` | `9BE5E091` | action | `—` | player:int, talent:gamelink<Talent> |
| `PlayerApplySkin` | `A3E34362` | action | `—` | player:int, skin:gamelink<Skin>, activateDeactivate:preset |
| `PlayerApplySkinReplacingExistingUnit` | `6C2CD9DE` | action | `—` | player:int, skin:gamelink<Skin>, activateDeactivate:preset |
| `PlayerArtifact` | `0700F547` | call | `gamelink<Artifact>` | p:int, artifactIndex:int |
| `PlayerArtifactRank` | `4988B6E2` | call | `int` | p:int, artifactIndex:int |
| `PlayerBeaconAlert` | `5295B368` | action | `—` | player:int, beacon:preset, alert:string, message:text |
| `PlayerBeaconClearTarget` | `FF813C01` | action | `—` | player:int, beacon:preset |
| `PlayerBeaconGetAllyPlayerId` | `AA9CC64B` | call | `int` | player:int, allyNum:int |
| `PlayerBeaconGetNumAllies` | `81D42ACF` | call | `int` | player:int |
| `PlayerBeaconGetTargetPoint` | `E9B4AB04` | call | `point` | player:int, beacon:preset |
| `PlayerBeaconGetTargetUnit` | `4C9C60B2` | call | `unit` | player:int, beacon:preset |
| `PlayerBeaconIsAutoCast` | `329485DF` | call | `bool` | player:int, beacon:preset |
| `PlayerBeaconIsFromUser` | `43549439` | call | `bool` | player:int, beacon:preset |
| `PlayerBeaconIsSet` | `E78465C0` | call | `bool` | player:int, beacon:preset |
| `PlayerBeaconRequestedMinerals` | `90D9D6B1` | call | `int` | player:int |
| `PlayerBeaconRequestedVespene` | `E7A1FD48` | call | `int` | player:int |
| `PlayerBeaconSetAutoCast` | `920815B9` | action | `—` | player:int, beacon:preset, enable:bool |
| `PlayerBeaconSetTargetPoint` | `9F8D343B` | action | `—` | player:int, beacon:preset, point:point, alert:bool |
| `PlayerBeaconSetTargetUnit` | `1593FCCC` | action | `—` | player:int, beacon:preset, unit:unit, alert:bool |
| `PlayerBrutalPlusDifficulty` | `EC9BA2B1` | call | `int` | p:int |
| `PlayerCanCreateEffectAtPoint` | `AF40BDE1` | call | `bool` | player:int, effect:gamelink<Effect>, point:point |
| `PlayerCanCreateEffectOnUnit` | `326F770A` | call | `bool` | player:int, effect:gamelink<Effect>, target:unit |
| `PlayerClearResponse` | `093C2762` | action | `—` | player:int, responseType:preset, location:preset |
| `PlayerCommander` | `2A6F4A29` | call | `gamelink<Commander>` | p:int |
| `PlayerCommanderLevel` | `53B9899B` | call | `int` | p:int |
| `PlayerCommanderMasteryLevel` | `46B736B4` | call | `int` | p:int |
| `PlayerCommanderMasteryTalentRank` | `2FF15B58` | call | `int` | p:int, talentIndex:int |
| `PlayerCommanderSelectedPrestige` | `853E3ADE` | call | `int` | p:int |
| `PlayerCreateEffectPoint` | `AB4663C2` | action | `—` | caster:int, effect:gamelink<Effect>, point:point |
| `PlayerCreateEffectUnit` | `EF15E7E2` | action | `—` | caster:int, effect:gamelink<Effect>, unit:unit |
| `PlayerDifficulty` | `2DFE4998` | call | `difficulty` | p:int |
| `PlayerGetAlliance` | `00000240` | call | `bool` | inSourcePlayer:int, inAllianceId:preset, inTargetPlayer:int |
| `PlayerGetChargeRegen` | `5F8A9E51` | call | `fixed` | inPlayer:int, inCharge:string |
| `PlayerGetChargeRegenFull` | `694FE99D` | call | `fixed` | inPlayer:int, inCharge:string, adjustmentOnly:bool |
| `PlayerGetChargeUsed` | `8AFB7F8B` | call | `fixed` | inPlayer:int, inCharge:string |
| `PlayerGetColorIndex` | `60A98A5A` | call | `playercolor` | player:int, option:preset |
| `PlayerGetCooldown` | `1AA9CCBB` | call | `fixed` | inPlayer:int, inCooldown:string |
| `PlayerGetHotkeyProfile` | `45C60DAF` | call | `string` | p:int |
| `PlayerGetPropertyFixed` | `69602796` | call | `fixed` | p:int, prop:preset |
| `PlayerGetPropertyInt` | `00000051` | call | `int` | p:int, prop:preset |
| `PlayerGetState` | `00000413` | call | `bool` | player:int, state:preset |
| `PlayerGroupActive` | `F463A414` | call | `playergroup` | — |
| `PlayerGroupAdd` | `15C2C248` | action | `—` | g:playergroup, p:int |
| `PlayerGroupAll` | `00000192` | call | `playergroup` | — |
| `PlayerGroupAlliance` | `B90786F4` | call | `playergroup` | alliance:preset, player:int |
| `PlayerGroupClear` | `00000059` | action | `—` | g:playergroup |
| `PlayerGroupCopy` | `00000214` | call | `playergroup` | g:playergroup |
| `PlayerGroupCount` | `00000061` | call | `int` | g:playergroup |
| `PlayerGroupEmpty` | `00000056` | call | `playergroup` | — |
| `PlayerGroupHasPlayer` | `00000062` | call | `bool` | g:playergroup, p:int |
| `PlayerGroupLoopCurrent` | `8570CA61` | call | `int` | — |
| `PlayerGroupLoopCurrentDeprecated` | `36ABE390` | call | `int` | — |
| `PlayerGroupPlayer` | `00000215` | call | `int` | g:playergroup, i:int |
| `PlayerGroupRemove` | `A8D356D7` | action | `—` | g:playergroup, p:int |
| `PlayerGroupSingle` | `00000057` | call | `playergroup` | p:int |
| `PlayerHandle` | `A5AB8322` | call | `string` | p:int |
| `PlayerHasAccessTo` | `CA19F820` | call | `bool` | player:int, entity:string |
| `PlayerHasLabel` | `EE06C602` | call | `bool` | player:int, label:string |
| `PlayerHasLicense` | `34577ED6` | call | `bool` | player:int, license:preset |
| `PlayerHasReward` | `68471659` | call | `bool` | p:int, reward:gamelink<Reward> |
| `PlayerHasTalent` | `998A01FC` | call | `bool` | p:int, talent:gamelink<Talent> |
| `PlayerHero` | `A364EF52` | call | `gamelink<Hero>` | p:int |
| `PlayerInCinematicMode` | `0B5CB9F5` | call | `bool` | player:int |
| `PlayerInStoryMode` | `0FF645BE` | call | `bool` | player:int |
| `PlayerIsEnemy` | `CA3AB9A9` | call | `bool` | sourcePlayer:int, targetPlayer:int, relation:preset |
| `PlayerModifyPropertyFixed` | `4CA291C4` | action | `—` | p:int, prop:preset, operation:preset, val:fixed |
| `PlayerModifyPropertyInt` | `943DF2F7` | action | `—` | p:int, prop:preset, operation:preset, val:int |
| `PlayerMount` | `0C9C0762` | call | `gamelink<Mount>` | p:int |
| `PlayerName` | `B611A2DA` | call | `text` | p:int |
| `PlayerOptionOverride` | `BDF27E57` | action | `—` | p:int, option:gameoption, value:gameoptionvalue |
| `PlayerPauseAllCharges` | `12E0F820` | action | `—` | inPlayer:int, pause:preset |
| `PlayerPauseAllCooldowns` | `14B399BD` | action | `—` | inPlayer:int, pause:preset |
| `PlayerRace` | `00000155` | call | `gamelink<Race>` | p:int |
| `PlayerRemoveAllLabels` | `7DB0C9D2` | action | `—` | player:int |
| `PlayerRemoveChargeRegen` | `AF67EB9F` | action | `—` | inPlayer:int, inCharge:string |
| `PlayerRemoveChargeUsed` | `3D9A3C0C` | action | `—` | inPlayer:int, inCharge:string |
| `PlayerRemoveCooldown` | `E3741424` | action | `—` | inPlayer:int, inCooldown:string |
| `PlayerRemoveLabel` | `9FD7FFFF` | action | `—` | player:int, label:string |
| `PlayerRemoveResponse` | `6914EAD1` | action | `—` | player:int, response:gamelink<PlayerResponse> |
| `PlayerRemoveTalent` | `B7D4E5C6` | action | `—` | player:int, talent:gamelink<Talent> |
| `PlayerRetryMutation` | `E972F9AC` | call | `int` | p:int, mutationNumber:int |
| `PlayerScoreValueEnable` | `28B72345` | action | `—` | inPlayer:int, scoreValue:gamelink<ScoreValue>, enable:preset |
| `PlayerScoreValueEnableAll` | `BD8A7B23` | action | `—` | inPlayer:int, enable:preset |
| `PlayerScoreValueGetAsFixed` | `80445C7C` | call | `fixed` | player:int, score:gamelink<ScoreValue> |
| `PlayerScoreValueGetAsInt` | `E2FCA970` | call | `int` | player:int, score:gamelink<ScoreValue> |
| `PlayerScoreValueSetFromFixed` | `15003AC6` | action | `—` | p:int, prop:gamelink<ScoreValue>, val:fixed |
| `PlayerScoreValueSetFromInt` | `7EFD6723` | action | `—` | p:int, prop:gamelink<ScoreValue>, val:int |
| `PlayerSetAlliance` | `00000239` | action | `—` | inSourcePlayer:int, inAllianceId:preset, inTargetPlayer:int, ally:preset |
| `PlayerSetBounds` | `AED628D3` | action | `—` | player:int, region:region |
| `PlayerSetColorIndex` | `69EDDFF6` | action | `—` | player:int, color:playercolor, changeUnits:preset |
| `PlayerSetCommander` | `2BE2A3C9` | action | `—` | player:int, commander:gamelink<Commander> |
| `PlayerSetCommanderLevel` | `D87D559C` | action | `—` | player:int, commanderLevel:int |
| `PlayerSetCommanderMasteryLevel` | `BF5965EB` | action | `—` | player:int, masteryLevel:int |
| `PlayerSetConsoleSkin` | `8CF1C041` | action | `—` | player:int, consoleSkin:gamelink<ConsoleSkin> |
| `PlayerSetDeathTimer` | `93A62F0C` | action | `—` | player:int, timer:timer |
| `PlayerSetDifficulty` | `CACCC2D8` | action | `—` | player:int, difficultyLevel:difficulty |
| `PlayerSetHero` | `65D2F111` | action | `—` | player:int, hero:gamelink<Hero> |
| `PlayerSetLighting` | `874086C1` | action | `—` | p:int, light:gamelink<Light>, blendTime:fixed |
| `PlayerSetMount` | `0ECBD142` | action | `—` | player:int, mount:gamelink<Mount> |
| `PlayerSetRace` | `63385694` | action | `—` | player:int, race:gamelink<Race> |
| `PlayerSetSkin` | `D3BCC3BA` | action | `—` | player:int, skin:gamelink<Skin> |
| `PlayerSetSpray` | `E55A662D` | action | `—` | player:int, index:int, spray:gamelink<Spray> |
| `PlayerSetState` | `00000407` | action | `—` | player:int, state:preset, value:preset |
| `PlayerSetToDLighting` | `476B4429` | action | `—` | player:int, light:gamelink<Light> |
| `PlayerSkin` | `785FE78A` | call | `gamelink<Skin>` | p:int |
| `PlayerSpray` | `D7A349CF` | call | `gamelink<Spray>` | p:int, sprayIndex:int |
| `PlayerStartLocation` | `00000151` | call | `point` | p:int |
| `PlayerStatus` | `F1E1DAE1` | call | `preset` | p:int |
| `PlayerType` | `A7BB52AE` | call | `preset` | p:int |
| `PlayerValidateEffectPoint` | `98FD66D2` | call | `int` | caster:int, effect:gamelink<Effect>, point:point |
| `PlayerValidateEffectUnit` | `537BC3B4` | call | `int` | caster:int, effect:gamelink<Effect>, unit:unit |
| `PlayMovieTextureOnUnitActor` | `4CB1474C` | action | `—` | unit:unit, movieTexture:gamelink<Texture> |
| `Point` | `00000022` | call | `point` | x:fixed, y:fixed |
| `PointFacingAngle` | `C53369A7` | call | `point` | point:point, angle:fixed |
| `PointFromName` | `1EA7F07C` | call | `point` | name:string |
| `PointFromPositionAndAngle` | `EF949A7D` | call | `point` | point:point, angle:fixed |
| `PointFromXYZ` | `B097202E` | call | `point` | x:fixed, y:fixed, y2:fixed |
| `PointGetFacing` | `DB4E6196` | call | `fixed` | p:point |
| `PointGetHeight` | `6E03EE18` | call | `fixed` | p:point |
| `PointGetX` | `00000024` | call | `fixed` | p:point |
| `PointGetY` | `00000025` | call | `fixed` | p:point |
| `PointInterpolate` | `53C179FB` | call | `point` | sourcePoint:point, targetPoint:point, fraction:fixed |
| `PointOffsetTowardsPoint` | `E62D9C8C` | call | `point` | sourcePoint:point, distance:fixed, targetPoint:point |
| `PointPathingCliffLevel` | `D88DB594` | call | `fixed` | p1:point |
| `PointPathingCost` | `5A91C75B` | call | `int` | p1:point, p2:point |
| `PointPathingIsConnected` | `6FC6704E` | call | `bool` | p1:point, p2:point |
| `PointPathingPassable` | `8E92E713` | call | `bool` | p1:point |
| `PointReflect` | `E1B8DD31` | call | `point` | sourcePoint:point, targetPoint:point, normalFacing:fixed |
| `PointSet` | `DBF8E9E3` | action | `—` | p:point, pos:point |
| `PointSetFacing` | `6FAF46B4` | action | `—` | p:point, angle:fixed |
| `PointSetHeight` | `51E3F39C` | action | `—` | p:point, height:fixed |
| `PointWithOffset` | `00000023` | call | `point` | p:point, x:fixed, y:fixed |
| `PointWithOffsetPolar` | `00000241` | call | `point` | p:point, dist:fixed, angle:fixed |
| `PointWithZOffset` | `EF33C610` | call | `point` | p:point, z:fixed |
| `PortraitCreate` | `C97BEF46` | action | `—` | offsetX:int, offsetY:int, anchor:preset, width:int, height:int, model:gamelink<Model>, camera:string, animation:modelanim, visible:preset, wait:preset |
| `PortraitDestroy` | `E0086548` | action | `—` | portrait:portrait |
| `PortraitDestroyAll` | `7187830A` | action | `—` | — |
| `PortraitForceTransition` | `28A3BFEE` | action | `—` | Portrait:portrait, onOff:preset, instant:bool |
| `PortraitGetGame` | `DEA2AB06` | call | `portrait` | — |
| `PortraitGetPlanetPanel` | `CDB7964B` | call | `portrait` | — |
| `PortraitGetTriggerControl` | `8F6FB1B4` | call | `portrait` | dialogItem:control |
| `PortraitLastCreated` | `A456D17F` | call | `portrait` | — |
| `PortraitSetActor` | `28A2358F` | action | `—` | Portrait:portrait, actor:gamelink<Actor> |
| `PortraitSetAnim` | `3F7D22D8` | action | `—` | Portrait:portrait, Anim:modelanim, identifier:string, flags:preset, blendTime:fixed |
| `PortraitSetBackgroundVisible` | `497ABB01` | action | `—` | Portrait:portrait, BackgroundVisible:preset |
| `PortraitSetBorderTexture` | `FDA30AFB` | action | `—` | Portrait:portrait, texture:filepath |
| `PortraitSetBorderVisible` | `91DBED38` | action | `—` | Portrait:portrait, BorderVisible:preset |
| `PortraitSetCamera` | `A291ADB0` | action | `—` | Portrait:portrait, Camera:string |
| `PortraitSetChannel` | `70036484` | action | `—` | Portrait:portrait, channel:int |
| `PortraitSetFullscreen` | `7CB54CDD` | action | `—` | Portrait:portrait, Fullscreen:preset |
| `PortraitSetLight` | `A98541DB` | action | `—` | Portrait:portrait, Light:gamelink<Light> |
| `PortraitSetModel` | `67E3C41A` | action | `—` | Portrait:portrait, Model:gamelink<Model>, wait:preset |
| `PortraitSetModelAnim` | `63DDB7B9` | action | `—` | Portrait:portrait, Model:gamelink<Model>, Anim:modelanim, flags:preset, wait:preset |
| `PortraitSetMouseTarget` | `3091096C` | action | `—` | Portrait:portrait, Model:preset |
| `PortraitSetMuted` | `1E66CA03` | action | `—` | Portrait:portrait, muted:bool |
| `PortraitSetOffscreen` | `A70BA1A1` | action | `—` | Portrait:portrait, Fullscreen:preset |
| `PortraitSetPaused` | `177118DA` | action | `—` | Portrait:portrait, paused:bool |
| `PortraitSetPosition` | `DAA86C93` | action | `—` | Portrait:portrait, Anchor:preset, OffsetX:int, OffsetY:int |
| `PortraitSetRenderType` | `42998B50` | action | `—` | Portrait:portrait, renderType:preset |
| `PortraitSetSize` | `DBD462D9` | action | `—` | Portrait:portrait, width:int, height:int |
| `PortraitSetTeamColor` | `A12163AE` | action | `—` | Portrait:portrait, color:color |
| `PortraitSetTintColor` | `07F97D03` | action | `—` | Portrait:portrait, color:color |
| `PortraitSetTransitionModel` | `1888B3BD` | action | `—` | Portrait:portrait, Model:gamelink<Model> |
| `PortraitSetVisible` | `7720F36F` | action | `—` | Portrait:portrait, Players:playergroup, Visible:preset, forceVisible:preset |
| `PortraitUseTransition` | `C15B101F` | action | `—` | Portrait:portrait, Fullscreen:preset |
| `PortraitVisible` | `FE63D1E9` | call | `bool` | portrait:portrait, player:int |
| `PortraitWaitForLoad` | `A5C74E7D` | action | `—` | portrait:portrait |
| `Pow` | `00000013` | call | `fixed` | x:fixed, p:fixed |
| `Pow2` | `F4E34D15` | call | `fixed` | x:fixed |
| `Pow2I` | `3FC99EFC` | call | `int` | x:fixed |
| `PowerIsProvidedBy` | `00000251` | call | `bool` | inPlayer:int, inPosition:point, inSource:unit, inMinLevel:int |
| `PowerIsProvidedBy` | `DB32F733` | call | `bool` | inPlayer:int, inPosition:point, inType:string, inSource:unit, inMinLevel:int |
| `PowerLevel` | `00000250` | call | `int` | inPlayer:int, inPosition:point |
| `PowerLevel` | `2E7FB833` | call | `int` | inPlayer:int, inPosition:point, inType:string |
| `PowI` | `75A93FA3` | call | `int` | x:fixed, p:fixed |
| `PreloadAsset` | `9AD89405` | action | `—` | key:string, queue:preset |
| `PreloadImage` | `E6D9AAFA` | action | `—` | file:filepath, queue:preset |
| `PreloadLayout` | `D7E01477` | action | `—` | file:filepath, queue:preset |
| `PreloadModel` | `35BCE4EA` | action | `—` | file:filepath, queue:preset |
| `PreloadModelAnimation` | `65586447` | action | `—` | file:filepath, queue:preset |
| `PreloadModelObject` | `C31395AC` | action | `—` | id:gamelink<Model>, queue:preset |
| `PreloadMovie` | `C6E357F0` | action | `—` | file:filepath, queue:preset |
| `PreloadObject` | `1EBE8CFF` | action | `—` | catalog:preset, id:string, queue:preset |
| `PreloadScene` | `E6E57D64` | action | `—` | file:string, queue:preset |
| `PreloadScript` | `DEDE37F9` | action | `—` | file:string, queue:preset |
| `PreloadSound` | `304C4EB6` | action | `—` | file:filepath, queue:preset |
| `PreloadSoundLength` | `1FC7FE9B` | action | `—` | info:soundlink |
| `PreloadSoundObject` | `1FDDB65E` | action | `—` | id:gamelink<Sound>, queue:preset |
| `PreloadSoundtrack` | `F2B3CCE5` | action | `—` | soundtrack:gamelink<Soundtrack>, queue:preset |
| `PreloadUnit` | `569DAE66` | action | `—` | unit:gamelink<Unit>, queue:preset |
| `Print` | `3C273629` | call | `actormsg` | string:string |
| `PulseScreenImage` | `BF411FAA` | action | `—` | screenImageID:int, period:fixed, transparency1:fixed, transparency2:fixed |
| `PurchaseCategoryCreate` | `C1C779E3` | action | `—` | Players:playergroup, slot:int |
| `PurchaseCategoryDestroy` | `470143E7` | action | `—` | purchaseCategory:preset |
| `PurchaseCategoryDestroyAll` | `3FCE3192` | action | `—` | players:playergroup |
| `PurchaseCategoryLastCreated` | `D018EB98` | call | `preset` | — |
| `PurchaseCategorySetNameText` | `C08692AC` | action | `—` | purchaseCategory:preset, name:text |
| `PurchaseCategorySetPlayerGroup` | `DD872A7D` | action | `—` | purchaseCategory:preset, players:playergroup |
| `PurchaseCategorySetSlot` | `AFFE905C` | action | `—` | purchaseCategory:preset, slot:int |
| `PurchaseCategorySetState` | `45CABEF1` | action | `—` | purchaseCategory:preset, state:preset |
| `PurchaseGetSelectedPurchaseCategory` | `C0856770` | call | `preset` | player:int |
| `PurchaseGetSelectedPurchaseItem` | `AC531352` | call | `preset` | player:int |
| `PurchaseGroupCreate` | `268A59D3` | action | `—` | Players:playergroup, purchaseCategory:preset, slot:int |
| `PurchaseGroupDestroy` | `B5BF0631` | action | `—` | purchaseGroup:preset |
| `PurchaseGroupDestroyAll` | `746B2F67` | action | `—` | players:playergroup |
| `PurchaseGroupLastCreated` | `5B287BB9` | call | `preset` | — |
| `PurchaseGroupSetIconFilePath` | `26A5030F` | action | `—` | purchaseGroup:preset, iconPath:filepath |
| `PurchaseGroupSetNameText` | `81CFAC3C` | action | `—` | purchaseGroup:preset, text:text |
| `PurchaseGroupSetPlayerGroup` | `93A7B467` | action | `—` | purchaseGroup:preset, players:playergroup |
| `PurchaseGroupSetSlot` | `12B4AED0` | action | `—` | purchaseGroup:preset, slot:int |
| `PurchaseGroupSetState` | `E386DAEA` | action | `—` | purchaseGroup:preset, state:preset |
| `PurchaseGroupSetTooltipText` | `97253AF4` | action | `—` | purchaseGroup:preset, tooltip:text |
| `PurchaseGroupSetUnitLink` | `DB2B20DA` | action | `—` | purchaseGroup:preset, unitLink:gamelink<Unit> |
| `PurchaseItemCreate` | `726B21F9` | action | `—` | Players:playergroup, purchaseGroup:preset, slot:int |
| `PurchaseItemDestroy` | `9D0B4B0F` | action | `—` | purchasableId:int |
| `PurchaseItemDestroyAll` | `42EECC4A` | action | `—` | playerGroupId:playergroup |
| `PurchaseItemIsRecentlyPurchased` | `43342724` | call | `bool` | purchaseItem:preset |
| `PurchaseItemLastCreated` | `5AED7D32` | call | `preset` | — |
| `PurchaseItemPurchase` | `8BFC8A51` | action | `—` | purchaseItem:preset |
| `PurchaseItemSetCost` | `AFF235B3` | action | `—` | purchaseItem:preset, cost:int |
| `PurchaseItemSetDescriptionText` | `8A0C0646` | action | `—` | purchaseItem:preset, description:text |
| `PurchaseItemSetIconFilePath` | `A56B2E60` | action | `—` | purchaseItem:preset, iconPath:filepath |
| `PurchaseItemSetMovieFilePath` | `766BD106` | action | `—` | purchaseItem:preset, movie:filepath |
| `PurchaseItemSetNameText` | `9F10B239` | action | `—` | purchaseItem:preset, name:text |
| `PurchaseItemSetPlayerGroup` | `F082C00E` | action | `—` | purchaseItem:preset, players:playergroup |
| `PurchaseItemSetRecentlyPurchased` | `3BD69BB3` | action | `—` | purchaseItem:preset, recentlyPurchased:bool |
| `PurchaseItemSetSlot` | `0D9F6082` | action | `—` | purchaseItem:preset, slot:int |
| `PurchaseItemSetState` | `36228A26` | action | `—` | purchaseItem:preset, state:preset |
| `PurchaseItemSetTooltipText` | `2CDEF203` | action | `—` | purchaseItem:preset, toolTip:text |
