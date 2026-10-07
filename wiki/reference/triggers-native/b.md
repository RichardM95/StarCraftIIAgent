# SC2 Native Functions: B

Columns are documented in [../triggers-native-functions.md](../triggers-native-functions.md). Reference in XML as `<FunctionDef Type="FunctionDef" Library="Ntve" Id="<ID>"/>`.

Parameter defaults in `nativelib` do not auto-apply; emit an explicit `<Parameter Type="Param" Id="..."/>` for every slot in generated `<FunctionCall>` XML.

### B

<a id="b"></a>

| Name | ID | Kind | Returns | Params |
|---|---|---|---|---|
| `BankBackup` | `4CD4BA5A` | action | `—` | toBackUp:bank, playerId:int |
| `BankBackupGetId` | `4BD87DC7` | call | `int` | backupBank:bank |
| `BankBackupGetLatestId` | `4B1AD9CE` | call | `int` | backupBank:bank |
| `BankBackupLoopCurrent` | `3FFA5A93` | call | `bank` | — |
| `BankBackupRemove` | `8F9FB053` | action | `—` | backupBank:bank, backupid:int, playerid:int |
| `BankConditionEvaluate` | `216F91E0` | call | `bool` | player:int, condition:gamelink<BankCondition> |
| `BankDeleteCampaignBanks` | `739C27F4` | action | `—` | player:int, index:int |
| `BankExists` | `00000280` | call | `bool` | name:string, player:int |
| `BankKeyCount` | `00000284` | call | `int` | bank:bank, section:string |
| `BankKeyExists` | `00000288` | call | `bool` | bank:bank, section:string, key:string |
| `BankKeyName` | `00000285` | call | `string` | bank:bank, section:string, key:int |
| `BankKeyRemove` | `00000296` | action | `—` | bank:bank, section:string, key:string |
| `BankKeySizeAsText` | `03D3698A` | call | `text` | bank:bank, section:string, key:string |
| `BankLastCreated` | `00000279` | call | `bank` | — |
| `BankLastRestoredUnit` | `5052436B` | call | `unit` | — |
| `BankLoad` | `00000292` | action | `—` | name:string, player:int |
| `BankName` | `00000281` | call | `string` | bank:bank |
| `BankOptionGet` | `C15EF21C` | call | `bool` | bank:bank, option:preset |
| `BankOptionSet` | `39E54B53` | action | `—` | bank:bank, option:preset, state:preset |
| `BankPlayer` | `82EFE368` | call | `int` | bank:bank |
| `BankPreload` | `7D278C76` | action | `—` | name:string, player:int |
| `BankReload` | `D315D984` | action | `—` | bank:bank |
| `BankRemove` | `00000293` | action | `—` | bank:bank |
| `BankRestore` | `488EC470` | action | `—` | originalBank:bank, playerId:int, backupId:int |
| `BankSave` | `00000294` | action | `—` | bank:bank |
| `BankSectionCount` | `00000282` | call | `int` | bank:bank |
| `BankSectionCreate` | `7730D3D7` | action | `—` | bank:bank, section:string |
| `BankSectionExists` | `00000287` | call | `bool` | bank:bank, section:string |
| `BankSectionName` | `00000283` | call | `string` | bank:bank, section:int |
| `BankSectionRemove` | `00000295` | action | `—` | bank:bank, section:string |
| `BankSectionSizeAsText` | `F1B693ED` | call | `text` | bank:bank, section:string |
| `BankSizeAsText` | `6D3A94D4` | call | `text` | name:string, player:int |
| `BankValueGetAsFixed` | `00000303` | call | `fixed` | bank:bank, section:string, key:string |
| `BankValueGetAsFlag` | `00000304` | call | `bool` | bank:bank, section:string, key:string |
| `BankValueGetAsInt` | `00000305` | call | `int` | bank:bank, section:string, key:string |
| `BankValueGetAsPoint` | `C45A90C0` | call | `point` | bank:bank, section:string, key:string |
| `BankValueGetAsString` | `00000306` | call | `string` | bank:bank, section:string, key:string |
| `BankValueGetAsText` | `543F43E3` | call | `text` | bank:bank, section:string, key:string |
| `BankValueGetAsUnit` | `00000307` | action | `—` | bank:bank, section:string, key:string, player:int, position:point, angle:fixed |
| `BankValueIsType` | `00000289` | call | `bool` | bank:bank, section:string, key:string, type:preset |
| `BankValueSetFromFixed` | `00000297` | action | `—` | bank:bank, section:string, key:string, value:fixed |
| `BankValueSetFromFlag` | `00000298` | action | `—` | bank:bank, section:string, key:string, value:bool |
| `BankValueSetFromInt` | `00000299` | action | `—` | bank:bank, section:string, key:string, value:int |
| `BankValueSetFromPoint` | `2CC865FE` | action | `—` | bank:bank, section:string, key:string, value:point |
| `BankValueSetFromString` | `00000300` | action | `—` | bank:bank, section:string, key:string, value:string |
| `BankValueSetFromText` | `949CCAA4` | action | `—` | bank:bank, section:string, key:string, value:text |
| `BankValueSetFromUnit` | `00000301` | action | `—` | bank:bank, section:string, key:string, value:unit |
| `BankVerify` | `0C6E8984` | call | `bool` | bank:bank |
| `BankWait` | `17616294` | action | `—` | bank:bank |
| `BattleReportAddAchievement` | `364CB97E` | action | `—` | battleReportId:preset, achievement:gamelink<Achievement> |
| `BattleReportCreate` | `F3918355` | action | `—` | playerGroup:playergroup, buttonText:text, type:preset, state:preset |
| `BattleReportDestroy` | `9538067D` | action | `—` | battleReportId:preset |
| `BattleReportGetBestTimeText` | `F9C25E6C` | call | `text` | battleReportId:preset |
| `BattleReportGetBonusText` | `BDAF8587` | call | `text` | battleReportId:preset |
| `BattleReportGetBonusTitle` | `D65C20AA` | call | `text` | battleReportId:preset |
| `BattleReportGetButtonImage` | `2F251E31` | call | `filepath` | battleReportId:preset |
| `BattleReportGetButtonText` | `CF4A4461` | call | `text` | battleReportId:preset |
| `BattleReportGetDialogControl` | `1419AB55` | call | `control` | — |
| `BattleReportGetDifficultyLevelBestTimeText` | `15D7EFD8` | call | `text` | battleReportId:preset, difficultyLevel:difficulty |
| `BattleReportGetDifficultyLevelCompleted` | `0DA15FC9` | call | `bool` | battleReportId:preset, difficultyLevel:difficulty |
| `BattleReportGetMissionImage` | `6F0AABD8` | call | `filepath` | battleReportId:preset |
| `BattleReportGetMissionText` | `10149A6A` | call | `text` | battleReportId:preset |
| `BattleReportGetPriority` | `5408B6EC` | call | `int` | battleReportId:preset |
| `BattleReportGetResearchText` | `00F5BF8D` | call | `text` | battleReportId:preset |
| `BattleReportGetResearchTitle` | `4889C7FA` | call | `text` | battleReportId:preset |
| `BattleReportGetSceneImage` | `68C30BB3` | call | `filepath` | battleReportId:preset |
| `BattleReportGetSceneText` | `E89E0065` | call | `text` | battleReportId:preset |
| `BattleReportGetState` | `4A826D69` | call | `preset` | battleReportId:preset |
| `BattleReportLastCreated` | `B1BE2D3C` | call | `preset` | — |
| `BattleReportPanelGetSelectedBattleReport` | `81083A39` | call | `preset` | player:int |
| `BattleReportPanelSetSelectedBattleReport` | `B9098720` | action | `—` | players:playergroup, visible:preset |
| `BattleReportSetBestTimeText` | `D2F7140F` | action | `—` | battleReportId:preset, text:text |
| `BattleReportSetBonusText` | `1BC22336` | action | `—` | battleReportId:preset, text:text |
| `BattleReportSetBonusTitle` | `D6FBE13C` | action | `—` | battleReportId:preset, text:text |
| `BattleReportSetButtonImage` | `90D87E30` | action | `—` | battleReportId:preset, image:filepath |
| `BattleReportSetButtonText` | `E6F25557` | action | `—` | battleReportId:preset, text:text |
| `BattleReportSetDifficultyLevelBestTimeText` | `5FB9E5A7` | action | `—` | battleReportId:preset, difficultyLevel:difficulty, text:text |
| `BattleReportSetDifficultyLevelCompleted` | `819A2DA9` | action | `—` | battleReportId:preset, difficultyLevel:difficulty, completed:bool |
| `BattleReportSetMissionImage` | `4050E6FA` | action | `—` | battleReportId:preset, image:filepath |
| `BattleReportSetMissionText` | `C1ED059D` | action | `—` | battleReportId:preset, text:text |
| `BattleReportSetPriority` | `6E136099` | action | `—` | battleReportId:preset, priority:int |
| `BattleReportSetResearchText` | `E6439D48` | action | `—` | battleReportId:preset, text:text |
| `BattleReportSetResearchTitle` | `E956CD56` | action | `—` | battleReportId:preset, text:text |
| `BattleReportSetSceneImage` | `84B40E32` | action | `—` | battleReportId:preset, image:filepath |
| `BattleReportSetSceneText` | `D8E3EC49` | action | `—` | battleReportId:preset, text:text |
| `BattleReportSetShownInMissionTotal` | `8160F635` | action | `—` | battleReportId:preset, shown:preset |
| `BattleReportSetState` | `43A84086` | action | `—` | battleReportId:preset, state:preset |
| `BehaviorAddToSharedTrackedUnitList` | `4B4B6564` | action | `—` | inBehavior:gamelink<Behavior>, inCaster:unit |
| `BitMaskAddBitMask` | `8E1C5BA7` | action | `—` | receivingBitMask:bitmask, bitMaskToAdd:bitmask |
| `BitMaskAndBitMask` | `D79B5E14` | action | `—` | receivingBitMask:bitmask, andWithBitMask:bitmask |
| `BitMaskCountOnBits` | `385D9069` | call | `int` | ?:0F33E346, bitMask:bitmask |
| `BitMaskFalseIndex` | `CA455926` | call | `bool` | bitMask:bitmask, indexToCheck:int |
| `BitMaskInvert` | `2539ACD3` | action | `—` | bitMask:bitmask |
| `BitMaskIsEqual` | `DE45F595` | call | `bool` | lHS:bitmask, rHS:bitmask |
| `BitMaskLeftShift` | `17A7CF59` | action | `—` | receivingBitMask:bitmask, leftShiftCount:int |
| `BitMaskMakeDefaultMask` | `30D85A7D` | call | `bitmask` | ?:D41D7C1E |
| `BitMaskOrBitMask` | `E2D0649C` | action | `—` | receivingBitMask:bitmask, orWithBitMask:bitmask |
| `BitMaskReset` | `7D134CB3` | action | `—` | bitMask:bitmask |
| `BitMaskRightShift` | `EBA91B3C` | action | `—` | receivingBitMask:bitmask, rightShiftCount:int |
| `BitMaskSetIndex` | `72D06237` | action | `—` | bitMask:bitmask, indextoSet:int, setOn:bool |
| `BitMaskTrueIndex` | `C29F8A41` | call | `bool` | bitMask:bitmask, indexToCheck:int |
| `BitMaskXorBitMask` | `B6ED82BE` | action | `—` | receivingBitMask:bitmask, xorWithBitMask:bitmask |
| `BoardCreate` | `503B2E7F` | action | `—` | columns:int, rows:int, name:text, color:color |
| `BoardDestroy` | `00000448` | action | `—` | board:preset |
| `BoardItemSetAlignment` | `00000461` | action | `—` | board:preset, column:int, row:int, align:preset |
| `BoardItemSetBackgroundColor` | `00000459` | action | `—` | board:preset, column:int, row:int, color:color |
| `BoardItemSetFontSize` | `23BAB430` | action | `—` | board:preset, column:int, row:int, size:int |
| `BoardItemSetIcon` | `00000460` | action | `—` | board:preset, column:int, row:int, icon:filepath, side:preset |
| `BoardItemSetProgressColor` | `0A37E6F9` | action | `—` | board:preset, column:int, row:int, color:color, step:int |
| `BoardItemSetProgressRange` | `734C8F91` | action | `—` | board:preset, column:int, row:int, minimum:fixed, maximum:fixed |
| `BoardItemSetProgressShow` | `F79DB963` | action | `—` | board:preset, column:int, row:int, showHide:preset |
| `BoardItemSetProgressValue` | `58C31300` | action | `—` | board:preset, column:int, row:int, minimum:fixed |
| `BoardItemSetSortValue` | `00000462` | action | `—` | board:preset, column:int, row:int, sort:int |
| `BoardItemSetText` | `00000457` | action | `—` | board:preset, column:int, row:int, text:text |
| `BoardItemSetTextColor` | `00000458` | action | `—` | board:preset, column:int, row:int, color:color |
| `BoardLastCreated` | `00000447` | call | `preset` | — |
| `BoardMinimizeEnable` | `4D70595C` | action | `—` | board:preset, players:playergroup, enable:preset |
| `BoardMinimizeSetColor` | `11C2C9DE` | action | `—` | board:preset, color:color |
| `BoardMinimizeSetState` | `7D06D8AB` | action | `—` | board:preset, players:playergroup, minimize:preset |
| `BoardMinimizeShow` | `788C4F28` | action | `—` | board:preset, players:playergroup, show:preset |
| `BoardPlayerAdd` | `00000465` | action | `—` | board:preset, player:int |
| `BoardPlayerRemove` | `5D44BC5F` | action | `—` | board:preset, player:int |
| `BoardResetPosition` | `DBE4CE29` | action | `—` | board:preset |
| `BoardRowSetGroup` | `00000456` | action | `—` | board:preset, row:int, group:int |
| `BoardSetAnchor` | `49934F8F` | action | `—` | board:preset, anchor:preset, xOffset:int, yOffset:int |
| `BoardSetColumnCount` | `00000452` | action | `—` | board:preset, count:int |
| `BoardSetColumnWidth` | `00000454` | action | `—` | board:preset, column:int, width:fixed |
| `BoardSetGroupCount` | `00000455` | action | `—` | board:preset, count:int |
| `BoardSetName` | `00000450` | action | `—` | board:preset, text:text, color:color |
| `BoardSetPlayerColumn` | `00000464` | action | `—` | board:preset, column:int, group:preset |
| `BoardSetPosition` | `DDBABF2E` | action | `—` | board:preset, x:int, y:int |
| `BoardSetRowCount` | `00000453` | action | `—` | board:preset, count:int |
| `BoardSetState` | `00000451` | action | `—` | board:preset, players:playergroup, state:preset, enable:preset |
| `BoardShowAll` | `00000449` | action | `—` | show:preset, players:playergroup |
| `BoardSort` | `00000463` | action | `—` | board:preset, column:int, ascending:preset, priority:int |
| `BoolToInt` | `2492FDC8` | call | `int` | boolean:bool |
