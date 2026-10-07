# SC2 Native Functions: S

Columns are documented in [../triggers-native-functions.md](../triggers-native-functions.md). Reference in XML as `<FunctionDef Type="FunctionDef" Library="Ntve" Id="<ID>"/>`.

Parameter defaults in `nativelib` do not auto-apply; emit an explicit `<Parameter Type="Param" Id="..."/>` for every slot in generated `<FunctionCall>` XML.

### S

<a id="s"></a>

| Name | ID | Kind | Returns | Params |
|---|---|---|---|---|
| `SaveDataTableInstanceValueDialogItem` | `CD9E279D` | action | `—` | instance:datatable, name:string, value:control |
| `SaveDataTableInstanceValueDifficultyLevel` | `3A8EE197` | action | `—` | instance:datatable, name:string, value:difficulty |
| `SaveDataTableInstanceValuePlayerColor` | `E8CBF871` | action | `—` | instance:datatable, name:string, value:playercolor |
| `SaveDataTableInstanceValueTextTag` | `C698D082` | action | `—` | instance:datatable, name:string, value:preset |
| `SaveDataTableValueDialogItem` | `7295AB42` | action | `—` | scope:preset, name:string, value:control |
| `SaveDataTableValueDifficultyLevel` | `0F80E344` | action | `—` | scope:preset, name:string, value:difficulty |
| `SaveDataTableValuePlayerColor` | `B725E84F` | action | `—` | scope:preset, name:string, value:playercolor |
| `SaveDataTableValueTextTag` | `B895880A` | action | `—` | scope:preset, name:string, value:preset |
| `ScreenButton` | `64C8AB22` | call | `control` | screenButtonID:int |
| `ScreenButtonDialog` | `F5A3C98A` | call | `dialog` | screenButtonID:int |
| `ScreenImageDialog` | `3B76ECAD` | call | `dialog` | screenImageID:int |
| `ScreenImageDialogItem` | `078BA666` | call | `control` | screenImageID:int |
| `ScreenLabelDialog` | `39E83804` | call | `dialog` | screenLabelID:int |
| `ScreenLabelDialogItem` | `A5883B0C` | call | `control` | screenLabelID:int |
| `SelectMainShadowLight` | `D2ED8E96` | action | `—` | inId:string |
| `SendActorMessageToGameRegion` | `7317E443` | action | `—` | region:region, message:actormsg |
| `SendActorMessageToGameRegionWithFilters` | `0912762F` | action | `—` | region:region, intersectType:preset, message:actormsg, classFilters:string, terms:string |
| `SendActorMessageToUnit` | `E1552C18` | action | `—` | unit:unit, message:actormsg |
| `SendTransmissionSimple` | `1543037A` | action | `—` | Source:transmissionsource, Target:portrait, Sound:soundlink, Duration:fixed, DurationType:preset, WaitUntilDone:preset |
| `SetAlliance` | `C29FFDCD` | action | `—` | sourcePlayer:int, targetPlayer:int, alliance:preset |
| `SetAllianceAspectForPlayerGroup` | `E4C1C421` | action | `—` | players:playergroup, inAllianceId:preset, ally:preset |
| `SetAllianceBetweenTwoPlayerGroups` | `8A8CD531` | action | `—` | sourcePlayers:playergroup, targetPlayers:playergroup, alliance:preset |
| `SetAllianceOneWay` | `C6A9716F` | action | `—` | sourcePlayer:int, targetPlayer:int, alliance:preset |
| `SetAllSoundChannelVolumes` | `3B8D5BC4` | action | `—` | mode:preset, players:playergroup, duration:fixed |
| `SetAnimationCompletion` | `477043D4` | action | `—` | target:actor, identifier:string, percent:fixed |
| `SetAnimationDuration` | `34DE36C4` | action | `—` | target:actor, identifier:string, duration:fixed |
| `SetAnimationTime` | `02FF6712` | action | `—` | target:actor, identifier:string, time:fixed, scaled:preset |
| `SetAnimationTimeScale` | `28E8EEF6` | action | `—` | target:actor, identifier:string, scale:fixed |
| `SetBearings` | `AAA4F3A3` | call | `actormsg` | positionX:fixed, positionY:fixed, positionZ:fixed, forwardX:fixed, forwardY:fixed, forwardZ:fixed, upX:fixed, upY:fixed, upZ:fixed |
| `SetBearingsFrom` | `37F6CF56` | call | `actormsg` | actor:string |
| `SetBearingsH` | `6967D3E5` | call | `actormsg` | positionX:fixed, positionY:fixed, height:fixed, forwardX:fixed, forwardY:fixed, forwardZ:fixed, upX:fixed, upY:fixed, upZ:fixed |
| `SetBehaviorCount` | `307CE3FF` | action | `—` | inUnit:unit, inBehavior:gamelink<Behavior>, inCaster:unit, inCount:int |
| `SetBossBarBoss` | `F4F94B84` | action | `—` | bossBarID:int, boss:unit, refresh:preset |
| `SetBossBarCurrentValue` | `ED2C60CE` | action | `—` | bossBarID:int, current:int, refresh:preset |
| `SetBossBarMaximumValue` | `76ECC716` | action | `—` | bossBarID:int, max:int, refresh:preset |
| `SetBossBarRace` | `231557AC` | action | `—` | bossBarID:int, race:preset, refresh:preset |
| `SetCinematicTransitionStyle` | `E3C77ACF` | action | `—` | style:preset |
| `SetDialogItemAcceptMouse` | `E48A04F2` | action | `—` | dialogItem:control, acceptMouse:bool, players:playergroup |
| `SetDialogItemAchievement` | `EB0FFD57` | action | `—` | dialogItem:control, achievement:gamelink<Achievement>, players:playergroup |
| `SetDialogItemActor` | `0EDF1F98` | action | `—` | dialogItem:control, actor:gamelink<Actor>, players:playergroup |
| `SetDialogItemAllowedMouseButtons` | `DD656F90` | action | `—` | dialogItem:control, allowedButtons:preset, players:playergroup |
| `SetDialogItemAlphaMask` | `3561BA91` | action | `—` | dialogItem:control, image:filepath, players:playergroup |
| `SetDialogItemAnimation` | `F934E0BA` | action | `—` | dialogItem:control, animation:modelanim, players:playergroup |
| `SetDialogItemAnimationDuration` | `2CA88AC8` | action | `—` | dialogItem:control, time:fixed, players:playergroup |
| `SetDialogItemAnimationIndex` | `FB8E3369` | action | `—` | dialogItem:control, index:int, players:playergroup |
| `SetDialogItemAnimationTime` | `62FBB9DC` | action | `—` | dialogItem:control, time:fixed, players:playergroup |
| `SetDialogItemBackgroundVisible` | `30122AF8` | action | `—` | dialogItem:control, visible:bool, players:playergroup |
| `SetDialogItemBehavior` | `AE9EFE82` | action | `—` | dialogItem:control, behavior:gamelink<Behavior>, players:playergroup |
| `SetDialogItemBlendMode` | `B20C9535` | action | `—` | dialogItem:control, blendMode:preset, players:playergroup |
| `SetDialogItemBorderColor` | `473C4DC6` | action | `—` | dialogItem:control, color:color, players:playergroup |
| `SetDialogItemBorderImage` | `E8355707` | action | `—` | dialogItem:control, image:filepath, players:playergroup |
| `SetDialogItemBorderVisible` | `C43E87D1` | action | `—` | dialogItem:control, visible:bool, players:playergroup |
| `SetDialogItemCamera` | `33761368` | action | `—` | dialogItem:control, camera:string, players:playergroup |
| `SetDialogItemChecked` | `45EF1251` | action | `—` | dialogItem:control, checked:preset, players:playergroup |
| `SetDialogItemClickOnDown` | `8B9F65D1` | action | `—` | dialogItem:control, clickOnDown:bool, players:playergroup |
| `SetDialogItemColor` | `976E02E6` | action | `—` | dialogItem:control, color:color, players:playergroup |
| `SetDialogItemCurrentValue` | `934CE3DF` | action | `—` | dialogItem:control, currentValue:fixed, players:playergroup |
| `SetDialogItemCustomTooltip` | `2DB2EF35` | action | `—` | dialogItem:control, tooltip:control, players:playergroup |
| `SetDialogItemCutscene` | `EF6279C8` | action | `—` | dialogItem:control, cutscene:filepath, players:playergroup |
| `SetDialogItemDesaturated` | `E997B568` | action | `—` | dialogItem:control, desaturated:bool, players:playergroup |
| `SetDialogItemDesaturationColor` | `66FCC01F` | action | `—` | dialogItem:control, color:color, players:playergroup |
| `SetDialogItemEditorValue` | `F73FDB4C` | action | `—` | dialogItem:control, value:string, players:playergroup |
| `SetDialogItemFillColor` | `0BE35026` | action | `—` | dialogItem:control, color:color, players:playergroup |
| `SetDialogItemFlash` | `670FD57D` | action | `—` | dialogItem:control, flash:filepath, players:playergroup |
| `SetDialogItemForceVisible` | `C9C49ED4` | action | `—` | dialogItem:control, visible:bool, players:playergroup |
| `SetDialogItemHandle` | `1AD2DE50` | action | `—` | dialogItem:control, handle:string, players:playergroup |
| `SetDialogItemHotkey` | `405648E4` | action | `—` | dialogItem:control, hotkey:preset, players:playergroup |
| `SetDialogItemImage` | `D5F9189A` | action | `—` | dialogItem:control, image:filepath, players:playergroup |
| `SetDialogItemImage2` | `8BE6BD8F` | action | `—` | dialogItem:control, image:filepath, players:playergroup |
| `SetDialogItemImageType` | `2B97DDF4` | action | `—` | dialogItem:control, imageType:preset, players:playergroup |
| `SetDialogItemImageType2` | `C55E1E32` | action | `—` | dialogItem:control, tiled:bool, players:playergroup |
| `SetDialogItemLight` | `AD67F0AD` | action | `—` | dialogItem:control, light:gamelink<Light>, players:playergroup |
| `SetDialogItemMaximumValue` | `F2E12806` | action | `—` | dialogItem:control, maxValue:fixed, players:playergroup |
| `SetDialogItemMinimumValue` | `C5C8712D` | action | `—` | dialogItem:control, minValue:fixed, players:playergroup |
| `SetDialogItemModel` | `C8CCD88A` | action | `—` | dialogItem:control, model:gamelink<Model>, players:playergroup |
| `SetDialogItemMovie` | `5C428316` | action | `—` | dialogItem:control, movie:filepath, players:playergroup |
| `SetDialogItemMuted` | `ADEDDAE8` | action | `—` | dialogItem:control, muted:bool, players:playergroup |
| `SetDialogItemPaused` | `F98F19F2` | action | `—` | dialogItem:control, paused:bool, players:playergroup |
| `SetDialogItemPlayerId` | `137A8328` | action | `—` | dialogItem:control, playerId:int, players:playergroup |
| `SetDialogItemRenderPriority` | `62157B3C` | action | `—` | dialogItem:control, renderPriority:int, players:playergroup |
| `SetDialogItemRenderType` | `B4E65256` | action | `—` | dialogItem:control, renderType:preset, players:playergroup |
| `SetDialogItemRotation` | `F5FF70C2` | action | `—` | dialogItem:control, rotation:int, players:playergroup |
| `SetDialogItemScoreValueLink` | `A3EAF56D` | action | `—` | dialogItem:control, scoreValueLink:gamelink<ScoreValue>, players:playergroup |
| `SetDialogItemStateIndex` | `7AED3102` | action | `—` | dialogItem:control, stateIndex:int, players:playergroup |
| `SetDialogItemStyle` | `3C8304BE` | action | `—` | dialogItem:control, style:fontstyle, players:playergroup |
| `SetDialogItemSubmenu` | `9E3E4BF5` | action | `—` | dialogItem:control, submenu:string, players:playergroup |
| `SetDialogItemTeamColor` | `5FEFE214` | action | `—` | dialogItem:control, color:color, players:playergroup |
| `SetDialogItemTeamColorIndex` | `4405C582` | action | `—` | dialogItem:control, index:int, players:playergroup |
| `SetDialogItemText` | `BA583993` | action | `—` | dialogItem:control, text:text, players:playergroup |
| `SetDialogItemTextWriteout` | `DA95549D` | action | `—` | dialogItem:control, writeout:bool, players:playergroup |
| `SetDialogItemTextWriteoutDuration` | `29F59B61` | action | `—` | dialogItem:control, duration:fixed, players:playergroup |
| `SetDialogItemTintColor` | `53D6FB68` | action | `—` | dialogItem:control, color:color, players:playergroup |
| `SetDialogItemToggled` | `4A7EACA2` | action | `—` | dialogItem:control, toggled:bool, players:playergroup |
| `SetDialogItemTooltip` | `E786CA75` | action | `—` | dialogItem:control, tooltip:text, players:playergroup |
| `SetDialogItemtoUseAspectUncorrection` | `B85FEED3` | action | `—` | dialogItem:control, useAspectUncorrection:bool, players:playergroup |
| `SetDialogItemTransitionModel` | `E2ACE3F2` | action | `—` | dialogItem:control, model:gamelink<Model>, players:playergroup |
| `SetDialogItemUnit` | `6E473B27` | action | `—` | dialogItem:control, unit:unit, players:playergroup |
| `SetDialogItemUnitGroup` | `AE4C1D89` | action | `—` | dialogItem:control, unitGroup:unitgroup, players:playergroup |
| `SetDialogItemUnitLink` | `D5C6C608` | action | `—` | dialogItem:control, unitLink:gamelink<Unit>, players:playergroup |
| `SetDialogItemUseTransition` | `71ADAE5C` | action | `—` | dialogItem:control, useTransition:bool, players:playergroup |
| `SetFacing` | `EEB3ECF8` | call | `actormsg` | facing:fixed |
| `SetHeight` | `DD557FEC` | call | `actormsg` | height:fixed |
| `SetHeroLeaderPanelEnabled` | `95FF63B8` | action | `—` | enabled:preset |
| `SetLocalTintColor` | `56C7DAB3` | call | `actormsg` | color:color |
| `SetNextMissionDifficulty` | `B609FCF9` | action | `—` | players:playergroup, difficulty:difficulty |
| `SetOpacity` | `B6218C18` | call | `actormsg` | opacity:fixed, blendDuration:fixed |
| `SetPlayerGroupAlliance` | `089982FF` | action | `—` | players:playergroup, alliance:preset |
| `SetPosition` | `3049D859` | call | `actormsg` | x:fixed, y:fixed, z:fixed |
| `SetPosition2D` | `8819B5CE` | call | `actormsg` | x:fixed, y:fixed |
| `SetPosition2DH` | `3C7147B0` | call | `actormsg` | x:fixed, y:fixed |
| `SetPositionFrom` | `7DEB7D4B` | call | `actormsg` | actor:string |
| `SetPositionH` | `FABD411F` | call | `actormsg` | x:fixed, y:fixed, height:fixed |
| `SetRenderToTextureEnabled` | `34B22F9F` | call | `actormsg` | enabled:bool |
| `SetRotation` | `6F1A64F5` | call | `actormsg` | forwardX:fixed, forwardY:fixed, forwardZ:fixed, upX:fixed, upY:fixed, upZ:fixed |
| `SetRotationFrom` | `E5EFA0FC` | call | `actormsg` | actor:string |
| `SetScale` | `116E3543` | call | `actormsg` | x:fixed, y:fixed, z:fixed, blendDuration:fixed |
| `SetScaleAbsolute` | `F21F850B` | call | `actormsg` | x:fixed, y:fixed, z:fixed, blendDuration:fixed |
| `SetScoreTimer` | `688C8C8E` | action | `—` | scoreTimer:timer |
| `SetScreenButtonBorderImage` | `D3FB8606` | action | `—` | screenButtonID:int, borderImage:filepath, hoverImage:filepath, borderType:preset |
| `SetScreenButtonFlashingBorderImage` | `E5CABD27` | action | `—` | screenButtonID:int, borderImage:filepath, hoverImage:filepath, borderType:preset |
| `SetTacticalAIRange` | `D0A20ECE` | action | `—` | player:int, unitType:gamelink<Unit>, distance:int |
| `SetTacticalAIThink` | `35699ADE` | action | `—` | player:int, unitType:gamelink<Unit>, target:string, isNative:preset |
| `SetTalentsEnabled` | `EF99264E` | action | `—` | enabled:preset |
| `SetTalentTierEnabled` | `5B11D09A` | action | `—` | tier:int, enabled:bool |
| `SetTalentTreeHeroLevel` | `6218BD4D` | action | `—` | player:int, heroLevel:int |
| `SetTalentTreePauseGameWhenSelectionPanelShown` | `25747069` | action | `—` | pauseGame:bool |
| `SetTalentTreeSelectionPanelAutoShow` | `21456699` | action | `—` | autoShow:bool |
| `SetTalentTreeSelectionPanelDismissAllowed` | `E92CD46E` | action | `—` | allowed:preset |
| `SetTalentUpgradeRequired` | `73D62C7D` | action | `—` | required:bool |
| `SetTeamColor` | `1161764D` | call | `actormsg` | diffuseColor:color, emissiveColor:color |
| `SetTintColor` | `D41CE6AB` | call | `actormsg` | color:color, hdr:fixed, duration:fixed |
| `SetUnitInfoButtonAbilityTooltip` | `A14A2FA0` | action | `—` | unit:unit, key:abilcmd, text:text |
| `SetUnitInfoButtonButtonTooltip` | `178CE7C2` | action | `—` | unit:unit, key:gamelink<Button>, text:text |
| `SetUnitInfoButtonItemTooltip` | `3A57DDE5` | action | `—` | item:unit, text:text |
| `SetUpgradeLevelForPlayer` | `9F8EF8FB` | action | `—` | p:int, upgrade:gamelink<Upgrade>, levels:int |
| `SetVariable` | `00000136` | action | `—` | var:anyvariable, val:sameas |
| `SetVariableParam` | `5BDC6A34` | action | `—` | var:anycompare, val:sameas |
| `SetVisibility` | `CB1ABC35` | call | `actormsg` | visible:bool |
| `SetWalkAnimMoveSpeed` | `005E9040` | call | `actormsg` | value:fixed |
| `SetZ` | `9A3A1F3F` | call | `actormsg` | z:fixed |
| `ShareVisionofUnit` | `443F1CA3` | action | `—` | unit:unit, shareUnshare:preset, player:int |
| `ShowHideBossBar` | `8A208EC7` | action | `—` | showHide:preset, bossBarID:int |
| `ShowHideDoodadsInRegion` | `B9B9D1BF` | action | `—` | showHide:preset, target:region, doodadType:gamelink<Actor> |
| `ShowHideLeaderboard` | `42E3909E` | action | `—` | board:preset, showHide:preset, players:playergroup |
| `ShowHidePlacementModels` | `087DF943` | action | `—` | show:preset |
| `ShowHideUnit` | `40000000` | action | `—` | unit:unit, showHide:preset |
| `Signal` | `DB5A7F79` | call | `actormsg` | signal:string |
| `SimpleLookAtStart` | `49B6B3DC` | action | `—` | unit:unit, type:preset, lookAtTarget:actor |
| `SimpleLookAtStop` | `3D6113BF` | action | `—` | unit:unit, type:preset |
| `Sin` | `00000015` | call | `fixed` | a:fixed |
| `SkipRemaining` | `00000139` | action | `—` | — |
| `SleepUnit` | `16D16133` | action | `—` | unit:unit, sleepWakeUp:preset |
| `SoundAddDSP` | `7E2859EF` | call | `actormsg` | effect:gamelink<Reverb> |
| `SoundChannelDSPInsert` | `6E191A9E` | action | `—` | players:playergroup, channel:preset, dSP:gamelink<DSP> |
| `SoundChannelDSPRemove` | `A2A56E70` | action | `—` | players:playergroup, channel:preset, dSP:gamelink<DSP> |
| `SoundChannelMute` | `F0DF33AB` | action | `—` | players:playergroup, channel:preset, mute:preset |
| `SoundChannelPause` | `43EB1F65` | action | `—` | players:playergroup, channel:preset, pause:preset |
| `SoundChannelSetVolume` | `3434F38C` | action | `—` | players:playergroup, channel:preset, volume:fixed, duration:fixed |
| `SoundChannelStop` | `38415B68` | action | `—` | players:playergroup, channel:preset |
| `SoundLastPlayed` | `C9ADFB21` | call | `sound` | — |
| `SoundLengthQuery` | `845B0678` | action | `—` | info:soundlink |
| `SoundLengthQueryWait` | `12E16952` | action | `—` | — |
| `SoundLengthSync` | `C0749AB9` | call | `fixed` | sound:soundlink |
| `SoundLink` | `D5671C0B` | call | `soundlink` | soundId:gamelink<Sound>, soundIndex:int |
| `SoundLinkAsset` | `29BBB8F3` | call | `int` | soundLink:soundlink |
| `SoundLinkId` | `577C6232` | call | `gamelink<Sound>` | soundLink:soundlink |
| `SoundPause` | `9BA6D89A` | action | `—` | s:sound, pause:preset |
| `SoundPlay` | `8457B54F` | action | `—` | soundLink:soundlink, players:playergroup, volume:fixed, offset:fixed |
| `SoundPlayAtPoint` | `BBBDE723` | action | `—` | soundLink:soundlink, players:playergroup, location:point, height:fixed, volume:fixed, offset:fixed |
| `SoundPlayAtPointForPlayer` | `37EFFD14` | action | `—` | soundLink:soundlink, owningPlayer:int, audibleMask:playergroup, location:point, height:fixed, volume:fixed, offset:fixed |
| `SoundPlayForPlayer` | `651D9322` | action | `—` | soundLink:soundlink, owningPlayer:int, audibleMask:playergroup, volume:fixed, offset:fixed |
| `SoundPlayOnUnit` | `2E34DB85` | action | `—` | soundLink:soundlink, players:playergroup, unit:unit, height:fixed, volume:fixed, offset:fixed |
| `SoundPlayOnUnitForPlayer` | `63857CE2` | action | `—` | soundLink:soundlink, owningPlayer:int, audibleMask:playergroup, unit:unit, height:fixed, volume:fixed, offset:fixed |
| `SoundPlayScene` | `4A5C98F6` | action | `—` | soundLink:soundlink, players:playergroup, units:unitgroup, animation:modelanim |
| `SoundPlaySceneFile` | `BEB5B53A` | action | `—` | soundLink:soundlink, players:playergroup, file:string, camera:string |
| `SoundPlaySceneForPlayer` | `ABB68C4F` | action | `—` | soundLink:soundlink, owningPlayer:int, audibleMask:playergroup, units:unitgroup, animation:modelanim |
| `SoundPortraitModel` | `63148912` | call | `gamelink<Model>` | soundLink:soundlink |
| `SoundSetFactors` | `54739F28` | action | `—` | distance:fixed, doppler:fixed, rolloff:fixed |
| `SoundSetListenerGender` | `1882D01B` | action | `—` | soundLink:soundlink, gender:preset |
| `SoundSetMuted` | `16D6316F` | call | `actormsg` | mutedState:bool, fade:bool |
| `SoundSetOffset` | `674435EE` | call | `actormsg` | offset:int |
| `SoundSetOffset` | `5CF85ABA` | action | `—` | s:sound, offset:fixed, offsetType:preset |
| `SoundSetPaused` | `F163BD1A` | call | `actormsg` | pausedState:bool, fade:bool |
| `SoundSetPosition` | `00000185` | action | `—` | s:sound, position:point, height:fixed |
| `SoundSetReverb` | `7668458D` | action | `—` | reverb:gamelink<Reverb>, duration:fixed, ambient:bool, global:bool |
| `SoundSetReverbForPlayers` | `F7BB6A26` | action | `—` | players:playergroup, reverb:gamelink<Reverb>, duration:fixed, ambient:bool, global:bool |
| `SoundSetVolume` | `00000184` | action | `—` | s:sound, volume:fixed |
| `SoundStop` | `00000183` | action | `—` | s:sound, fade:preset |
| `SoundStopAllModelSounds` | `08EA3333` | action | `—` | — |
| `SoundStopAllTriggerSounds` | `1DDE5BDA` | action | `—` | fade:preset |
| `SoundSubtitleText` | `5AF17B44` | call | `text` | soundLink:soundlink |
| `SoundtrackDefault` | `678683E1` | action | `—` | players:playergroup, category:preset, soundtrackID:gamelink<Soundtrack>, cue:int, index:int |
| `SoundtrackPause` | `5A41C578` | action | `—` | players:playergroup, category:preset, pause:preset, fade:preset |
| `SoundtrackPlay` | `9D67F076` | action | `—` | players:playergroup, category:preset, soundtrackID:gamelink<Soundtrack>, cue:int, index:int, makeDefault:preset |
| `SoundtrackSetContinuous` | `12FCBA7A` | action | `—` | players:playergroup, category:preset, continuous:preset |
| `SoundtrackSetDelay` | `AF1FAF75` | action | `—` | players:playergroup, category:preset, continuous:fixed |
| `SoundtrackSetShuffle` | `7FD4FA0E` | action | `—` | players:playergroup, category:preset, cue:preset, index:preset |
| `SoundtrackStop` | `BF972A93` | action | `—` | players:playergroup, category:preset, fade:preset |
| `SoundtrackStopCurrent` | `29E51225` | action | `—` | players:playergroup, category:preset, fade:preset |
| `SoundtrackWait` | `76E5F423` | action | `—` | soundtrack:gamelink<Soundtrack> |
| `SoundWait` | `00000408` | action | `—` | sound:sound, offset:fixed, offsetType:preset |
| `SquareRoot` | `00000012` | call | `fixed` | x:fixed |
| `SquareRootI` | `7CF39D61` | call | `int` | x:fixed |
| `StartProfileRun` | `8289E452` | action | `—` | inTestName:text |
| `StatEventAddDataFixed` | `EC2BD155` | action | `—` | statEvent:preset, key:string, value:fixed |
| `StatEventAddDataInt` | `A0A2962F` | action | `—` | statEvent:preset, key:string, value:int |
| `StatEventAddDataString` | `32BA9E2D` | action | `—` | statEvent:preset, key:string, value:string |
| `StatEventCreate` | `724BBE1B` | action | `—` | eventName:string |
| `StatEventLastCreated` | `D2B30562` | call | `preset` | — |
| `StatEventSend` | `365A883E` | action | `—` | statEvent:preset |
| `StatusDecrement` | `603D4494` | call | `actormsg` | statusVariable:string |
| `StatusIncrement` | `61475924` | call | `actormsg` | statusVariable:string |
| `StopAllVideoTexturesOnUnit` | `82A56C6E` | action | `—` | unit:unit |
| `StopFlashingScreenButton` | `C1174045` | action | `—` | screenButtonID:int |
| `StopLooping` | `7B4A4D9D` | action | `—` | — |
| `StopProfileRun` | `AF64C86A` | action | `—` | — |
| `StopPulsingScreenImage` | `8F6C2A63` | action | `—` | screenImageID:int |
| `StopTimer` | `5C9399D4` | action | `—` | timer:timer |
| `StoreUnitSelection` | `9A0A8B06` | action | `—` | forPlayer:int, storeOption:preset |
| `StoryCreatePlanetPanel` | `10C7E0AB` | action | `—` | — |
| `StoryMode` | `15536611` | action | `—` | players:playergroup, storyMode:bool |
| `StoryMode` | `B88E5C2B` | action | `—` | players:playergroup, onOff:preset |
| `StorySetChange` | `BD076980` | action | `—` | — |
| `StringCase` | `00000008` | call | `string` | s:string, case:preset |
| `StringCompare` | `D1588D5B` | call | `int` | s1:string, s2:string, sens:preset |
| `StringContains` | `00000011` | call | `bool` | s1:string, s2:string, loc:preset, sens:preset |
| `StringEqual` | `00000010` | call | `bool` | s1:string, s2:string, sens:preset |
| `StringExternal` | `BC53F705` | call | `text` | path:string |
| `StringExternalAsset` | `3BB0CA58` | call | `text` | path:string |
| `StringExternalHotkey` | `AF39D31D` | call | `text` | path:string |
| `StringFind` | `4E152EAE` | call | `int` | string:string, substring:string, sensitivity:preset |
| `StringLength` | `00000007` | call | `int` | s:string |
| `StringReplace` | `A6A76E21` | call | `string` | string:string, replaceString:string, start:int, end:int |
| `StringReplaceWord` | `1ECBD20E` | call | `string` | string:string, findString:string, replaceString:string, count:int, sensitivity:preset |
| `StringSub` | `00000009` | call | `string` | s:string, start:int, end:int |
| `StringToAbilCmd` | `FE8E0EB8` | call | `abilcmd` | val:string |
| `StringToDateTime` | `23639A2E` | call | `datetime` | string:string |
| `StringToFixed` | `00000006` | call | `fixed` | val:string |
| `StringToInt` | `00000005` | call | `int` | val:string |
| `StringToText` | `55C79F96` | call | `text` | val:string |
| `StringToText` | `B843D120` | call | `actormsg` | val:string |
| `StringToText2` | `E4B86923` | call | `string` | val:anygamelink |
| `StringToText22` | `95AB960D` | call | `string` | val:convstateindex |
| `StringToText222` | `2130CFCE` | call | `convstateindex` | val:string |
| `StringToText23` | `7D1F0181` | call | `string` | val:userinstance |
| `StringToText24` | `DF489D52` | call | `string` | val:fontstyle |
| `StringWord` | `A078FB65` | call | `string` | string:string, index:int |
| `Switch` | `91C49196` | action | `—` | value:anycompare +2sub |
| `SwitchCase` | `3A1227AB` | action | `—` | value:sameasparent +1sub |
| `SwooshCamera` | `3766D08E` | action | `—` | player:int, distance1:fixed, distance2:fixed, location:point, duration:fixed |
| `SynchronousGameStartTimeGet` | `12F29E83` | call | `int` | — |
