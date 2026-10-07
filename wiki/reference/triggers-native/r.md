# SC2 Native Functions: R

Columns are documented in [../triggers-native-functions.md](../triggers-native-functions.md). Reference in XML as `<FunctionDef Type="FunctionDef" Library="Ntve" Id="<ID>"/>`.

Parameter defaults in `nativelib` do not auto-apply; emit an explicit `<Parameter Type="Param" Id="..."/>` for every slot in generated `<FunctionCall>` XML.

### R

<a id="r"></a>

| Name | ID | Kind | Returns | Params |
|---|---|---|---|---|
| `RandomAngle` | `D1C924E4` | call | `fixed` | — |
| `RandomFixed` | `00000196` | call | `fixed` | min:fixed, max:fixed |
| `RandomInt` | `00000195` | call | `int` | min:int, max:int |
| `RandomPercent` | `2D29A1C5` | call | `fixed` | — |
| `RandomPointBetweenPoints` | `3424196B` | call | `point` | point1:point, point2:point |
| `RefClear` | `A804684B` | call | `actormsg` | actorRefName:string |
| `RefDestroy` | `31123B1B` | call | `actormsg` | actorRefName:string |
| `RefDump` | `AFF0AFBF` | call | `actormsg` | actorRefName:string |
| `RefNotify` | `EC390E46` | call | `actormsg` | actorRefName:string, subName:string |
| `RefreshBossBar` | `A0768E88` | action | `—` | bossBarID:int |
| `RefSet` | `AD353D8C` | call | `actormsg` | actorRefName:string, refSource:string |
| `RefSetFromActor` | `E672DFB5` | call | `actormsg` | actorRefName:string, refPrimary:string, refSecondary:string |
| `RefSetFromMsg` | `AFECF7B1` | call | `actormsg` | actorRefName:string, message:string |
| `RefSetRefreshName` | `E425C4B1` | call | `actormsg` | actorRefName:string, refreshName:string |
| `RegionAddCircle` | `00000032` | action | `—` | r:region, state:preset, c:point, rad:fixed |
| `RegionAddRect` | `00000031` | action | `—` | r:region, state:preset, minx:fixed, miny:fixed, maxx:fixed, maxy:fixed |
| `RegionAddRegion` | `00000033` | action | `—` | r:region, toAdd:region |
| `RegionAttachToUnit` | `1E29721A` | action | `—` | region:region, unit:unit, offset:point |
| `RegionCircle` | `00000030` | call | `region` | c:point, r:fixed |
| `RegionContainsPoint` | `00000036` | call | `bool` | r:region, p:point |
| `RegionEmpty` | `00000028` | call | `region` | — |
| `RegionEntireMap` | `00000356` | call | `region` | — |
| `RegionFromName` | `0936F71D` | call | `region` | name:string |
| `RegionGetAttachUnit` | `51FCDFC1` | call | `unit` | r:region |
| `RegionGetBoundsMax` | `00000038` | call | `point` | r:region |
| `RegionGetBoundsMin` | `00000037` | call | `point` | r:region |
| `RegionGetCenter` | `00000039` | call | `point` | r:region |
| `RegionPlayableMap` | `46F2D5B8` | call | `region` | — |
| `RegionPlayableMapSet` | `9AD8B4CA` | action | `—` | region:region |
| `RegionRandomPoint` | `307ED312` | call | `point` | r:region |
| `RegionRect` | `00000029` | call | `region` | minx:fixed, miny:fixed, maxx:fixed, maxy:fixed |
| `RegionSetCenter` | `00000034` | action | `—` | r:region, p:point |
| `RegisterEvents` | `5870F9D1` | action | `—` | — +1sub |
| `RemoveDeathModelsinRegion` | `D399C353` | action | `—` | region:region |
| `RemoveDeathModelsinRegionImmediately` | `FF02E4D3` | action | `—` | region:region |
| `RemoveDoodadsinRegion` | `D92843D4` | action | `—` | target:region, doodadType:gamelink<Actor> |
| `RemovePlayerGroupFromPlayerGroup` | `565D7F83` | action | `—` | sourceGroup:playergroup, targetGroup:playergroup |
| `RemoveUnitGroupFromUnitGroup` | `9D10CC93` | action | `—` | sourceUnitGroup:unitgroup, targetUnitGroup:unitgroup |
| `Repeat` | `00000349` | action | `—` | count:int +1sub |
| `RepeatForever` | `CEDAB9C3` | action | `—` | — +1sub |
| `ReplaceUnit` | `F5662180` | action | `—` | unit:unit, unitType:gamelink<Unit>, options:preset |
| `RescueUnit` | `20000000` | action | `—` | unit:unit, player:int, changeColor:preset |
| `RescueUnit2` | `FA586BEC` | action | `—` | unit:unitgroup, player:int, changeColor:preset |
| `ResearchCategoryCreate` | `8148756C` | action | `—` | players:playergroup, slot:int |
| `ResearchCategoryDestroy` | `99E7A7E9` | action | `—` | researchCategory:preset |
| `ResearchCategoryDestroyAll` | `A7102E28` | action | `—` | players:playergroup |
| `ResearchCategoryLastCreated` | `E38A3C64` | call | `preset` | — |
| `ResearchCategorySetCurrentLevel` | `84312307` | action | `—` | researchCategory:preset, level:int |
| `ResearchCategorySetLastLevel` | `3F11396E` | action | `—` | researchCategory:preset, level:int |
| `ResearchCategorySetNameText` | `C616545B` | action | `—` | researchItem:preset, text:text |
| `ResearchItemCreate` | `9984B5AC` | action | `—` | players:playergroup, researchTier:preset, slot:int |
| `ResearchItemDestroy` | `3AD71E74` | action | `—` | researchItem:preset |
| `ResearchItemGetSelected` | `9032C964` | call | `preset` | player:int |
| `ResearchItemIsRecentlyPurchased` | `0328EA77` | call | `bool` | researchItem:preset |
| `ResearchItemLastCreated` | `43DF4248` | call | `preset` | — |
| `ResearchItemPurchase` | `17B2BCBB` | action | `—` | researchItem:preset |
| `ResearchItemSetConfirmationText` | `BA831D90` | action | `—` | researchItem:preset, text:text |
| `ResearchItemSetDescriptionText` | `5767F7FB` | action | `—` | researchItem:preset, text:text |
| `ResearchItemSetIconFilePath` | `8B0DCC82` | action | `—` | researchItem:preset, filePath:filepath |
| `ResearchItemSetMovieFilePath` | `E07A3283` | action | `—` | researchItem:preset, filePath:filepath |
| `ResearchItemSetNameText` | `9B71CD25` | action | `—` | researchItem:preset, text:text |
| `ResearchItemSetRecentlyPurchased` | `F86F691D` | action | `—` | researchItem:preset, recentlyPurchased:bool |
| `ResearchItemSetSelected` | `76F1C2ED` | action | `—` | players:playergroup, researchItem:preset |
| `ResearchItemSetState` | `61DCA344` | action | `—` | researchItem:preset, state:preset |
| `ResearchItemSetTooltipText` | `378229AF` | action | `—` | researchItem:preset, text:text |
| `ResearchTierCreate` | `DF17F356` | action | `—` | players:playergroup, researchTier:preset, slot:int |
| `ResearchTierDestroy` | `9C86A7EA` | action | `—` | researchTier:preset |
| `ResearchTierDestroyAll` | `22A96A01` | action | `—` | players:playergroup |
| `ResearchTierLastCreated` | `06B256B0` | call | `preset` | — |
| `ResearchTierSetMaxPurchasesAllowed` | `71609202` | action | `—` | researchTier:preset, max:int |
| `ResearchTierSetRequiredLevel` | `BC54F629` | action | `—` | researchTier:preset, level:int |
| `ResetUnitInfoButtonAbilityTooltip` | `913EDE3A` | action | `—` | unit:unit, abilcmd:abilcmd |
| `ResetUnitInfoButtonButtonTooltip` | `D1F8F338` | action | `—` | unit:unit, button:gamelink<Button> |
| `ResetUnitInfoButtonItemTooltip` | `0A37213A` | action | `—` | item:unit |
| `RestartGame` | `428A4625` | action | `—` | playerGroup:playergroup |
| `RestoreUnitSelection` | `862673FA` | action | `—` | forPlayer:int |
| `Return` | `00000097` | action | `—` | val:return |
| `ReviveOrderTargetingPoint` | `C837E5F8` | call | `order` | abilCmd:abilcmd, p:point, reviveUnit:unit |
| `ReviveOrderWithNoTarget` | `9D7786E5` | call | `order` | abilCmd:abilcmd, reviveUnit:unit |
| `Round` | `1333F1DA` | call | `fixed` | x:fixed |
| `RoundI` | `6A0BD10C` | call | `int` | x:fixed |
