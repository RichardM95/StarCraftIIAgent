# SC2 Native Functions: E

Columns are documented in [../triggers-native-functions.md](../triggers-native-functions.md). Reference in XML as `<FunctionDef Type="FunctionDef" Library="Ntve" Id="<ID>"/>`.

Parameter defaults in `nativelib` do not auto-apply; emit an explicit `<Parameter Type="Param" Id="..."/>` for every slot in generated `<FunctionCall>` XML.

### E

<a id="e"></a>

| Name | ID | Kind | Returns | Params |
|---|---|---|---|---|
| `EffectHistoryCount` | `EC54A169` | call | `int` | history:effecthistory |
| `EffectHistoryGetAbil` | `E120F0A6` | call | `gamelink<Abil>` | history:effecthistory, index:int |
| `EffectHistoryGetAmountFixed` | `C3A6E6C7` | call | `fixed` | history:effecthistory, index:int, amount:preset, total:preset |
| `EffectHistoryGetAmountInt` | `A83C6E46` | call | `int` | history:effecthistory, index:int, amount:preset, total:preset |
| `EffectHistoryGetEffect` | `4F485352` | call | `gamelink<Effect>` | history:effecthistory, index:int, effect:preset |
| `EffectHistoryGetTime` | `476AD761` | call | `fixed` | history:effecthistory, index:int |
| `EffectHistoryGetType` | `62465F0F` | call | `preset` | history:effecthistory, index:int |
| `EffectHistoryGetUnitByLocation` | `2AFED320` | call | `unit` | history:effecthistory, index:int, unit:preset |
| `EffectHistoryGetWeapon` | `977A86F1` | call | `gamelink<Weapon>` | history:effecthistory, index:int |
| `EngineReset` | `0C104B6C` | action | `—` | — |
| `EnvironmentShow` | `F5C63A46` | action | `—` | environmentType:preset, showHide:preset |
| `EventAlert` | `A7024352` | call | `gamelink<Alert>` | — |
| `EventBattleReportPanelDifficultySelected` | `129BCCC1` | call | `difficulty` | — |
| `EventBattleReportPanelMissionSelected` | `410E5FBD` | call | `preset` | — |
| `EventBattleReportPanelSceneSelected` | `5BE46847` | call | `preset` | — |
| `EventButtonPressed` | `A506FF54` | call | `gamelink<Button>` | — |
| `EventCameraMoveReason` | `2F74B2A2` | call | `preset` | — |
| `EventChatMessage` | `00000122` | call | `string` | m:preset |
| `EventCheatUsed` | `B658B97F` | call | `preset` | — |
| `EventCommandErrorAbilCmd` | `44BB3417` | call | `abilcmd` | — |
| `EventCommandErrorValue` | `3F185475` | call | `preset` | — |
| `EventConversation` | `00000466` | call | `conversation` | — |
| `EventConversationReply` | `00000467` | call | `reply` | — |
| `EventConversationState` | `A1D59D71` | call | `convstateindex` | — |
| `EventCustomDialogResult` | `109B6B81` | call | `preset` | — |
| `EventCutsceneBookmark` | `5669CBC2` | call | `string` | — |
| `EventCutsceneId` | `798AC00C` | call | `preset` | — |
| `EventDialogControl` | `305EC1D4` | call | `control` | — |
| `EventDialogControlEventType` | `F4C1F96C` | call | `preset` | — |
| `EventDialogControlMouseButton` | `2227686B` | call | `preset` | — |
| `EventGameMenuItemSelected` | `585EFA98` | call | `preset` | — |
| `EventGameTimeEvent` | `23F0A010` | call | `preset` | — |
| `EventGameUser` | `8603728B` | call | `preset` | — |
| `EventGenericName` | `346CD628` | call | `string` | — |
| `EventHotkeyPressed` | `86582BB2` | call | `preset` | — |
| `EventItemAbilityOrUnitAbility` | `E7FCABB7` | call | `abilcmd` | — |
| `EventKeyAlt` | `A7C9E6B1` | call | `bool` | — |
| `EventKeyControl` | `274327C0` | call | `bool` | — |
| `EventKeyPressed` | `CCCD0A10` | call | `preset` | — |
| `EventKeyShift` | `DFB0AB0D` | call | `bool` | — |
| `EventMouseClickedButton` | `58FBAD08` | call | `preset` | — |
| `EventMouseClickedPosXUI` | `43B3E049` | call | `int` | — |
| `EventMouseClickedPosXWorld` | `D606E2CD` | call | `fixed` | — |
| `EventMouseClickedPosYUI` | `86F097AA` | call | `int` | — |
| `EventMouseClickedPosYWorld` | `451E6FB0` | call | `fixed` | — |
| `EventMouseClickedPosZWorld` | `4916AF3C` | call | `fixed` | — |
| `EventMouseMovedPosXUI` | `177BC870` | call | `int` | — |
| `EventMouseMovedPosXWorld` | `D22038F6` | call | `fixed` | — |
| `EventMouseMovedPosYUI` | `48452E5F` | call | `int` | — |
| `EventMouseMovedPosYWorld` | `032677A8` | call | `fixed` | — |
| `EventMouseMovedPosZWorld` | `3126BE7F` | call | `fixed` | — |
| `EventMouseWheelSpin` | `E194768D` | call | `fixed` | — |
| `EventPingedMinimap` | `25B67D5F` | call | `bool` | — |
| `EventPingOption` | `6471FA62` | call | `int` | — |
| `EventPingPoint` | `47CE984E` | call | `point` | — |
| `EventPingUnit` | `3AF81856` | call | `unit` | — |
| `EventPingUnitControlPlayer` | `054275DF` | call | `int` | — |
| `EventPingUnitIsUnderConstruction` | `8B98D4F9` | call | `bool` | — |
| `EventPingUnitPosition` | `035EAAEF` | call | `point` | — |
| `EventPingUnitType` | `E85E42E0` | call | `gamelink<Unit>` | — |
| `EventPingUnitUpkeepPlayer` | `BB8134D2` | call | `int` | — |
| `EventPlanetPanelDifficultySelected` | `0DFB367A` | call | `difficulty` | — |
| `EventPlanetPanelMissionSelected` | `4FA1D0CD` | call | `planet` | — |
| `EventPlayer` | `00000053` | call | `int` | — |
| `EventPlayerEffectUsed` | `7827DA5C` | call | `gamelink<Effect>` | — |
| `EventPlayerEffectUsedAbil` | `1E4D891C` | call | `gamelink<Abil>` | — |
| `EventPlayerEffectUsedAmountFixed` | `C132A7D1` | call | `fixed` | amountType:preset, total:bool |
| `EventPlayerEffectUsedAmountInt` | `F8127598` | call | `int` | amountType:preset, total:bool |
| `EventPlayerEffectUsedItem` | `5CA38E6D` | call | `unit` | — |
| `EventPlayerEffectUsedItemType` | `338C4772` | call | `gamelink<Unit>` | — |
| `EventPlayerEffectUsedPoint` | `0E9617C3` | call | `point` | location:preset |
| `EventPlayerEffectUsedSourceBehavior` | `A7A8E34A` | call | `gamelink<Behavior>` | — |
| `EventPlayerEffectUsedUnit` | `BADA9C08` | call | `unit` | location:preset |
| `EventPlayerEffectUsedUnitImpact` | `C354001C` | call | `unit` | — |
| `EventPlayerEffectUsedUnitLaunch` | `DDF1E5C5` | call | `unit` | — |
| `EventPlayerEffectUsedUnitOwner` | `DBE94B43` | call | `int` | location:preset |
| `EventPlayerEffectUsedUnitType` | `3AEFE731` | call | `gamelink<Unit>` | location:preset |
| `EventPlayerEffectUsedWeapon` | `E73751F6` | call | `gamelink<Weapon>` | — |
| `EventPlayerProperty` | `A57F57DA` | call | `preset` | — |
| `EventPlayerPropertyChangeFixed` | `040F0304` | call | `fixed` | — |
| `EventPlayerPropertyChangeInt` | `686859EE` | call | `int` | — |
| `EventPlayerWave` | `34041821` | call | `wave` | — |
| `EventPurchaseMade` | `7734441D` | call | `preset` | — |
| `EventResourceRequestAmount` | `4D5B437D` | call | `int` | resourceType:preset |
| `EventResourceTradeAmount` | `62514997` | call | `int` | resourceType:preset |
| `EventResourceTradeRecipient` | `9906C4A0` | call | `int` | — |
| `EventTargetModeAbilCmd` | `650C0947` | call | `abilcmd` | — |
| `EventTargetModeState` | `4F235804` | call | `preset` | — |
| `EventTimer` | `19ABD428` | call | `timer` | — |
| `EventTrigger` | `561B0A1E` | call | `trigger` | — |
| `EventUnit` | `00000092` | call | `unit` | — |
| `EventUnitAbility` | `00000314` | call | `abilcmd` | — |
| `EventUnitAbilityOtherUnit` | `102B1CE1` | call | `unit` | — |
| `EventUnitAbilityStage` | `00000309` | call | `preset` | — |
| `EventUnitAttributePoints` | `22EA61EC` | call | `int` | — |
| `EventUnitBehavior` | `00000355` | call | `gamelink<Behavior>` | — |
| `EventUnitBehaviorChange` | `BC460968` | call | `preset` | — |
| `EventUnitCargo` | `00000209` | call | `unit` | — |
| `EventUnitCreatedAbil` | `5FB839EE` | call | `gamelink<Abil>` | — |
| `EventUnitCreatedBehavior` | `049B93BD` | call | `gamelink<Behavior>` | — |
| `EventUnitCreatedUnit` | `11EB5EB1` | call | `unit` | — |
| `EventUnitDamageAbsorbed` | `98DA6AD1` | call | `fixed` | — |
| `EventUnitDamageAmount` | `00000098` | call | `fixed` | — |
| `EventUnitDamageAttempted` | `C3E29B47` | call | `fixed` | — |
| `EventUnitDamageAttemptedVitals` | `FECF5F24` | call | `fixed` | — |
| `EventUnitDamageBehaviorShield` | `3E5CC42D` | call | `fixed` | — |
| `EventUnitDamageDeathCheck` | `00000243` | call | `bool` | deathType:preset |
| `EventUnitDamageEffect` | `E7ABAA18` | call | `gamelink<Effect>` | — |
| `EventUnitDamageKillXP` | `1BD6D194` | call | `int` | — |
| `EventUnitDamageSourcePlayer` | `00000100` | call | `int` | — |
| `EventUnitDamageSourcePoint` | `00000101` | call | `point` | — |
| `EventUnitDamageSourceUnit` | `00000099` | call | `unit` | — |
| `EventUnitDamageVitalsLeeched` | `7A2BE368` | call | `fixed` | vitalType:preset |
| `EventUnitEffectUsed` | `B3949D45` | call | `gamelink<Effect>` | — |
| `EventUnitGetItem` | `F7A67C8E` | call | `unit` | — |
| `EventUnitGetItemType` | `23D22D79` | call | `gamelink<Item>` | — |
| `EventUnitGetWeapon` | `FC12F300` | call | `gamelink<Weapon>` | — |
| `EventUnitHealAmount` | `1FC10431` | call | `fixed` | — |
| `EventUnitHealEffect` | `B975B224` | call | `gamelink<Effect>` | — |
| `EventUnitHealLaunchPlayer` | `C6CB4429` | call | `int` | — |
| `EventUnitHealLaunchUnit` | `5A8971F0` | call | `unit` | — |
| `EventUnitHealVital` | `5D86D199` | call | `preset` | — |
| `EventUnitInventoryChange` | `835EFAFB` | call | `preset` | — |
| `EventUnitInventoryItem` | `D0EBBB91` | call | `unit` | — |
| `EventUnitInventoryItemContainer` | `B94C6E96` | call | `int` | — |
| `EventUnitInventoryItemSlot` | `D613946A` | call | `int` | — |
| `EventUnitInventoryItemTargetPoint` | `C211B081` | call | `point` | — |
| `EventUnitInventoryItemTargetUnit` | `A3ADDDEE` | call | `unit` | — |
| `EventUnitItemUsed` | `61F48E33` | call | `unit` | — |
| `EventUnitOrder` | `00000103` | call | `order` | — |
| `EventUnitOwnerNew` | `7CFC4EDA` | call | `int` | — |
| `EventUnitOwnerOld` | `2EFFA9C5` | call | `int` | — |
| `EventUnitPowerupUnit` | `F27365D4` | call | `unit` | — |
| `EventUnitProgressObjectType` | `56590DD1` | call | `gamelink` | — |
| `EventUnitProgressUnit` | `00000419` | call | `unit` | — |
| `EventUnitProperty` | `68CDC79B` | call | `preset` | — |
| `EventUnitPropertyChangeFixed` | `AF08AFB4` | call | `fixed` | — |
| `EventUnitPropertyChangeInt` | `ABFA76F7` | call | `int` | — |
| `EventUnitRangeUnit` | `B9E1327D` | call | `unit` | — |
| `EventUnitRegion` | `00000094` | call | `region` | — |
| `EventUnitSpentVitalAmount` | `D3FDCBF6` | call | `fixed` | — |
| `EventUnitSpentVitalVital` | `43AE9C7E` | call | `preset` | — |
| `EventUnitTarget` | `4ACABF10` | call | `unit` | — |
| `EventUnitTargetPoint` | `00000312` | call | `point` | — |
| `EventUnitTargetUnit` | `00000313` | call | `unit` | — |
| `EventUnitVictimUnit` | `31573276` | call | `unit` | — |
| `EventUnitXPDelta` | `00000353` | call | `fixed` | — |
| `EventUpgradeLevelDelta` | `81F49744` | call | `int` | — |
| `EventUpgradeName` | `F161CEC9` | call | `gamelink<Upgrade>` | — |
| `EventVictoryPanelDifficultySelected` | `B3BBAF2B` | call | `difficulty` | — |
