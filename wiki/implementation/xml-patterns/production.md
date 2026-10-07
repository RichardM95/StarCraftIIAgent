# Production and Command-Card XML Patterns

## Unit/Structure Cost Modification

`Operation="Multiply"` does **NOT** work for `CostResource` fields. Use `Add`/`Subtract`/`Set`:

```xml
<EffectArray Operation="Subtract" Reference="Unit,Roach,CostResource[Minerals]" Value="38"/>
```

### Batch-trained units (For example Zergling ×2)

Game charges `CostResource × count`. Whether to modify the unit or ability depends on whether the ability InfoArray already has a `Resource` entry:

- **InfoArray has an existing `Resource` entry** → `Subtract` from the ability resource
- **InfoArray has NO existing `Resource` entry** → zero out the unit cost AND `Set` the ability resource

```xml
<!-- Zergling: zero unit cost first, then set ability batch cost -->
<EffectArray Operation="Subtract" Reference="Unit,Zergling,CostResource[Minerals]" Value="25"/>
<EffectArray Operation="Set" Reference="Abil,LarvaTrain,InfoArray[Train2].Resource[Minerals]" Value="25"/>
```

Key ability→unit mapping:
- `LarvaTrain InfoArray[Train2]` → Zergling ×2 (no prior Resource — zero unit + Set ability)

---

## Command-Card Cost Display for Train/Build Buttons

Prefer the native cost display over writing minerals, vespene, build time, or supply into the button tooltip text. It matches Blizzard's native campaign presentation and remains accurate when upgrades modify unit costs.

Native cost strip display (mineral icon + cost, vespene icon + cost, supply icon, and build/cooldown time) relies on three synchronized layers in XML:

1. **Ability Layer (`AbilData.xml`)**:
   - Each `InfoArray` entry on `CAbilTrain` and `CAbilWarpTrain` must have explicit `<Resource index="Minerals" value="..."/>` and `<Resource index="Vespene" value="..."/>` (when > 0) matching the unit's cost.
   - For batch units (e.g. Swarmlings ×3 or Civilians ×2), `InfoArray.Resource` reflects the total batch cost.

2. **Button Layer (`ButtonData.xml`)**:
   - Custom unit production buttons require `<Universal value="1"/>` to tell the SC2 command-card engine to bind universal context for tooltips and hotkeys.
   - Enable tooltip flags: `<TooltipFlags index="ShowResources" value="1"/>`, `<TooltipFlags index="ShowSupply" value="1"/>`, `<TooltipFlags index="ShowTime" value="1"/>`, and `<TooltipFlags index="ShowCooldown" value="1"/>`.

3. **Command-Card & Unit Layer (`UnitData.xml`)**:
   - **Indexed Card Bounds**: On worker build submenus (`PBl1`, `TBl1`, `ZBl1`) and producer cards, command buttons must be wired within the unit's authoritative indexed slots (0..11). Duplicate or unindexed `<LayoutButtons>` entries appended outside the native array stack over slot coordinates and break the engine's build/train ability cost header resolution.
   - **Cost Definition**: The produced unit must have authoritative `<CostResource index="Minerals" value="..."/>`, `<CostResource index="Vespene" value="..."/>`, `<Food value="..."/>`, and `<CostCategory value="Army"/>` (or `Technology`).

```xml
<!-- AbilData.xml -->
<CAbilTrain id="MyGatewayTrain">
    <InfoArray index="Train6" Time="38">
        <Resource index="Minerals" value="100"/>
        <Button DefaultButtonFace="MyCommando" Requirements="MyTrainCommando"/>
        <Unit value="MyCommando"/>
    </InfoArray>
</CAbilTrain>

<!-- ButtonData.xml -->
<CButton id="MyCommando">
    <Icon value="Assets\Textures\btn-unit-terran-marine.dds"/>
    <AlertIcon value="Assets\Textures\btn-unit-terran-marine.dds"/>
    <EditorCategories value="Race:Terran"/>
    <Universal value="1"/>
    <TooltipFlags index="ShowResources" value="1"/>
    <TooltipFlags index="ShowSupply" value="1"/>
    <TooltipFlags index="ShowTime" value="1"/>
    <TooltipFlags index="ShowCooldown" value="1"/>
</CButton>
```

Checklist for custom train/build entries:

- The producer has the ability in `AbilArray`.
- The ability slot has `InfoArray[TrainX].Unit` or `InfoArray[BuildX].Unit` with explicit `Resource` costs.
- The producer command card button is `Type="AbilCmd"` and its `AbilCmd` exactly matches that InfoArray command.
- For the six Protoss production structures (`Gateway`, `WarpGate`, `RoboticsFacility`, `RoboticsFacilityWarp`, `Stargate`, `StargateWarp`), every faction train button must have an existing unit/faction requirement both on the ability button (`InfoArray/Button Requirements`) and on the command-card `LayoutButtons` row. Stacked buttons share command-card slots, so a missing or invalid requirement can remain enabled and block the intended lower button.
- Utility morph buttons restored onto overridden producer command cards, such as Gateway <-> Warp Gate, also need explicit `Type="AbilCmd"` and fixed `Row`/`Column`; inherited/default values are not reliable after masking or replacing card entries by index.
- Structure command-card additions on inherited indexed cards must use an explicit `LayoutButtons index="N"` on a free slot. Unindexed `LayoutButtons` rows between indexed inherited slots are dropped on Editor save.
- Worker build cards (`PBl1`, `TBl1`, `ZBl1`) must modify inherited slot indices directly (e.g. `index="3"` for Gateway on Probe) rather than appending unindexed rows.
- The command-card `Face` and ability `DefaultButtonFace` use the same button ID with `<Universal value="1"/>`.
- The produced unit has `CostResource[Minerals]` / `CostResource[Vespene]` and does not hide resources (`FlagArray[ShowResources]=1`).
- Campaign train commands also need `TechTreeUnitAllow(player, "UnitID", true)` when the unit is normally locked by campaign tech.

`InfoArray.Resource` is **not** a harmless display field. It is an additive cost adjustment on top of the produced unit's cost. Only use it for special cases such as batch units, refunds, or morph deltas after confirming the existing ability data.

### Inherited InfoArray fields and Editor canonicalization

Indexed ability entries inherit unchanged subfields from the same index on their parent ability. A child can replace `InfoArray[Build2].Unit` and its button while retaining the parent's `Time`. When a local field equals the inherited value, the SC2 Editor may remove the redundant serialization on save without changing the effective catalog value.

For example, a child ability may replace `Build2.Unit=Pylon` with a custom structure while `ProtossBuild,Build2` supplies `Time="25"`. The child needs no local time field, and the Editor may remove a repeated child `Time="25"`; this is canonicalization, not a zero-time regression. Before restoring a pruned indexed field, inspect the exact parent index and compare the effective value.

### Split Warp-Train Charges

When a producer needs multiple `CAbilWarpTrain` abilities because one ability cannot reference every produced unit, all split abilities on that producer must use the same unit-local charge link. Do not give each split ability its own self-link, or one structure can warp a unit from ability A and immediately warp another from ability B.

Current live split groups:

| Producer | Split abilities | Shared charge link |
|---|---|---|
| `WarpGate` | `MyWarpGateTrainA`, `MyWarpGateTrainB`, `MyWarpGateTrainC` | `MyWarpGateCharge` |
| `RoboticsFacilityWarp` | `MyRoboticsWarpTrainA`, `MyRoboticsWarpTrainB` | `MyRoboticsWarpCharge` |
| `StargateWarp` | `MyStargateWarpTrainA`, `MyStargateWarpTrainB` | `MyStargateWarpCharge` |

Use `<Location value="Unit"/>` on those charge blocks so cooldown sharing is per structure instance, not global across all structures.

`CAbilWarpTrain` does **not** support batch output the same way `CAbilTrain` does. The SC2 Editor canonicalizes warp train rows back to one `InfoArray.Unit` value and removes repeated child `<Unit value="..."/>` entries. Keep the XML single-unit and implement any required pair/triple output through a project script when the warped unit reaches `c_unitProgressStageComplete`. Do not key this path from the generic unit-created event or `EventUnitCreatedAbil()`; the ability link is not reliable for field-warp construction.

### Warpgate-Produced Non-Protoss Units

When a custom `CAbilWarpTrain` produces a Terran, Zerg, or custom unit through a Protoss Warp Gate / Warp Robotics / Warp Stargate bridge, the produced `CUnit` must have:

```xml
<AbilArray Link="Warpable"/>
```

Normal Gateway/Robotics/Stargate training can work without this, so always test the matching warp producer too. Missing `Warpable` can create the correct custom unit actor plus an extra `GenericUnitFallback` sphere actor, with console warnings like "Unable to create unit actor" and "More than one CActorUnit persisting in the same unit scope."

The unit actor also needs a warp/build visual. In the Data Editor this is shown under the unit actor's visual/build properties; in XML it is `CActorUnit.BuildModel`. For generic non-Protoss bridge units, use:

```xml
<BuildModel value="ProtossGenericWarpInOut"/>
```

Map the produced unit to its actual actor ID before patching this field. Some dependency actors do not match their unit ID; for example, `Spectre` uses `SpecterUnit` and `DuskWing` uses `DuskWingBanshee`.

If the produced unit uses a custom `CActorUnit` that inherits from a named unit actor, also use indexed birth/revive/construction overrides instead of appending new `UnitBirth.CustomUnit` rows. See "Actor Variant from a Named Unit Actor" below.

When creating a local unit actor shim, verify the parent actor's catalog class first. Some Blizzard unit-looking actors, including `HotSHunter` and `Reaper`, are exported as `CActorMissile`; a local `CActorUnit` cannot inherit from them. Use a compatible generic unit parent such as `GenericUnitBase` or `GenericBurrowerStandard`, then copy the needed `Model`, `PlacementModel`, `PortraitModel`, death model, and local unit events explicitly.

### Protoss Warp-Train Visuals

When a custom Protoss unit is produced through `CAbilWarpTrain`, prefer the parent unit's specific one-shot warp-in model on the custom `CActorUnit.BuildModel` instead of the generic bridge model. For example:

| Custom actor | BuildModel |
|---|---|
| `MyZealotVariant` | `ZealotAiurWarpIn` |
| `MySentryVariant` | `SentryAiurWarpIn` |
| `MyImmortalVariant` | `ImmortalAiurWarpIn` |
| `MyDarkTemplarVariant` | `DarkTemplarAiurWarpIn` |

Use active dependency data as the source of truth before choosing a model. Some trainable custom units are based on dependency units that are not normally trained from a warp producer, so they need the closest active Protoss one-shot model.

### Terran Drop Pod Visuals for Field Warp Production

When Terran faction ground units are produced through `CAbilWarpTrain` (Warp Gate / Warp Robotics Facility), use the campaign **Orbital Strike / Barracks drop-train** presentation instead of only the protoss warp sphere.

Reference chain in `DataEditorXML/Liberty Campaign Effects.txt` and `Liberty Campaign Actors.txt`:

| Piece | ID | Role |
|---|---|---|
| Effect set | `DropTrainSet` | `MakePrecursor` hides the unit, then starts `DropTrain` |
| Persistent | `DropTrain` | 2.3s on the produced unit; `FinalEffect` = `RemovePrecursor` |
| Actor | `BarracksDropPod` | Listens for `Effect.DropTrain.Start`; plays falling pod animation |
| Model | `BarracksDropPod` | `DropPodFalling.m3` (same asset family as campaign `TerranDropPod`) |
| Sounds | `BarracksDropPodFall`, `BarracksDropPodUnload` | Fall/unload audio tied to `DropTrain` start/stop |
| Behavior | `Precursor` | `NoDraw` while the pod sequence runs |

**Do not assume `Effect` works on `CAbilWarpTrain`.** The Orbital Strike upgrade patches `CAbilTrain` (`BarracksTrain`) `InfoArray` entries with `Effect="DropTrainSet"`. `CAbilWarpTrain` does not accept that field; the Editor will warn and the attribute is ignored.

**Do not gate drop pods on `ProtossGenericWarpInOut` behavior.** Field warp uses unit construction plus `CActorUnit.BuildModel=ProtossGenericWarpInOut`, which creates the protoss warp actor on `UnitConstruction.{unit}.Start`. That is separate from the `ProtossGenericWarpInOut` behavior buff. A validator that checks the behavior count will fail during warp-train construction.

**Do gate field warp only with `UnderConstruction`.** Gateway `CAbilTrain` production at the structure should keep normal protoss warp-in and must not spawn drop pods. Use `CValidatorUnitFilters` with `Filters value="UnderConstruction;-"`.

Example project wiring:

```xml
<!-- Ground unit: passive trigger behavior -->
<CBehaviorBuff id="MyTerranWarpDropPod">
    <InfoFlags index="Hidden" value="1"/>
    <Requirements value="HaveMyTerranFaction"/>
    <InitialEffect value="MyTerranWarpDropPodSet"/>
</CBehaviorBuff>

<!-- Short delay so construction state exists before the execute step -->
<CEffectSet id="MyTerranWarpDropPodSet">
    <EffectArray value="MyTerranWarpDropPodApplyDelay"/>
</CEffectSet>
<CEffectApplyBehavior id="MyTerranWarpDropPodApplyDelay">
    <Behavior value="MyTerranWarpDropPodDelay"/>
</CEffectApplyBehavior>
<CBehaviorBuff id="MyTerranWarpDropPodDelay">
    <Duration value="0.125"/>
    <ExpireEffect value="MyTerranWarpDropPodExecute"/>
</CBehaviorBuff>
<CEffectSet id="MyTerranWarpDropPodExecute">
    <EffectArray value="DropTrainSet"/>
    <ValidatorArray value="MyTerranWarpFieldWarpIn"/>
</CEffectSet>

<CValidatorUnitFilters id="MyTerranWarpFieldWarpIn">
    <Filters value="UnderConstruction;-"/>
</CValidatorUnitFilters>
```

Attach `MyTerranWarpDropPod` through `BehaviorArray Link` on Terran ground units only and exclude air units. Replace the `My` prefix and requirement with the project's configured equivalents.

**Preload the full drop-pod chain.** Referencing only `Effect=DropTrainSet` in `PreloadAssetDB.txt` is not enough. If `MakePrecursor` runs but `BarracksDropPod` is not preloaded, the unit stays invisible until `RemovePrecursor` and no pod appears. Also preload:

- Actors: `BarracksDropPod`, `BarracksDropPodFall`, `BarracksDropPodUnload`
- Model: `BarracksDropPod`
- Effects: `DropTrain`, `MakePrecursor`, `RemovePrecursor`
- Behavior: `Precursor`

**Failed approaches to avoid:**

- Patching `ProtossGenericWarpInOut` with `InitialEffect` — engine-applied warp construction does not reliably fire that behavior's initial effect.
- `UnitConstruction.*.Start` wildcard actor events on all Terran unit actors — caused overlapping Terran health bars/outlines on protoss structure warp-ins and did not reliably show pods on mercenary warp-ins.
- `DropTrainSet` without actor/model preload — hides the unit via `MakePrecursor` but shows no pod.

Some campaign hire units already have an alternate drop presentation through `MercGroundDrop` and unit-specific `*DropModel` actors (`MercDropModelBase` → `DropPodFalling`). A project can instead use the Barracks / Orbital Strike chain above to give its Terran ground units shared pod visuals without per-unit actor wiring.

### Zerg Unburrow Visuals for Field Warp Production

When Zerg ground units are produced through `CAbilWarpTrain`, use a presentation-only unburrow actor instead of creating a temporary burrowed unit. Creating a real burrowed unit would require issuing its unburrow command and cleaning up duplicate gameplay units; the safer pattern leaves the warp-trained unit authoritative and creates only a transient `CActorModel`.

Example project wiring:

```xml
<CBehaviorBuff id="MyZergWarpUnburrowVisual">
    <InfoFlags index="Hidden" value="1"/>
    <Requirements value="HaveMyZergFaction"/>
    <InitialEffect value="MyZergWarpUnburrowVisualSet"/>
</CBehaviorBuff>

<CEffectApplyBehavior id="MyZergWarpUnburrowVisualExecute">
    <Behavior value="MyZergWarpUnburrowVisualMarker"/>
    <ValidatorArray value="MyTerranWarpFieldWarpIn"/>
</CEffectApplyBehavior>

<CActorModel id="MyZergWarpUnburrowVisualSwarmling" parent="ModelAdditionNoAnims">
    <Model value="HotSSwarmling"/>
    <Inherits index="Opacity" value="0"/>
    <Inherits index="Visibility" value="0"/>
    <On Terms="Behavior.MyZergWarpUnburrowVisualMarker.On; ValidateUnit CasterHotSSwarmling" Send="Create"/>
    <On Terms="ActorCreation" Send="AnimBracketStart Burrow Burrow IGNORE Unburrow ClosingFull,OpeningPlayForever,Instant"/>
    <On Terms="ActorCreation" Send="TimerSet 0.062500 Unburrow"/>
    <On Terms="TimerExpired; TimerName Unburrow" Send="AnimBracketStop Burrow"/>
    <On Terms="TimerExpired; TimerName Unburrow" Send="TimerSet 2.000000 Destroy"/>
    <On Terms="TimerExpired; TimerName Destroy" Send="Destroy"/>
</CActorModel>
```

Attach `MyZergWarpUnburrowVisual` only to ground Zerg units with a known burrowed counterpart and a unit model that supports the Burrow/Unburrow animation bracket. Confirm each selected unit's model supports the Burrow/Unburrow animation bracket.

Keep the `UnderConstruction` validator on the automatic marker application so normal Gateway/Robotics/Stargate train-at-structure production does not show the field-warp unburrow actor. If a map creates a unit through Galaxy and immediately replaces it with a Zerg unit, prefer creating the real burrowed form and issuing its native unburrow order from Galaxy. This matches the engine's normal burrow/unburrow actor path and avoids relying on a presentation-only effect that may fire before the created unit's actor scope is ready.

Confirmed scripted-arrival examples:

- `RoachCorpser` -> create `RoachCorpserBurrowed`, issue `BurrowHotSCorpserUp`.
- A custom roach variant -> create its custom burrowed variant and issue its custom unburrow command.
- A custom hydralisk variant -> create its custom burrowed variant and issue its custom unburrow command.

An explicit scripted delay behavior remains a fallback when a real burrowed form or unburrow command is unavailable. For the actor-marker path, preload the scripted delay/execute/marker rows alongside every actor/model row, and keep `CValidatorUnitType` validators explicit with `WhichUnit Value="Caster"`.

### Static Stacked Campaign Production Buttons

For LotV campaign production structures, prefer static XML button stacks over runtime command-card edits:

- Put each faction's train button on the same Row/Column as its vanilla anchor.
- Give every stacked button a mutually exclusive requirement. Exactly one button in a stack should satisfy `Show`/`Use` for a player.
- Add buttons to the card layer the structure actually opens. Campaign structures often have both `CardLayouts index="0"` and a second campaign card layer; grep the vanilla unit first and patch the same layer as the relevant `*TrainAI` buttons.
- If inherited vanilla buttons conflict with project buttons, hide them with data requirements that become false when the project upgrades are granted. Avoid `CatalogFieldValueSet` command-card rewrites for production UI.
- Keep names/tooltips anchored on real `CButton` and train ability data. Runtime-only strings are vulnerable to SC2 Editor pruning.
- Keep custom `CButton` rows in `ButtonData.xml`, not broad `GameData.xml`. If an Editor save regenerates typed `ButtonData.xml` rows for buttons moved to `GameData.xml`, treat that as a canonicalization signal and remove the duplicate entry.
- Let production button faces use the Editor-normalized icon-only shape (`Icon`, `AlertIcon`, `EditorCategories`, plus any non-cost display flags such as cooldown/autocast) **and** direct `Name`/`Tooltip` fields pointing at `Button/Name/{id}` and `Button/Tooltip/{id}`. After adding new train/build `CButton` rows, run `python tools/audit-gamestrings-anchors.py`; after an Editor save, use `--fill` to restore keys that still exist in `ObjectStrings.txt`.
- If `GameStrings.txt` loses a key that is still referenced by `Name`, `Tooltip`, or `Description` XML, restore the key or remove the stale XML reference. If the lost key is only helper/editor metadata, prefer `ObjectStrings.txt` or no player-facing anchor.

For Drone build submenus, use the vanilla submenu IDs when adding buttons:

```xml
<CardLayouts index="1" CardId="ZBl1">...</CardLayouts>
<CardLayouts index="2" CardId="ZBl2">...</CardLayouts>
```

Use both the inherited submenu index and the vanilla `CardId`. `CardId` is the submenu target (`ZBl1` / `ZBl2`), while `index` ensures the mod patch overrides the inherited Drone submenu instead of appending a duplicate card that the command card may not open.

---
