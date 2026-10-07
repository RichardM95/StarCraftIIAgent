# SC2 Native Functions: G

Columns are documented in [../triggers-native-functions.md](../triggers-native-functions.md). Reference in XML as `<FunctionDef Type="FunctionDef" Library="Ntve" Id="<ID>"/>`.

Parameter defaults in `nativelib` do not auto-apply; emit an explicit `<Parameter Type="Param" Id="..."/>` for every slot in generated `<FunctionCall>` XML.

### G

<a id="g"></a>

| Name | ID | Kind | Returns | Params |
|---|---|---|---|---|
| `GameAddChargeRegen` | `90684127` | action | `—` | inCharge:string, inVal:fixed |
| `GameAddChargeRegenFull` | `2A102654` | action | `—` | inCharge:string, inVal:fixed |
| `GameAddChargeRegenRemaining` | `D89521D2` | action | `—` | inCharge:string, inVal:fixed |
| `GameAddChargeUsed` | `477085FF` | action | `—` | inCharge:string, inVal:fixed |
| `GameAddCooldown` | `38867CC5` | action | `—` | inCooldown:string, inVal:fixed |
| `GameAreHeroDuplicatesAllowed` | `9DB6F7DA` | call | `bool` | — |
| `GameAttributeGameValue` | `9AC9D531` | call | `attributevalue` | attribute:attributegame |
| `GameAttributePlayersForTeam` | `2F695638` | call | `playergroup` | team:int |
| `GameAttributePlayerValue` | `1C7F6A3E` | call | `attributevalue` | attribute:attributeplayer, player:int |
| `GameCheatAllow` | `4AB9E08B` | action | `—` | cheat:preset, allow:preset |
| `GameCheatsEnabled` | `3CE0B2FC` | call | `bool` | category:preset |
| `GameDestroyEffects` | `43E44B87` | action | `—` | position:point, distance:fixed, maximum:int, effectType:gamelink<Effect> |
| `GameGetAbsoluteTimeRemaining` | `F2E7D3C7` | call | `fixed` | — |
| `GameGetAbsoluteTimeRemainingPaused` | `C54E0080` | call | `bool` | — |
| `GameGetChargeRegen` | `26A716B4` | call | `fixed` | inCharge:string |
| `GameGetChargeRegenFull` | `B9A3D515` | call | `fixed` | inCharge:string, adjustmentOnly:bool |
| `GameGetChargeUsed` | `3743B764` | call | `fixed` | inCharge:string |
| `GameGetCooldown` | `65093B8D` | call | `fixed` | inCooldown:string |
| `GameGetGlobalTimeScale` | `6E8F94CA` | call | `fixed` | — |
| `GameGetMissionTime` | `5A832F2D` | call | `fixed` | — |
| `GameGetSpeed` | `663E1162` | call | `fixed` | — |
| `GameGetSpeedValue` | `37FE2FA1` | call | `preset` | — |
| `GameGetSpeedValueMinimum` | `E10B1BC6` | call | `preset` | — |
| `GameIsCompetitive` | `E32EC8BE` | call | `bool` | — |
| `GameIsCooperative` | `4DC37831` | call | `bool` | — |
| `GameIsDebugOptionSet` | `ABE9862E` | call | `bool` | m:string, player:int |
| `GameIsExaminable` | `F1585010` | call | `bool` | — |
| `GameIsMatchmade` | `EBD818C4` | call | `bool` | — |
| `GameIsMissionTimePaused` | `71337636` | call | `bool` | — |
| `GameIsOnline` | `02F692F1` | call | `bool` | — |
| `GameIsPractice` | `701D2C53` | call | `bool` | — |
| `GameIsSeedLocked` | `D265EBCA` | call | `bool` | — |
| `GameIsSpeedLocked` | `A7CB1C4B` | call | `bool` | — |
| `GameIsTestMap` | `40844EC3` | call | `bool` | type:preset |
| `GameIsTransitionMap` | `23AAB834` | call | `bool` | — |
| `GameMapDescription` | `4AB3CB9A` | call | `text` | — |
| `GameMapIsBlizzard` | `24872502` | call | `bool` | — |
| `GameMapName` | `F7D7DC36` | call | `text` | — |
| `GameMapPath` | `514AEF40` | call | `string` | — |
| `GameOver` | `00000198` | action | `—` | player:int, type:preset, showDialog:preset, showScore:preset |
| `GamePauseAllCharges` | `38D102EB` | action | `—` | pause:preset |
| `GamePauseAllCooldowns` | `344B7296` | action | `—` | pause:preset |
| `GamePlayTime` | `0F5B8AA6` | call | `fixed` | player:int |
| `GameRemoveChargeRegen` | `58A706F7` | action | `—` | inCharge:string |
| `GameRemoveChargeUsed` | `E80E31D9` | action | `—` | inCharge:string |
| `GameRemoveCooldown` | `57266FCE` | action | `—` | inCooldown:string |
| `GameSaveCreate` | `1C57B355` | action | `—` | name:text, description:text, image:string, automatic:bool |
| `GameSetAbsoluteTimeRemaining` | `97BA2D33` | action | `—` | time:fixed |
| `GameSetAbsoluteTimeRemainingPaused` | `90629198` | action | `—` | pauseUnpause:preset |
| `GameSetBackground` | `73DA313C` | action | `—` | type:preset, model:gamelink<Model>, speed:fixed |
| `GameSetGlobalTimeScale` | `62180C0B` | action | `—` | timeScale:fixed |
| `GameSetLighting` | `BB08B228` | action | `—` | light:gamelink<Light>, blendTime:fixed |
| `GameSetMissionTimePaused` | `043D7B4F` | action | `—` | paused:preset |
| `GameSetNextCampaignIndex` | `733FE4D0` | action | `—` | players:playergroup, campaignIndex:int |
| `GameSetNextMap` | `00000336` | action | `—` | map:string |
| `GameSetPauseable` | `2395936A` | action | `—` | allow:preset |
| `GameSetQuitOnQuitButton` | `22FD81D4` | action | `—` | enable:bool |
| `GameSetSeed` | `480BC837` | action | `—` | value:int |
| `GameSetSeedLocked` | `0F6BD400` | action | `—` | onOff:preset |
| `GameSetSpeedLocked` | `86A15A1D` | action | `—` | lockUnlock:preset |
| `GameSetSpeedValue` | `EEFB5A8F` | action | `—` | speed:preset |
| `GameSetSpeedValueMinimum` | `58C4A428` | action | `—` | speed:preset |
| `GameSetToDLighting` | `8A768239` | action | `—` | light:gamelink<Light> |
| `GameSetTransitionMap` | `8D1CFF2D` | action | `—` | transition:string |
| `GameTerrainSet` | `21FDF59F` | call | `gamelink<Terrain>` | — |
| `GameTestConfigType` | `2577A272` | call | `int` | — |
| `GameTimeOfDayCurrentTimeEvent` | `AAAF9344` | call | `preset` | — |
| `GameTimeOfDayGet` | `00000394` | call | `timeofday` | — |
| `GameTimeOfDayGetLength` | `21C1E117` | call | `fixed` | — |
| `GameTimeOfDayIsPaused` | `00000396` | call | `bool` | — |
| `GameTimeOfDayPause` | `00000393` | action | `—` | pause:preset |
| `GameTimeOfDaySet` | `00000391` | action | `—` | time:timeofday |
| `GameTimeOfDaySetLength` | `46F3910A` | action | `—` | length:fixed |
| `GameTimeOfDayTimeValueSet` | `CC7E793A` | action | `—` | hours:int, minutes:int, seconds:int |
| `GameTimeOfDayValueGet` | `C70C770F` | call | `int` | type:preset |
| `GameTimeOfDayValueSet` | `84B94983` | action | `—` | seconds:int |
| `GameUserClearMessages` | `7B72A8FE` | action | `—` | gameUser:preset, options:preset |
| `GameUserDisplayMessage` | `7B581C02` | action | `—` | gameUser:preset, messageArea:preset, message:text |
| `GameUserHandle` | `AA8BBBBA` | call | `string` | gameUserId:preset |
| `GameUserName` | `B08F1A3A` | call | `text` | gameUserId:preset |
| `GameWaitForResourcesToComplete` | `19DB283F` | action | `—` | — |
| `GetDateTimeWeekday` | `D8A8D577` | call | `int` | datetime:datetime |
| `GlobalCinematicSetting` | `4A703103` | action | `—` | onOff:preset |
| `GlobalCinematicSettingFixedSeedOnOff` | `8FFC90F3` | action | `—` | onOff:preset, fixedSeedOnOff:preset |
