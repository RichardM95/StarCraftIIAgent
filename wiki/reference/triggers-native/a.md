# SC2 Native Functions: A

Columns are documented in [../triggers-native-functions.md](../triggers-native-functions.md). Reference in XML as `<FunctionDef Type="FunctionDef" Library="Ntve" Id="<ID>"/>`.

Parameter defaults in `nativelib` do not auto-apply; emit an explicit `<Parameter Type="Param" Id="..."/>` for every slot in generated `<FunctionCall>` XML.

### A

<a id="a"></a>

| Name | ID | Kind | Returns | Params |
|---|---|---|---|---|
| `AbilityClass` | `DC731674` | call | `preset` | ability:gamelink<Abil> |
| `AbilityCommand` | `B413B15B` | call | `abilcmd` | ability:gamelink<Abil>, command:int |
| `AbilityCommandGetAbility` | `5EE599E7` | call | `gamelink<Abil>` | abilityCommand:abilcmd |
| `AbilityCommandGetAction` | `5B5E9C2E` | call | `preset` | abilityCommand:abilcmd |
| `AbilityCommandGetCommand` | `9D886DAF` | call | `int` | abilityCommand:abilcmd |
| `AbilityMatchesFilters` | `A23C589A` | call | `bool` | ability:gamelink<Abil>, abilityOwner:int, abilityClass:preset, alias:string |
| `AbsF` | `67AF3393` | call | `fixed` | value:fixed |
| `AbsI` | `0154BFCA` | call | `int` | value:int |
| `AchievementAward` | `3102861D` | action | `—` | p:int, name:gamelink<Achievement> |
| `AchievementErase` | `C96DB672` | action | `—` | p:int, name:gamelink<Achievement> |
| `AchievementPanelSetCategory` | `8874BA0C` | action | `—` | players:playergroup, category:gamelink<Achievement> |
| `AchievementPanelSetVisible` | `3F56BDA5` | action | `—` | players:playergroup, visible:preset |
| `AchievementPercentText` | `E76B043D` | call | `text` | p:int, category:string |
| `AchievementsDisable` | `6C483CBE` | action | `—` | p:int |
| `AchievementsDisabled` | `BF3E5B2A` | call | `bool` | p:int |
| `AchievementTermQuantityAdd` | `A7E74DB9` | action | `—` | player:int, term:gamelink<AchievementTerm>, quantity:int |
| `AchievementTermQuantitySet` | `ACB49AEE` | action | `—` | player:int, term:gamelink<AchievementTerm>, quantity:int |
| `ACos` | `00000019` | call | `fixed` | x:fixed |
| `AcquiredTarget` | `E0DF688F` | call | `unit` | — |
| `ActionDamage` | `667BFCB5` | call | `actormsg` | — |
| `ActionGroup` | `75796BFD` | action | `—` | comment:string +1sub |
| `ActionImpact` | `20C6912A` | call | `actormsg` | — |
| `ActionQueueAdd` | `74DFFAD8` | action | `—` | — +1sub |
| `ActorAddOrientUpdate` | `044A964C` | action | `—` | statusName:string, divisions:int |
| `ActorCreate` | `0165CF77` | action | `—` | actorScope:actorscope, name:gamelink<Actor>, content1:string, content2:string, content3:string |
| `ActorFrom` | `E9B7A1DB` | call | `actor` | name:string |
| `ActorFromActor` | `76B3930A` | call | `actor` | actor:actor, name:string |
| `ActorFromDialogControl` | `51260275` | call | `actor` | dialogItem:control |
| `ActorFromDoodad` | `4D71B0AB` | call | `actor` | doodad:doodad |
| `ActorFromPortrait` | `AEBDE1ED` | call | `actor` | portrait:portrait |
| `ActorFromScope` | `4113F63C` | call | `actor` | actorScope:actorscope, name:string |
| `ActorGetText` | `48D454FB` | call | `text` | actor:actor |
| `ActorLastCreated` | `0F696993` | call | `actor` | — |
| `ActorLastCreatedSend` | `4DA2E9BC` | call | `actor` | — |
| `ActorLookAtStart` | `6CC03970` | action | `—` | source:actor, type:preset, weight:int, time:fixed, target:actor |
| `ActorLookAtStop` | `5952C562` | action | `—` | source:actor, type:preset, weight:int, time:fixed |
| `ActorLookAtTypeStart` | `E501C879` | action | `—` | actor:actor, type:preset, lookAtTarget:actor |
| `ActorLookAtTypeStop` | `62439CDE` | action | `—` | actor:actor, type:preset |
| `ActorRefGet` | `01502763` | call | `actor` | actor:actor, name:string |
| `ActorRefSet` | `70E9151C` | action | `—` | actor:actor, actorRefName:string, actorValue:actor |
| `ActorRegionCreate` | `46B99CA4` | action | `—` | actorScope:actorscope, actorLink:gamelink<Actor>, region:region |
| `ActorRegionSend` | `2F1BA360` | action | `—` | region:actor, intersectType:preset, message:actormsg, classFilters:string, terms:string |
| `ActorRegionSendSimple` | `F96FCAE7` | action | `—` | region:actor, message:actormsg |
| `ActorScopeCreate` | `5C695F56` | action | `—` | actorName:string |
| `ActorScopeFrom` | `A789E91D` | call | `actorscope` | name:string |
| `ActorScopeFromActor` | `D1BC9455` | call | `actorscope` | actor:actor |
| `ActorScopeFromDialogControl` | `C2BD263C` | call | `actorscope` | dialogItem:control |
| `ActorScopeFromPortrait` | `04BEA0F0` | call | `actorscope` | portrait:portrait |
| `ActorScopeFromUnit` | `6DACD0B5` | call | `actorscope` | unit:unit |
| `ActorScopeGetText` | `5AF231D7` | call | `text` | actorScope:actorscope |
| `ActorScopeKill` | `23BF23BF` | action | `—` | actorScope:actorscope |
| `ActorScopeLastCreated` | `F0857987` | call | `actorscope` | — |
| `ActorScopeLastCreatedSend` | `A0C127E0` | call | `actorscope` | — |
| `ActorScopeMoveTo` | `C783209C` | action | `—` | actorScope:actorscope, actor:actor |
| `ActorScopeOrphan` | `06E7C64F` | action | `—` | actorScope:actorscope |
| `ActorScopeSend` | `A51886E9` | action | `—` | actorScope:actorscope, message:actormsg |
| `ActorSend` | `0343B95F` | action | `—` | actor:actor, message:actormsg |
| `ActorSendAsText` | `ECF84383` | action | `—` | actor:actor, message:text |
| `ActorSendTo` | `C8E8FB03` | action | `—` | actor:actor, name:string, message:actormsg |
| `ActorSendToAsText` | `03EC4BB7` | action | `—` | actor:actor, name:string, message:text |
| `ActorTextureGroupApplyGlobal` | `68E7E107` | action | `—` | textureProps:string |
| `ActorTextureGroupPop` | `F25477A9` | action | `—` | — |
| `ActorTextureGroupPush` | `E5AF914B` | action | `—` | — |
| `ActorTextureGroupRemoveGlobal` | `E730CE19` | action | `—` | textureProps:string |
| `ActorWorldParticleFXDestroy` | `1D2DCAF0` | action | `—` | — |
| `AddPlayerGroupToPlayerGroup` | `BA6A2F7E` | action | `—` | sourceGroup:playergroup, targetGroup:playergroup |
| `AddRemoveUIFrameTypeForGlobalFilterList` | `D8594765` | action | `—` | addRemove:preset, frameType:preset |
| `AddUnitGroupToUnitGroup` | `46D30CCC` | action | `—` | sourceUnitGroup:unitgroup, targetUnitGroup:unitgroup |
| `AIAddBully` | `A0089822` | action | `—` | player:int, unitType:gamelink<Unit>, loc:point, rebuildCount:int |
| `AIAttackWaveAddEscortType` | `F172A13B` | action | `—` | player:int, type:gamelink<Unit>, escort:unit, offset:fixed, angle:fixed |
| `AIAttackWaveAddEscortUnit` | `D2D4E17D` | action | `—` | player:int, unit:unit, escort:unit, offset:fixed, angle:fixed |
| `AIAttackWaveAddUnits3` | `897E3B38` | action | `—` | easyCount:int, normalCount:int, hardCount:int, unitType:gamelink<Unit> |
| `AIAttackWaveAddUnits4` | `253D7FAD` | action | `—` | easyCount:int, normalCount:int, hardCount:int, expertCount:int, unitType:gamelink<Unit> |
| `AIAttackWaveAddWaypoint` | `17E6D92B` | action | `—` | player:int, waypoint:point, useTransport:preset |
| `AIAttackWaveCancel` | `232935FA` | action | `—` | wave:wave |
| `AIAttackWaveSend` | `3A0403D0` | action | `—` | player:int, time:int, wait:preset |
| `AIAttackWaveSetGatherEarlyNoReplace` | `D59531F5` | action | `—` | player:int |
| `AIAttackWaveSetGatherPoint` | `D92EAFA7` | action | `—` | player:int, gatherPoint:point |
| `AIAttackWaveSetKeepAlive` | `42C5413B` | action | `—` | player:int |
| `AIAttackWaveSetTargetEscort` | `5EB3E17A` | action | `—` | player:int, escortGroup:unitgroup, replaceType:preset |
| `AIAttackWaveSetTargetEscortNL` | `B2CAB822` | action | `—` | player:int, escortGroup:unitgroup, replaceType:preset |
| `AIAttackWaveSetTargetGatherD` | `6FF5F733` | action | `—` | player:int, town:int |
| `AIAttackWaveSetTargetGatherO` | `C0C71187` | action | `—` | player:int, town:int |
| `AIAttackWaveSetTargetMelee` | `27FDA8F2` | action | `—` | player:int |
| `AIAttackWaveSetTargetMeleeHarass` | `AE456797` | action | `—` | player:int |
| `AIAttackWaveSetTargetMerge` | `C0B9F82E` | action | `—` | player:int, wave:wave |
| `AIAttackWaveSetTargetPatrol` | `4A81E03B` | action | `—` | player:int, replaceType:preset |
| `AIAttackWaveSetTargetPlayer` | `3955F80B` | action | `—` | player:int, playerMask:playergroup |
| `AIAttackWaveSetTargetPoint` | `12E81501` | action | `—` | player:int, point:point |
| `AIAttackWaveSetTargetRegion` | `AA60F62B` | action | `—` | player:int, region:region, replaceType:preset |
| `AIAttackWaveSetTargetUnit` | `46F660D9` | action | `—` | player:int, unitTag:unit |
| `AIAttackWaveSetTargetUnitGroup` | `A1970AD2` | action | `—` | player:int, unitGroup:unitgroup |
| `AIAttackWaveSetTargetUnitPoint` | `EC3358BD` | action | `—` | player:int, unitTag:unit |
| `AIAttackWaveUseGroup` | `D16912F9` | action | `—` | player:int, unitGroup:unitgroup |
| `AIAttackWaveUseUnit` | `2811FB0A` | action | `—` | player:int, unit:unit |
| `AIBaseThink` | `23421792` | action | `—` | unit:unit, candidates:unitgroup |
| `AIBestTargetPoint` | `E9CE6B42` | call | `point` | group:unitgroup, minHits:int, damageBase:int, minScore:fixed, radius:fixed, from:point, range:fixed, bonusAttribute:int |
| `AIBuild` | `136B709A` | action | `—` | player:int, priority:int, town:int, unitType:gamelink<Unit>, count:int, flags:int |
| `AICampaignStart` | `E2E35DF6` | action | `—` | player:int |
| `AICast` | `1DFB2458` | action | `—` | unit:unit, order:order |
| `AICast` | `FB5C6DA7` | action | `—` | unit:unit, order:order, marker:marker, retreat:bool |
| `AICastFlee` | `B3F00FBD` | action | `—` | who:unit, from:unit, distance:int, marker:marker |
| `AIClearAllBullies` | `CD05E06B` | action | `—` | player:int |
| `AIClearBuildQueue` | `B9F8937C` | action | `—` | player:int |
| `AIClearCloakedAttacker` | `13AC02CC` | action | `—` | player:int, point:point |
| `AIClearResearchQueue` | `8B786E6C` | action | `—` | player:int |
| `AIClearStock` | `D6FE8683` | action | `—` | player:int |
| `AIClearTrainQueue` | `80A883C0` | action | `—` | player:int |
| `AICombatDiffFlagCatSortBuildingsPrio` | `66289439` | call | `bool` | player:int, action:preset |
| `AICombatDiffFlagCatSpecialHighPrio` | `80DAD37A` | call | `bool` | player:int, action:preset |
| `AICombatDiffFlagCatSplashHighPrio` | `01EA83D3` | call | `bool` | player:int, action:preset |
| `AICombatDiffFlagCatTimedLowPrio` | `C709A5B8` | call | `bool` | player:int, action:preset |
| `AICombatDiffFlagCatWorkersNormalPrio` | `737DE073` | call | `bool` | player:int, action:preset |
| `AICombatDiffFlagTieBreakBonusDamage` | `929F17F7` | call | `bool` | player:int, action:preset |
| `AICombatDiffFlagTieBreakDetector` | `08431739` | call | `bool` | player:int, action:preset |
| `AICombatDiffFlagTieBreakHealers` | `BCD227ED` | call | `bool` | player:int, action:preset |
| `AICombatDiffFlagTieBreakInjured` | `07737A02` | call | `bool` | player:int, action:preset |
| `AICombatDiffFlagTieBreakLowHP` | `367F839E` | call | `bool` | player:int, action:preset |
| `AICombatDiffFlagTieBreakRange` | `301FA66C` | call | `bool` | player:int, action:preset |
| `AIControlWantsToMove` | `3D360D90` | call | `bool` | unit:unit |
| `AIDeclareTown` | `4DC893FD` | action | `—` | player:int, town:int, center:point |
| `AIDefaultCombatPriority` | `8198A5A9` | call | `unit` | attackers:unitgroup, enemies:unitgroup, maxAttackersLimit:int |
| `AIDefaultEconomy` | `891D2DCA` | action | `—` | player:int, townHall:gamelink<Unit>, refinery:gamelink<Unit>, food:string, peon:string, cap:int, peonMode:bool |
| `AIDefaultExpansion` | `CBAA7BFC` | action | `—` | player:int, townHall:gamelink<Unit>, minerals:int, gas:int, flags:int |
| `AIDefaultGetFirstMissingReq` | `6D09502F` | call | `string` | player:int, object:string |
| `AIDefaultGetFirstUnfinishedReq` | `03915715` | call | `string` | player:int, object:string |
| `AIDefaultGetFullMakeTime` | `522AA4A2` | call | `int` | player:int, object:string |
| `AIDefaultGetMaker` | `1CC9B0A2` | call | `string` | player:int, object:string |
| `AIDefaultGetObjectType` | `D02CF6A0` | call | `int` | player:int, object:string |
| `AIEnableStock` | `9F4A5938` | action | `—` | player:int |
| `AIEvalRatio` | `86903CA2` | call | `int` | player:int |
| `AIEvalSetCustomIndex` | `613DD983` | action | `—` | index:int |
| `AIExecuteAbilTactical` | `87E66217` | action | `—` | unit:unit, scrip:string, scanGroup:unitgroup, ability:gamelink<Abil>, item:unit |
| `AIExpand` | `53D30B3F` | call | `int` | player:int, point:point, building:gamelink<Unit> |
| `AIFilter` | `A8AB1B4D` | call | `aifilter` | player:int |
| `AIFindUnits` | `124D7CB6` | call | `unitgroup` | player:int, unitType:string, centerPoint:point, withinRange:fixed, maxCount:int |
| `AIGetAllEscorts` | `C6DD8D08` | call | `unitgroup` | unit:unit |
| `AIGetAllEscortsGroup` | `A7431889` | call | `unitgroup` | unitGroup:unitgroup |
| `AIGetBaseName` | `ACA3819C` | call | `string` | objectString:string |
| `AIGetBestTarget` | `B00BA8E5` | call | `point` | player:int, enemies:playergroup, gatherPoint:point, flags:preset |
| `AIGetBuildAtName` | `CA3522F4` | call | `string` | objectString:string |
| `AIGetBuildingCountInTown` | `6BA2288F` | call | `int` | player:int, town:int, unit:gamelink<Unit>, countMask:preset |
| `AIGetBuildingPlacement` | `70EA8615` | call | `point` | player:int, center:point, unitType:gamelink<Unit>, buildFlags:int |
| `AIGetCloakedAttacker` | `927B2EC7` | call | `point` | player:int |
| `AIGetClosestTown` | `73D79FC7` | call | `int` | player:int, location:point |
| `AIGetCoopFlag` | `D21221AD` | call | `bool` | player:int, index:int |
| `AIGetCurPeonCount` | `88299C13` | call | `int` | player:int, town:int |
| `AIGetDefaultBuildFlags` | `55F11088` | call | `int` | player:int, buildingType:string |
| `AIGetDifficulty` | `D50EF6A5` | call | `bool` | player:int, index:preset |
| `AIGetFilterGroup` | `4B9AE2C2` | call | `unitgroup` | filter:aifilter, candidates:unitgroup |
| `AIGetFirstMissingReq` | `7407844C` | call | `string` | player:int, object:string |
| `AIGetFirstUnfinishedReq` | `D096667E` | call | `string` | player:int, object:string |
| `AIGetFlag` | `A5F3A30C` | call | `bool` | player:int, index:int |
| `AIGetFullMakeTime` | `0D425579` | call | `int` | player:int, object:string |
| `AIGetGasAmountLeft` | `4CF8BD14` | call | `int` | player:int, town:int |
| `AIGetGatherDefLocation` | `0CE536BB` | call | `point` | player:int, town:int |
| `AIGetGatherLocation` | `7E2BDC46` | call | `point` | player:int, town:int |
| `AIGetMaker` | `B9E6CE90` | call | `string` | player:int, object:string |
| `AIGetMaxPeonCount` | `1E835C46` | call | `int` | player:int, town:int |
| `AIGetMineralAmountLeft` | `ED658714` | call | `int` | player:int, town:int |
| `AIGetMineralNumSpots` | `6BCD444B` | call | `int` | player:int, town:int |
| `AIGetMinPeonCount` | `00F8536E` | call | `int` | player:int, town:int |
| `AIGetNextScoutLoc` | `CA5B980A` | call | `point` | player:int |
| `AIGetNextUnusedTownSlot` | `E48E495F` | call | `int` | player:int |
| `AIGetObjectType` | `C672F322` | call | `int` | player:int, object:string |
| `AIGetRawGasNumSpots` | `3AD70FB4` | call | `int` | player:int, town:int |
| `AIGetScout` | `CF51BA45` | call | `unit` | player:int, indexSlot:int, previousUnit:unit |
| `AIGetTime` | `8BDC6216` | call | `fixed` | — |
| `AIGetTownLocation` | `F2A576A6` | call | `point` | player:int, town:int |
| `AIGetTownState` | `9418322D` | call | `int` | player:int, town:int |
| `AIGetTownThreats` | `64C44D41` | call | `unitgroup` | player:int, town:int |
| `AIGetUnitsInWavesWithTarget` | `1E3BDBCF` | call | `unitgroup` | player:int, waveTarget:wavetarget |
| `AIGivingUp` | `C74452B4` | call | `bool` | player:int |
| `AIGlobalSuicide` | `6829CA57` | action | `—` | player:int |
| `AIGoodGame` | `C26CAC0E` | action | `—` | player:int |
| `AIGrabUnit` | `6907D2C0` | call | `unit` | player:int, unitType:string, priority:int, location:point |
| `AIHarvest` | `A3F78565` | action | `—` | player:int, town:int |
| `AIHarvestRate` | `411A8BD2` | action | `—` | player:int, amount:int |
| `AIHasRes` | `BB7112C9` | call | `bool` | player:int, minerals:int, gas:int |
| `AIInitCampaignHarvest` | `B65D30F7` | action | `—` | player:int |
| `AIInitCampaignTowns` | `A27E3181` | action | `—` | player:int |
| `AIIsCampaign` | `CE113DDF` | call | `bool` | player:int |
| `AIIsIgnoredByWave` | `F9D17330` | call | `bool` | unit:unit |
| `AIIsNotUsableInWaves` | `B4B744A5` | call | `bool` | unit:unit |
| `AIIsScriptControlled` | `2D900E1C` | call | `bool` | unit:unit |
| `AIIsSuicideUnit` | `F2F49F9B` | call | `bool` | unit:unit |
| `AIIsTacticalDisabled` | `AF001F41` | call | `bool` | unit:unit |
| `AIIsTownHarvestRunning` | `054F17DD` | call | `bool` | player:int, town:int |
| `AIKnownUnitCount` | `91DE7A68` | call | `int` | player:int, otherPlayer:int, unitType:gamelink<Unit> |
| `AILaneWaypointAdd` | `84571FC9` | action | `—` | lane:int, waypoint:point |
| `AILaneWaypointCalcClosestDataForLane` | `1C4095AE` | action | `—` | testLane:int, testPoint:point |
| `AILaneWaypointClearAll` | `129C4A8B` | action | `—` | — |
| `AILaneWaypointGetCalcDataClosestDist` | `935BC487` | call | `fixed` | — |
| `AILaneWaypointGetCalcDataClosestPoint` | `372F1C16` | call | `point` | — |
| `AILaneWaypointGetCalcDataClosestWaypointIndex` | `6E450624` | call | `int` | — |
| `AILaneWaypointGetCalcDataSecondWaypointIndex` | `25652AB5` | call | `int` | — |
| `AILaneWaypointGetClosestLane` | `B592FDBF` | call | `int` | testPoint:point |
| `AILastAttack` | `9B939290` | call | `int` | unit:unit |
| `AILastAttacker` | `44C3372B` | call | `unit` | unit:unit |
| `AIMakeAlways` | `CEB6863E` | action | `—` | player:int, priority:int, town:int, objectType:string, count:int |
| `AIMakeOnce` | `1BE799E9` | action | `—` | player:int, priority:int, town:int, objectType:string, count:int |
| `AIMarker` | `6E721C10` | call | `marker` | unit:unit, name:string |
| `AIMeleeStart` | `5DB8FF7D` | action | `—` | player:int |
| `AINearestTownBullyRebuild` | `5C676F69` | action | `—` | player:int, enable:preset |
| `AINearestTownLimitWaveGather` | `A92A2CD2` | action | `—` | player:int, enable:preset |
| `AIPathingCostMap` | `897BC1F9` | call | `int` | from:point, to:point |
| `AIPathingCostUnit` | `E80D1B4D` | call | `int` | unit:unit, to:point, type:preset |
| `AIRandomSpawnPoint` | `2445C07B` | call | `point` | player:int, region:region, minDistFromEnemies:fixed, maxDistFromEnemies:fixed, maxDistFromBuildings:fixed |
| `AIReleaseUnit` | `8676426B` | action | `—` | unit:unit |
| `AIRemoveGroupFromAnyWaves` | `2DD3364B` | action | `—` | group:unitgroup |
| `AIRemoveGroupFromAnyWavesAndSetHome` | `663AAFD7` | action | `—` | group:unitgroup, home:point |
| `AIRemoveUnitFromAnyWaves` | `6A5E7D21` | action | `—` | unit:unit |
| `AIRemoveUnitFromAnyWavesAndSetHome` | `858C1FB1` | action | `—` | unit:unit, home:point |
| `AIReqCountAsBuiltObject` | `48519E3B` | action | `—` | player:int, unit:gamelink<Unit> |
| `AIResearch` | `94C71F93` | action | `—` | player:int, priority:int, town:int, upgradeType:gamelink<Upgrade> |
| `AIResetBullyRebuildCountsInRegion` | `D688C655` | action | `—` | player:int, region:region |
| `AISameCommand` | `89527ECA` | call | `bool` | firstUnit:unit, secondUnit:unit |
| `AIScout` | `C82B8202` | action | `—` | player:int |
| `AISelfReinforceDropPoint` | `B36CF3A0` | call | `point` | player:int |
| `AISetAllStates` | `8D62B174` | action | `—` | player:int, state:int |
| `AISetAPM` | `0406AF36` | action | `—` | player:int, aPM:int |
| `AISetBullyAttackWavePercent` | `A55BF7C8` | action | `—` | percent:int, player:int |
| `AISetBullyRebuildDelay` | `4714FAB1` | action | `—` | minDelay:fixed, maxDelay:fixed, player:int |
| `AISetCoopFlag` | `B3E923C4` | action | `—` | player:int, index:int, state:bool |
| `AISetDefenseRadii` | `8E970633` | action | `—` | player:int, maxThreatingRange:fixed, buildingCallForHelpRange:fixed, threatCallForHelpRange:fixed |
| `AISetDifficulty` | `C3EC8366` | action | `—` | player:int, index:preset, state:preset |
| `AISetFilterAlliance` | `05CAB88A` | action | `—` | filter:aifilter, alliance:preset |
| `AISetFilterBits` | `0ED83E6C` | action | `—` | filter:aifilter, unitFilter:unitfilter |
| `AISetFilterEnergy` | `F5C599A6` | action | `—` | filter:aifilter, min:fixed, max:fixed |
| `AISetFilterInCombat` | `1E6DFAFD` | action | `—` | filter:aifilter, inCombat:preset |
| `AISetFilterLife` | `7C978DF1` | action | `—` | filter:aifilter, min:fixed, max:fixed |
| `AISetFilterLifeLost` | `226407B8` | action | `—` | filter:aifilter, min:fixed, max:fixed |
| `AISetFilterLifeMod` | `D20ABCFC` | action | `—` | filter:aifilter, attribute:preset, amount:fixed |
| `AISetFilterLifePerMarker` | `3E80483C` | action | `—` | filter:aifilter, each:fixed, marker:marker |
| `AISetFilterLifeSortReference` | `2C3ABB83` | action | `—` | filter:aifilter, vitality:fixed, threshold:fixed |
| `AISetFilterMarker` | `B2DCD6C2` | action | `—` | filter:aifilter, min:int, max:int, marker:marker |
| `AISetFilterMelee` | `0ACB9EB9` | action | `—` | filter:aifilter, inCombat:preset |
| `AISetFilterPlane` | `408AB1E3` | action | `—` | filter:aifilter, plane:preset |
| `AISetFilterRange` | `D14651C4` | action | `—` | filter:aifilter, aroundUnit:unit, radius:fixed |
| `AISetFilterSelf` | `C66E506F` | action | `—` | filter:aifilter, self:unit |
| `AISetFilterShields` | `BB3B2A79` | action | `—` | filter:aifilter, min:fixed, max:fixed |
| `AISetFlag` | `8F2500FF` | action | `—` | player:int, index:int, state:bool |
| `AISetGasPeonCountOverride` | `BB9C147B` | action | `—` | player:int, town:int, desiredPeonCount:int |
| `AISetGeneralRebuildCount` | `7F2D83FF` | action | `—` | count:int, building:preset, player:int |
| `AISetGroupNotUsableInWaves` | `6D8D747A` | action | `—` | group:unitgroup, controlled:preset |
| `AISetGroupScriptControlled` | `DDB3F038` | action | `—` | group:unitgroup, controlled:preset |
| `AISetGroupSuicide` | `A8F7E9C5` | action | `—` | group:unitgroup, controlled:preset |
| `AISetGroupTacticalDisabled` | `662F6F4F` | action | `—` | group:unitgroup, controlled:preset |
| `AISetIgnoredByWave` | `6B6A38DD` | action | `—` | unit:unit, enable:preset |
| `AISetMainTown` | `642520EE` | action | `—` | player:int, mainTown:int |
| `AISetMinimumBullyCount` | `E916DC36` | action | `—` | count:int, unitType:gamelink<Unit>, player:int |
| `AISetNumScouts` | `DE1A962E` | action | `—` | player:int, num:int |
| `AISetScoutTimes` | `328F6584` | action | `—` | player:int, startLocationTime:int, obstructedTime:int, mineralsTime:int, generalTime:int |
| `AISetSpecificRebuildCount` | `FAF78B95` | action | `—` | count:int, unitType:gamelink<Unit>, player:int |
| `AISetSpecificState` | `59EB7D4A` | action | `—` | player:int, index:int, state:int |
| `AISetStock` | `0DD50612` | action | `—` | player:int, count:int, unitType:gamelink<Unit> |
| `AISetStockAlias` | `93E5F5FD` | action | `—` | player:int, count:int, unitType:gamelink<Unit>, aliasType:string |
| `AISetStockEx` | `2D993BDF` | action | `—` | player:int, town:int, count:int, unitType:gamelink<Unit>, buildFlags:int, stockFlags:int |
| `AISetStockExpand` | `9304C879` | action | `—` | player:int, townHall:gamelink<Unit>, count:int |
| `AISetStockFree` | `8B505342` | action | `—` | player:int, count:int, unitType:gamelink<Unit>, prereq:string |
| `AISetStockOpt` | `700EC30F` | action | `—` | player:int, count:int, unitType:gamelink<Unit> |
| `AISetStockTown` | `EF7E05B0` | action | `—` | player:int, townHall:gamelink<Unit>, refinery:gamelink<Unit> |
| `AISetStockUnitNext` | `C97424F4` | action | `—` | player:int, count:int, unitType:gamelink<Unit>, ignoreIfQueued:bool |
| `AISetUnitNotUsableInWaves` | `14110193` | action | `—` | unit:unit, controlled:preset |
| `AISetUnitScriptControlled` | `AA8C27B5` | action | `—` | unit:unit, controlled:preset |
| `AISetUnitSuicide` | `6ADF6634` | action | `—` | unit:unit, controlled:preset |
| `AISetUnitTacticalDisabled` | `053E17EE` | action | `—` | unit:unit, controlled:preset |
| `AIStart` | `00000323` | action | `—` | player:int, mode:preset, APM:int |
| `AIState` | `701F3006` | call | `int` | player:int, index:int |
| `AITechCount` | `E40B4D3C` | call | `int` | player:int, unitType:gamelink<Unit>, countMask:preset |
| `AITechFlag` | `DB0E6ABB` | action | `—` | player:int, index:int, count:int, what:string, state:int |
| `AITimeIsPaused` | `D59E1980` | call | `bool` | — |
| `AITimePause` | `BC622053` | action | `—` | pause:preset |
| `AIToggleBulliesInRegion` | `5FF15420` | action | `—` | player:int, region:region, activate:preset |
| `AITrain` | `C89E24A9` | action | `—` | player:int, priority:int, town:int, unitType:gamelink<Unit>, count:int |
| `AITransportDisableAutoPickup` | `ACD579FA` | action | `—` | player:int |
| `AITransportSetPanic` | `0A90C548` | action | `—` | player:int, value:fixed |
| `AITransportSetReturn` | `571DFD8F` | action | `—` | player:int, location:point |
| `AIUnitGetWave` | `869F0576` | call | `wave` | unit:unit |
| `AIUnitGroupGetValidOrder` | `1E7DE62A` | call | `order` | unitGroup:unitgroup, inOrder:order, caster:unit, forward:bool |
| `AIUnitIsInCombat` | `D2E1DC04` | call | `bool` | unit:unit |
| `AIWaveAddUnit` | `00000265` | action | `—` | wave:wave, unit:unit |
| `AIWaveAddUnitPriority` | `9C13A2D1` | action | `—` | wave:wave, unit:unit, priority:int |
| `AIWaveCreate` | `00000263` | call | `wave` | waveInfo:waveinfo, player:int, stagingPoint:point |
| `AIWaveDelete` | `12E45E26` | action | `—` | w:wave |
| `AIWaveEval` | `012B787C` | call | `int` | waveRef:wave |
| `AIWaveEvalRatio` | `29AF608A` | call | `int` | waveRef:wave, range:fixed |
| `AIWaveGet` | `B9BB6748` | call | `wave` | player:int, waveIndex:int |
| `AIWaveGetTarget` | `CA8628B0` | call | `wavetarget` | wave:wave |
| `AIWaveGetTimeInCombat` | `631074E7` | call | `int` | waveRef:wave |
| `AIWaveGetTimeSinceCombat` | `F9BAA257` | call | `int` | waveRef:wave |
| `AIWaveGetTimeSinceOrdered` | `BD3A49F3` | call | `int` | waveRef:wave |
| `AIWaveGetUnits` | `434CFCE2` | call | `unitgroup` | wave:wave |
| `AIWaveHarassRetreat` | `3B948B04` | call | `wavetarget` | player:int, wave:wave, range:fixed |
| `AIWaveInfo` | `F7F93AB0` | call | `waveinfo` | wave:wave |
| `AIWaveInfoAdd` | `9FD9132C` | action | `—` | waveInfo:waveinfo, unitType:string, count:int |
| `AIWaveInfoAttack` | `5A29FC42` | action | `—` | waveInfo:waveinfo, player:int, from:point, target:wavetarget, time:int |
| `AIWaveInfoCreate` | `00000264` | call | `waveinfo` | — |
| `AIWaveInfoSuicide` | `00000363` | action | `—` | waveInfo:waveinfo, player:int, from:point, target:wavetarget, time:int |
| `AIWaveIsInCombat` | `864A13AD` | call | `bool` | waveRef:wave |
| `AIWaveMerge` | `EEC9FC53` | action | `—` | player:int, waveFrom:int, waveInto:int |
| `AIWaveRemoveUnit` | `D29C2D5E` | action | `—` | wave:wave, unit:unit |
| `AIWaveSet` | `974C796D` | action | `—` | player:int, waveName:int, wave:wave |
| `AIWaveSetType` | `F8C91F07` | action | `—` | wave:wave, type:int, target:wavetarget |
| `AIWaveState` | `5D9D7313` | call | `int` | waveRef:wave |
| `AIWaveTargetAddWaypoint` | `1921CDD9` | action | `—` | target:wavetarget, waypoint:point, useTransport:preset, index:int |
| `AIWaveTargetClearWaypoints` | `E95AC0AF` | action | `—` | wt:wavetarget |
| `AIWaveTargetEscort` | `C55EEFBE` | call | `wavetarget` | unitGroup:unitgroup, replaceType:preset |
| `AIWaveTargetEscortNL` | `C6F10828` | call | `wavetarget` | unitGroup:unitgroup, replaceType:preset |
| `AIWaveTargetGatherD` | `B947254E` | call | `wavetarget` | player:int, town:int |
| `AIWaveTargetGatherO` | `148F1F3E` | call | `wavetarget` | player:int, town:int |
| `AIWaveTargetMelee` | `4A9D2A1A` | call | `wavetarget` | player:int |
| `AIWaveTargetMeleeHarass` | `6E3A8C34` | call | `wavetarget` | player:int |
| `AIWaveTargetMerge` | `225660B8` | call | `wavetarget` | wave:wave |
| `AIWaveTargetPatrol` | `C9555AF8` | call | `wavetarget` | replaceType:preset |
| `AIWaveTargetPlayer` | `00000362` | call | `wavetarget` | player:playergroup |
| `AIWaveTargetPoint` | `444891AA` | call | `wavetarget` | p:point |
| `AIWaveTargetRegion` | `09C84766` | call | `wavetarget` | region:region, replaceType:preset |
| `AIWaveTargetUnit` | `00000268` | call | `wavetarget` | unit:unit |
| `AIWaveTargetUnitGroup` | `29EBBD36` | call | `wavetarget` | unitGroup:unitgroup |
| `AIWaveTargetUnitPoint` | `00000267` | call | `wavetarget` | unit:unit |
| `AIWaveToString` | `CFA36FEA` | call | `string` | w:wave |
| `AIWaveToText` | `BBEA4D1B` | call | `text` | w:wave |
| `AIWaveType` | `80D47188` | call | `int` | waveRef:wave |
| `AIWaveUnitCount` | `D2E12783` | call | `int` | w:wave |
| `AliasAdd` | `8CE9D5F5` | call | `actormsg` | alias:string |
| `AliasRemove` | `511FEFCC` | call | `actormsg` | alias:string |
| `AlliesEnemiesOfPlayerCountInactiveAndSelf` | `1B53B94F` | call | `playergroup` | alliance:preset, player:int |
| `And` | `00000132` | ? | `—` | — +1sub |
| `AndOr` | `00000135` | call | `bool` | val1:bool, op:preset, val2:bool |
| `AndOrMult` | `00000134` | call | `bool` | op:preset, val:bool |
| `AndOrMult2` | `C879D158` | call | `bool` | value:bool |
| `AngleBetweenPoints` | `00000026` | call | `fixed` | p1:point, p2:point |
| `AnimBaselineStart` | `91D998DE` | call | `actormsg` | — |
| `AnimBaselineStop` | `0B0D7DF0` | call | `actormsg` | — |
| `AnimBlendTimeApply` | `58A0FCE5` | call | `actormsg` | blendTime:fixed |
| `AnimBlendTimeRemove` | `6DA18A65` | call | `actormsg` | — |
| `AnimClear` | `9E701E85` | call | `actormsg` | animName:string, blendTime:fixed |
| `AnimClearAllBut` | `F9CD403E` | call | `actormsg` | animName:string, blendTime:fixed |
| `AnimDumpDB` | `9D857F1C` | call | `actormsg` | — |
| `AnimGroupRemoveAll` | `AEC5207F` | call | `actormsg` | — |
| `AnimLengthQueryByName` | `27719FBE` | action | `—` | actor:actor, identifier:string, getScaledTime:bool |
| `AnimLengthQueryByProps` | `43A613E5` | action | `—` | actor:actor, animProps:modelanim |
| `AnimLengthQueryLastCreated` | `AF2CA536` | call | `animlengthquery` | — |
| `AnimLengthQueryWait` | `90A266F3` | action | `—` | — |
| `AnimLengthRemainingSync` | `A7B1D22F` | call | `fixed` | handle:animlengthquery |
| `AnimLengthSync` | `B07868B5` | call | `fixed` | handle:animlengthquery |
| `AnimPlaySequence` | `65F2B34D` | call | `actormsg` | animName:string, sequenceList:string |
| `AnimSetCompletion` | `FB6A1C18` | call | `actormsg` | animName:string, percent:fixed |
| `AnimSetDuration` | `6E7FC0EB` | call | `actormsg` | animName:string, duration:fixed |
| `AnimSetPaused` | `44B7EA9B` | call | `actormsg` | pause:preset |
| `AnimSetTime` | `0237F8A4` | call | `actormsg` | animName:string, time:fixed, scaled:bool |
| `AnimSetTimeScale` | `B1F81BE5` | call | `actormsg` | animName:string, scale:fixed |
| `AnimSetTimeScaleGlobal` | `95693EFD` | call | `actormsg` | value:fixed |
| `AnimWait` | `65BF0787` | action | `—` | actor:actor, identifier:string, offset:fixed, offsetType:preset |
| `ArithmeticInt` | `00000128` | call | `int` | val1:int, op:preset, val2:int |
| `ArithmeticInt2` | `7D16A215` | call | `int` | val1:int, op:preset, val2:int |
| `ArithmeticIntClamp` | `81737707` | call | `int` | value:int, min:int, max:int |
| `ArithmeticIntMult` | `00000126` | call | `int` | op:preset, val:int |
| `ArithmeticIntMult2` | `D3C80FAD` | call | `int` | op:preset, val:int |
| `ArithmeticReal` | `00000129` | call | `fixed` | val1:fixed, op:preset, val2:fixed |
| `ArithmeticRealClamp` | `32F302DF` | call | `fixed` | value:fixed, min:fixed, max:fixed |
| `ArithmeticRealMult` | `00000127` | call | `fixed` | op:preset, val:fixed |
| `ASin` | `00000018` | call | `fixed` | x:fixed |
| `ATan` | `00000020` | call | `fixed` | x:fixed |
| `ATan2` | `00000021` | call | `fixed` | y:fixed, x:fixed |
| `AttachActorToActor` | `80B0856C` | action | `—` | hostingActor:actor, attachingActor:gamelink<Actor>, attachPoint:preset |
| `AttachActorToUnit` | `57380ECA` | action | `—` | unit:unit, actor:gamelink<Actor>, attachPoint:preset |
| `AttachModelToActor` | `2F0D3EEE` | action | `—` | actor:actor, model:gamelink<Model>, attachPoint:preset |
| `AttachModelToActor2` | `1B1310D9` | action | `—` | actor:actor, model:gamelink<Model>, attachPoint:preset |
| `AttachModelToUnit` | `3A43F8C8` | action | `—` | unit:unit, model:gamelink<Model>, attachPoint:preset |
| `AttachModelToUnitInheritVisibility` | `E5916D67` | action | `—` | unit:unit, model:gamelink<Model>, attachPoint:preset |
| `AttachSetBearings` | `C358BFC4` | call | `actormsg` | attachMethods:string, bearings:string |
| `AttachSetBearingsFrom` | `E59EA897` | call | `actormsg` | attachMethods:string, actorName:string, actorSiteOps:string |
| `AttachSetPosition` | `6C5ACBFE` | call | `actormsg` | attachMethods:string, position:string |
| `AttachSetPositionFrom` | `68765003` | call | `actormsg` | attachMethods:string, actorName:string, actorSiteOps:string |
| `AttachSetRotation` | `1B030597` | call | `actormsg` | attachMethods:string, rotation:fixed |
| `AttachSetRotationFrom` | `B2D07F84` | call | `actormsg` | attachMethods:string, actorName:string, actorSiteOps:string |
