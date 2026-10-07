# Catalog Rules and Inheritance XML Patterns

## Effective-Value Evidence Before Source Changes

Before editing a statistic, prove the effective value rather than inferring it from the leaf XML row. Record the local unit or catalog object, its `parent`, the inherited value at the exact field/index, and the intended local override. Check the active dependency chain and Editor canonicalization when a local field is absent or is removed on save. A value copied into a child row may be redundant; a missing child field may still be correct if the parent supplies the intended value.

For UI text, first classify the observed surface as **world hover**, **selection panel**, **command-card button**, **tooltip**, or **editor text**. Then trace that surface to its owning catalog object and effective localization anchor. Do not change a `GameStrings.txt` key until the UI surface and the XML field that consumes it are identified; similarly, do not change a unit name or actor highlight field to fix text owned by a button or tooltip.

This evidence is a prerequisite for the `root cause confirmed` state in the [issue lifecycle](../testing-feedback-workflow.md#6-stage-issue-lifecycle). Include it in the issue record before making the source fix.

## Mission-Local Overrides and Variant Isolation

Use a map-local catalog override only when a set piece, objective, boss, or
terrain interaction is unique to that mission. Keep it small and name the
owning map/mechanic in the implementation notes. Reusable faction mechanics
belong in the project mod behind the configured project prefix instead.

Do not override a vanilla ID merely to create a faction variant: it changes
every dependency consumer that resolves that ID and can defeat the project's
replacement isolation. Use a parented project-prefixed variant for selectable faction
content. A same-ID override is reserved for an explicitly intended,
campaign-wide change and still requires effective-value evidence and an
Editor test of affected maps.

## Footprints and Creep Placement

Use `DataEditorXML/* Footprints.txt` before changing `CUnit.Footprint` or `CUnit.PlacementFootprint`. Footprints are not just IDs: Blizzard footprints can carry `Check`, `Place`, and `Pathing` layers plus a `Shape`. When making a creep-friendly building footprint, preserve the original footprint's size/shape/layers and only clear the creep blocker.

Confirmed useful references:

- `Liberty Mod Footprints.txt`: `Footprint2x2IgnoreCreepContour` and `Footprint3x3IgnoreCreepContour` are the native editor examples. They use `parent="Footprint2x2"` / `parent="Footprint3x3"`, clear `Negative[Creep]`, keep `Negative[Fogged]`, and add contour/pathing shape data.
- `Footprint5x5DropOff` and `Footprint5x5Contour` preserve town-hall resource/drop-off behavior; keep `NearResources` / `DropOff` sets when cloning them.
- Geyser structures use both `FootprintGeyserRoundedBuilt` and `Footprint3x3CappedGeyser`; keep their resource-adjacency/capped-geyser layout when making creep-friendly variants.

---

## RequirementNodeData Patterns

```xml
<!-- CRequirementNot child field: -->
<OperandArray index="0" value="NodeID"/>   <!-- NOT NodeArray or Value -->

<!-- CRequirement: -->
<NodeArray index="Show" Link="NodeID"/>
```

**When adding a new `CRequirement` + `CRequirementCountUpgrade`**, always add 4 lines to `ObjectStrings.txt`:
```
Requirement/EditorPrefix/HaveMyUpgrade=My
Requirement/Name/HaveMyUpgrade=Have MyUpgrade
RequirementNode/EditorPrefix/CountMyUpgrade=My
RequirementNode/Name/CountMyUpgrade=Count MyUpgrade
```

---

## Pre-Existing Validators (do NOT redefine — reference by name from Void.SC2Mod)

- `SourceIsNotStationary` — unit movement speed > 0

---

## Combine Validators

`CValidatorCombine` defaults to `Type="Or"` through the catalog default record. For simple OR validators, omit the explicit `<Type value="Or"/>`; the SC2 Editor may canonicalize it away on save. Use explicit `<Type value="And"/>` only when all child validators must pass, and use `<Negate value="1"/>` to invert the combine result instead of `Type="Not"`.

---

## CBehaviorBuff WeaponRange

```xml
<CBehaviorBuff.Modification WeaponRange="1"/>  <!-- adds +1 to ALL weapon ranges -->
```

---

## Cross-Mod Array Overrides

When a local catalog row uses the same ID as a row in another loaded mod, give array overrides explicit indices. An unindexed `EffectArray` in a later `CEffectSet` can append to the earlier mod's array rather than replace its element. In particular, `VortexEffectGA` occurs in both `SCORE-Golden.SC2Mod` and `Heros.SC2Mod`; its five effects and two validators in Heros must use indices `0` onward so the combined load does not exceed the effect array's supported positions.

## Autocast Configuration

To make an ability autocast (AI-controlled casting), configure it in the Data Editor → Abilities tab:

1. **Enable autocast:** In `Stats - Flags`, check `Auto Cast`. Check `Auto Cast (On)` if it should be enabled by default.
2. **Targeting filters:** Set `Auto Cast Filters` to restrict who the ability targets (e.g. `Enemy`, `Visible`, `Biological`). Filters only check general attributes (alliance, structure status) — not specific unit types.
3. **Conditional grouping (Validators):** Use `Auto Cast Validators` for rules the ability cannot express through filters alone — e.g. "only cast when 3+ enemies are in range". Create a `UnitCount` or `UnitFilter` validator and attach it here.

For area effects, set the radius in the ability's Search Area effect to define what counts as a "group".

Recent bug pattern: filters alone are usually too broad for custom campaign abilities. If autocast could drain/heal/buff the wrong family of unit, add validators for the exact target set and keep a Galaxy handler guard when the ability has a scripted side effect. When handling a cast in Galaxy, prefer `EventUnit()` and `EventUnitTargetUnit()` from the ability event over "nearest unit" inference.

---

## XML Comment Hygiene

SC2 XML is strict XML: do not put `--` inside a comment body. A comment like `<!-- foo -- bar -->` will make the editor reject the file even though the data itself is fine. Prefer short ASCII comments, and skip comments when the XML entry is obvious.

---

## EditorCategories Must Match Active Dependency Tabs

Do not copy `EditorCategories` blindly from inactive exports. Those exports can contain editor category buckets that are not recognized by the active dependency stack.

Before setting or bulk-normalizing categories, grep the active `DataEditorXML/` dump for the same catalog/tab and use only values proven there. Common active categories include race buckets such as `Race:Terran`, `Race:Protoss`, `Race:Zerg`, and `Race:Neutral`; ability/behavior categories such as `Race:Zerg,AbilityorEffectType:Units`; upgrade categories such as `Race:Zerg,UpgradeType:Talents`; and unit categories based on `ObjectType` / `ObjectFamily` such as `ObjectType:Unit,ObjectFamily:Campaign`.

Unit data does not use the imported StarCoop faction families in the active dumps. For imported campaign/faction units, collapse unsupported families like `FactionMecha`, `FactionPrimal`, `FactionInfested`, `FactionCovertOps`, `FactionRaider`, `FactionPurifier`, and `FactionTaldarim` to a valid active family such as `ObjectFamily:Campaign` while preserving the `ObjectType` (`Unit`, `Structure`, `Projectile`, `Hero`, or `Other`).

Sound categories are an exception in this repo because the active `DataEditorXML/` reference set does not include sound dumps. Treat user/Editor-saved `SoundData.xml` categories as the current canonical signal unless matching active sound dumps are added later.

---

## Editor-Saved Split Catalog Duplicates

When the SC2 Editor saves a standard catalog entry into a dedicated file such as `EffectData.xml`, remove any older definition of the same `(catalog type, id)` from `GameData.xml` or side catalog files. The loader treats all files under `Base.SC2Data/GameData/` as one catalog namespace, so `CEffectSet id="Example"` in both `GameData.xml` and `EffectData.xml` produces an `Unable to create duplicate entry` warning even if the rows are identical.

Keep references, preload rows, and localization anchors unless they are stale. Only one XML definition should remain for each `(catalog type, id)`.

Prefer typed catalog files for authored faction data. Mixed side catalogs are easy to hand-edit, but the Editor/runtime is more reliable when each row lives in its standard catalog file: `CUnit` in `UnitData.xml`, `CButton` in `ButtonData.xml`, `CAbil*` in `AbilData.xml`, `CBehavior*` in `BehaviorData.xml`, `CEffect*` in `EffectData.xml`, `CRequirement` in `RequirementData.xml`, requirement nodes in `RequirementNodeData.xml`, validators in `ValidatorData.xml`, models in `ModelData.xml`, movers in `MoverData.xml`, and upgrades in `UpgradeData.xml`. Do not introduce new custom catalog filenames without an Editor round-trip reason.

After splitting a side catalog, open and close the migrated entries in the SC2 Editor once. The Editor may strip redundant `CButton` name/tooltip fields when localization already provides them, add `PreloadAssetDB.txt` unit/effect rows, and expose broken icon paths that local XML parsing cannot detect. Accept those normalizations when the mod reopens without XML warnings.

---

## Actor Variant from a Named Unit Actor (parent="SomeUnitActor")

When creating a unit actor that inherits visuals/sounds from a specific unit's actor (e.g. `parent="Ravager"`), the `##unitName##` macro does **NOT** resolve to the leaf actor's own `unitName`. It resolves to the **nearest ancestor in the parent chain that defines `unitName`**. For `parent="Ravager"` (which has `unitName="Ravager"`), all inherited events still say `UnitBirth.Ravager`, `UnitRevive.Ravager`, etc. — even if the child defines `unitName="MyMyVariant"`.

**Fix:** Override every unit-name-specific event by index in the child actor.

Warning example: `Supplicant` once used `parent="Zealot"` with appended `UnitBirth.Supplicant` / `UnitRevive.Supplicant` / `UnitConstruction.Supplicant.Start` events. Standard vanilla Zealots then created both `CActorUnit[Zealot]` and `CActorUnit[Supplicant]` in the same unit scope, producing the warning `More than one CActorUnit persisting in the same unit scope`. The fix was to override indexes 0, 1, 2, 3, and 5 on the `Supplicant` actor instead of appending new creation events.

### Required indexed overrides for `parent="Ravager"`

| Index | Source | Event to override |
|-------|--------|-------------------|
| 0, 1 | GenericUnitMinimal | `UnitBirth.##unitName##` (two copies) |
| 2, 3 | GenericUnitMinimal | `UnitRevive.##unitName##` (two copies) |
| 5 | GenericUnitMinimal | `UnitConstruction.##unitName##` |
| 69 | GenericBurrowerStandard | `UnitBirth.##unitName##Burrowed` → `Send="Create"` |
| 70 | GenericBurrowerStandard | `UnitBirth.##unitName##Burrowed` → `Send="AnimBracketStart Burrow..."` |
| 74 | Ravager (hardcoded) | `AbilMorph.*.Cancel; MorphFrom Ravager; MorphTo RavagerBurrowed` |
| 75 | Ravager (hardcoded) | `AbilMorph.*.Finish; MorphTo Ravager; MorphFrom RavagerBurrowed` |
| 76 | Ravager (hardcoded) | `AbilMorph.*.Finish; MorphTo Ravager; MorphFrom RavagerCocoon` → `Send="Create"` |
| 77 | Ravager (hardcoded) | `AbilMorph.*.Finish; MorphTo Ravager; MorphFrom RavagerCocoon` → `Send="$Birth 0 0.000000"` |

Note: index 4 (second copy of UnitConstruction) is not unit-name-specific — leave it inherited.

### Full example

```xml
<CActorUnit id="MyRavagerVariant" parent="Ravager" unitName="MyRavagerVariant">
    <On index="0" Terms="UnitBirth.MyRavagerVariant"/>
    <On index="1" Terms="UnitBirth.MyRavagerVariant"/>
    <On index="2" Terms="UnitRevive.MyRavagerVariant"/>
    <On index="3" Terms="UnitRevive.MyRavagerVariant"/>
    <On index="5" Terms="UnitConstruction.MyRavagerVariant"/>
    <On index="69" Terms="UnitBirth.MyRavagerVariantBurrowed" Send="Create"/>
    <On index="70" Terms="UnitBirth.MyRavagerVariantBurrowed" Send="AnimBracketStart Burrow Burrow IGNORE Unburrow ClosingFull,OpeningPlayForever,Instant,DontResetOnUnhide"/>
    <On index="74" Terms="AbilMorph.*.Cancel; MorphFrom MyRavagerVariant; MorphTo MyRavagerVariantBurrowed" Send="AnimClear Burrow"/>
    <On index="75" Terms="AbilMorph.*.Finish; MorphTo MyRavagerVariant; MorphFrom MyRavagerVariantBurrowed" Send="AnimBracketStop Burrow"/>
    <On index="76" Terms="AbilMorph.*.Finish; MorphTo MyRavagerVariant; MorphFrom RavagerCocoon" Send="Create"/>
    <On index="77" Terms="AbilMorph.*.Finish; MorphTo MyRavagerVariant; MorphFrom RavagerCocoon" Send="$Birth 0 0.000000"/>
</CActorUnit>

<!-- Burrowed splat: unitName = the UNBURROWED unit's ID -->
<CActorSplat id="MyRavagerVariantBurrowedSplat" parent="BurrowedSplat" unitName="MyRavagerVariant">
    <Scale value="1.100000"/>
</CActorSplat>

<!-- Attack action: only effectLaunch needs overriding; effectImpact inherits from parent -->
<CActorAction id="MyRavagerVariantAttack" parent="RavagerAttack" effectLaunch="MyRavagerVariantWeaponLM"/>
```

### Red entries in SC2 Editor

The SC2 Editor marks **all indexed overrides in red** — this is cosmetic/informational only, not an error. It means "this entry overrides an inherited parent event." It cannot be avoided when using the index-override pattern.

The alternative is to use `parent="GenericUnitBase"` and redefine all events from scratch (as `RoachCorpser` does in the base game). That avoids red entries but requires duplicating every visual/sound event from the parent unit actor.

### Named missile and action parents retain native listeners

The same inheritance hazard applies to `CActorMissile` and `CActorAction`, but changing `unitName`, `effectAttack`, `effectLaunch`, or `effectImpact` on the leaf does not reliably retoken inherited event arrays. Runtime symptoms include a fallback sphere for an otherwise valid custom ammo unit, `Can only create one CActorAction per effect`, or `ActionImpactPhysics arrived before action commenced`.

For a project-owned missile, prefer `parent="GenericAttackMissile"`, set the custom `unitName`, and bind the active dependency `CModel` explicitly. Copy any native scale or lifetime animation fields that are part of the intended presentation. For a project-owned action, prefer `parent="GenericAttack"` (or the proven generic action base), set only the local effects, and copy the source action's attach query, assets, impact map, physics, acquisition arcs, and flags. Bind a custom `Beam` explicitly when cleanup events live on a custom beam actor; editing that beam without changing the action's inherited beam field has no runtime effect.

### Morph variants from named units

When a custom unit variant uses a copied `CAbilMorph` from a named unit, override the inherited morph target with `InfoArray index="0" Unit="CustomTarget"`. A bare `<InfoArray Unit="CustomTarget"/>` is easy to misread as a replacement, but for inherited morph arrays it can leave the source unit's morph target and source transition actors in play after an Editor round trip. On the unit, replace the inherited morph ability in the same `AbilArray` slot instead of appending a new ability. For example, if the parent unit has its unsiege morph as the third ability, use `<AbilArray index="2" Link="MyUnsiege"/>`; a bare `<AbilArray Link="MyUnsiege"/>` leaves both source and custom morph commands live.

For actors, provide a local `CActorUnit` for each custom morph endpoint and override its unit-name-specific birth/revive/construction events by index. If the source morph uses transition actors such as `*SiegeModeMorphModel`, also create local transition actors with `MorphTo`/`MorphFrom` terms rewritten to the custom unit IDs. This avoids alternating between fallback-sphere fixes that have no unit actor and duplicate-actor fixes that still let the source unit or source transition actor enter the custom unit scope.

---

## Do Not Index-Override Core Animation-Style Infrastructure Slots

`<On index="N">` **replaces** the parent event in that slot; it does not append. The Core animation-style parents keep infrastructure there: `ModelAnimationStyleContinuous` uses slot 0 for `ActorCreation -> AnimBracketStart BSD Birth Stand Death` and slot 1 for `ActorOrphan -> Destroy`; `ModelAnimationStyleOneShot` keeps slot 0 the same (with `ContentPlayOnce`) and uses slot 1 for `AnimBracketState.*.AfterClosing; AnimName BSD -> Destroy`.

A child that writes `<On index="0" Terms="Effect.MyPersistent.Start" Send="Create"/>` plus `<On index="1" Terms="Effect.MyPersistent.Stop" Send="AnimBracketStop BSD"/>` therefore deletes the bracket start and the orphan fallback: BSD never opens, `AnimBracketStop BSD` becomes a no-op, `AfterClosing -> Destroy` can never fire, and the model stays on the map forever (ISSUE-016, `ArchonShakurasVoidRiftModel`).

Write those terms **without** an index so they append after the inherited slots. Every shipped reference for this shape does exactly that: Psi Storm `HighTemplarVoidStormModelD`, SCORE-Ihanrii `BlackHoleBombI`, SCORE-Taldarim `HighTemplarVoidStormImpactD`/`SoundD`, SCORE-Golden `ArchonShieldModelG`.

Two related facts worth checking before adding an index:

- A named parent's own events are appended **after** the Core infrastructure slots, so a child's `index="0"` / `index="1"` hits infrastructure, not the parent's ability listeners. Read the parent actor and count slots instead of assuming the parent's first event is index 0.
- An index override removes only the slot it names. If a variant must not react to the parent's listeners (`Behavior.SomeParentBuff.On`, `Effect.SomeParentPersistent.Start`), those parent slots need explicit `removed="1"` rows; overriding slot 0/1 does not silence them.

Verify a suspected lingering-VFX actor by checking that its `AnimBracketStop BSD` has a live bracket to stop, and by confirming that the parent provides an orphan or `AfterClosing -> Destroy` path - the shipped `Effect.<persistent>.Stop` delivery at natural expiry is reliable, so a missing destroy is almost always a missing or overridden listener, not a missing event.

---

## Damage-Response Effects Must Anchor Their Own Location

A `CBehaviorBuff.DamageResponse Fatal="1"` effect tree starts in a damage context, where `Target` is the damage source (the attacker), not the behavior holder. `CEffectCreatePersistent` defaults to `<WhichLocation Value="TargetPoint"/>` (Core Effects.txt L34-35), so a death-triggered persistent that declares no location anchors on the killer instead of on the unit that died - the rift/field/explosion opens in the wrong place, and its `RevealRadius` reveals there too.

Anchor it explicitly with `<WhichLocation Value="CasterUnit"/>`, the shipped `SS_ScourgeDeathPersistent` shape (Liberty Campaign Effects.txt L852-861, started by `SS_ScourgeDeath` in Liberty Campaign Behaviors.txt L268-271). Children of that persistent inherit its location, so their own `ImpactLocation`/`WhichLocation` stays `TargetPoint` - that is why `SS_ScourgeDeathLaunchMissile` (Liberty Campaign Effects.txt L845-851) keeps `TargetPoint` inside a `CasterUnit` persistent.

A sibling entry in the same `CEffectSet` is **not** a child: it inherits no location and must be anchored itself (ISSUE-018 changed `ArchonShakurasVoidRiftBurstSearch`'s `ImpactLocation` to `CasterUnit` for exactly that reason). `CasterUnit` is legal for both `WhichLocation` and `ImpactLocation`.

---

## ZergGroundArmors / ZergMissileWeapons — All Levels Required

`ZergGroundArmorsLevel1`, `Level2`, `Level3` are separate upgrades that each fire once when that tier is researched. A unit only receives the full +3 armor at Level3 if EffectArrays exist on **all three** Level upgrades. Adding entries only to Level2 and Level3 caps the unit at +2.

When adding a new Zerg unit to ground armor upgrades, add `AffectedUnitArray` + `EffectArray` entries (LifeArmor and LifeArmorLevel, +1 each) to all three Level upgrades:

```xml
<!-- In ZergGroundArmorsLevel1, Level2, AND Level3 — same entries in all three -->
<AffectedUnitArray value="MyRavagerVariant"/>
<AffectedUnitArray value="MyRavagerVariantBurrowed"/>
<EffectArray Reference="Unit,MyRavagerVariant,LifeArmor" Value="1"/>
<EffectArray Reference="Unit,MyRavagerVariant,LifeArmorLevel" Value="1"/>
<EffectArray Reference="Unit,MyRavagerVariantBurrowed,LifeArmor" Value="1"/>
<EffectArray Reference="Unit,MyRavagerVariantBurrowed,LifeArmorLevel" Value="1"/>
```

For `ZergMissileWeapons`, if the variant's weapon impact set references the same damage effect as the base unit (e.g. `RavagerWeaponDamage`), only `AffectedUnitArray` entries are needed — no separate EffectArray — since the base game's damage scaling already applies through the shared effect.

There are similar upgrades for Terran and Protoss.

---

## Vanilla `parent=` Inheritance Risk

**Never use `parent="HotS*"` (or any vanilla upgrade ID) on a My `CUpgrade`.**

SC2 Data Editor `parent=` is **data-field inheritance only** — it does NOT mean "this upgrade depends on the parent." When you apply `HydraliskAncillaryCarapace` via `TechTreeUpgradeAddLevel`, the game does NOT mark `HotSHydraliskHealth` as complete. They are independent upgrade IDs.

The risk: vanilla HotS campaign maps have Galaxy triggers that directly call `TechTreeUpgradeAddLevel(player, "HotSHydraliskHealth")` based on the `ZCampaign` bank when a map loads. These triggers bypass the `CArmyUpgrade` override in `ArmyUpgradeData.xml`. If a player has a `ZCampaign` bank with that evolution flagged (e.g. from a prior vanilla HotS run), `HotSHydraliskHealth` fires independently of your mod — causing:

- **Double-apply of the stat bonus** (once from the vanilla trigger via `HotSHydraliskHealth`, once from your custom upgrade that inherited the same EffectArray)
- **Extra vanilla button appearing** on the command card (the slot gated by `HaveHotSHydraliskHealth` at Row=2 Column=1 becomes visible, conflicting with your custom button)

The fix is always to **write explicit EffectArray entries** and omit the `parent=`. This is a few extra lines of XML but eliminates the coupling entirely.

```xml
<!-- WRONG — inherits effects AND risks double-apply from vanilla map triggers -->
<CUpgrade id="HydraliskAncillaryCarapace" parent="HotSHydraliskHealth"/>

<!-- CORRECT — fully self-contained, no coupling to vanilla upgrade system -->
<CUpgrade id="HydraliskAncillaryCarapace">
    <Icon value="Assets\Textures\BTN-Upgrade-Zerg-AncillaryArmor.dds"/>
    <Race value="Zerg"/>
    <EditorCategories value="Race:Zerg,UpgradeType:Talents"/>
    <EffectArray Reference="Unit,Hydralisk,LifeMax" Value="20"/>
    <EffectArray Reference="Unit,Hydralisk,LifeStart" Value="20"/>
    <!-- ... all variants ... -->
    <AffectedUnitArray value="Hydralisk"/>
    <!-- ... -->
</CUpgrade>
```

**Important: `ArmyUpgradeData.xml` overrides do NOT protect against direct `TechTreeUpgradeAddLevel` calls.** Redirecting `CArmyUpgrade` to dummy upgrades only intercepts the army-panel upgrade path. Vanilla map Galaxy triggers that call `TechTreeUpgradeAddLevel` directly are unaffected.

---

## CEffectDamage Fields

`CEffectDamage` only accepts `Amount` (and damage type fields). `ImpactLocation`, `WhichUnit`, and `KillType` do NOT exist on it:

```xml
<CEffectDamage id="MyMyDoomDamage">
    <Amount value="5000"/>
</CEffectDamage>
```

Do not use `CEffectDamage` as `PeriodicEffect` for self-kill — see [galaxy-gotchas.md](../galaxy-gotchas.md).

---

## DamageDealtFraction Is Additive

`CBehaviorBuff.Modification.DamageDealtFraction` is an additive fraction applied to the unit's outgoing damage multiplier. Use positive values for bonus damage and negative values for reductions:

```xml
<!-- 40% less damage dealt; final multiplier is 1 + (-0.4) = 0.6 -->
<DamageDealtFraction index="Melee" value="-0.4"/>
<DamageDealtFraction index="Ranged" value="-0.4"/>
```

Blizzard examples use the same pattern: `DamageDealtMinimal` sets Melee/Ranged/Spell/Splash to `-0.9`, and campaign debuffs use `-0.25`, `-0.35`, or `-0.5` for damage reductions. A value like `0.6` is a +60% damage bonus, not 60% final damage.

---

## XML Node Structure & Common Schema Traps

StarCraft II GameData modification relies on cascading XML catalogs with parent inheritance (`parent="..."`). To ensure structural validity and avoid schema rejection by the engine:

### 1. Child Value Elements vs. Raw Attributes
Most catalog fields require child XML elements with a `value="..."` attribute rather than placing attributes directly on the root catalog element.
- **WRONG:** `<CUnit id="Marine" LifeMax="100" Speed="3.15"/>`
- **CORRECT:**
  ```xml
  <CUnit id="Marine" parent="MarineBase">
      <LifeMax value="100"/>
      <Speed value="3.15"/>
      <CostResource index="Minerals" value="75"/>
  </CUnit>
  ```

### 2. Card Layout 37 Format
Command card button slots use `CardLayout37` with `LayoutButtons` index arrays:
```xml
<CardLayout37>
    <LayoutButtons index="0" Ability="Stimpack" AbilityCmd="Execute" Row="2" Column="0"/>
</CardLayout37>
```

### 3. Ability & Behavior Array Indexing
Field arrays (such as `CmdButtonArray`, `InfoArray`, `CostResource`) require explicit index keys in array assignments.

### 4. Behavior Modification Nesting
Behavior attribute modifications under `CBehaviorBuff` must be nested inside `<Modification>`:
```xml
<CBehaviorBuff id="MyMyBuff">
    <Modification WeaponRange="1">
        <DamageDealtFraction index="Melee" value="0.2"/>
    </Modification>
</CBehaviorBuff>
```
Do not place modification sub-elements directly under the root `<CBehaviorBuff>` tag.

### 5. Actor Event Lists
In `<CActorUnit>`, `<CActorAction>`, etc., actor event triggers must use valid `<On Terms="..." Send="..."/>` syntax. Check existing active dependency actors before authoring new term expressions.

### 6. UI Layouts (`.SC2Layout`)
Interface frames in `Base.SC2Data/UI/Layout/*.SC2Layout` use `<Frame type="..." name="...">`, `<Anchor>`, `<StateGroup>`, and `<Animation>` tags with valid template namespaces.

### Schema Validation Reference
Formal XSD schemas for GameData and Layout files are bundled in `tools/schemas/sc2-xsd/` (derived from `sc2-arcade-watcher/sc2-xsd` and `SC2Mapster/sc2layout-schema`).
- Pre-flight validation (`tools/validate-mod.py` invoked by `tools/test-suite.py`) automatically validates all GameData XML files against `Catalog.xsd` using `lxml`.
- VS Code workspace settings (`.vscode/settings.json`) bind `Base.SC2Data/GameData/*.xml` to `Catalog.xsd` for real-time editor diagnostics.
- See [external-sc2-resources.md](../../reference/external-sc2-resources.md) for external repository links.
