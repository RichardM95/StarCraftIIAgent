# Confirmed XML Patterns

Confirmed working Data Editor XML patterns. Always grep `DataEditorXML/` files before writing new XML — field names are case-sensitive.

> **Note:** Code samples below use generic `My*` IDs (e.g. `MyUpgrade`, `MyBehavior`, `MyAbility`). Replace with your mod's prefix from `AGENTS.md`.

See [wiki/reference/data-editor-xml.md](../../reference/data-editor-xml.md) for the DataEditorXML file index.

**Localization rule:** when adding or overriding XML catalog entries, add matching `ObjectStrings.txt` editor `Name` and `EditorPrefix` keys in the same change. See [localization.md](../localization.md) for the required key formats and validation expectation.

---

## Editor Round-Trip Audit

A unit or faction extraction can be mechanically incomplete even when the primary unit, ability, effect, behavior, and actor rows parse. See the [Editor round-trip checklist](editor-roundtrip-and-actors.md#editor-round-trip-checklist).

For any extracted or copied unit set, treat these catalogs as part of the same required implementation surface:

- Gameplay: `UnitData.xml`, `AbilData.xml`, `WeaponData.xml`, `EffectData.xml`, `BehaviorData.xml`, `RequirementData.xml`, `RequirementNodeData.xml`, `ValidatorData.xml`, `TurretData.xml`, and any mover/footprint/upgrades that are referenced.
- Presentation: `ActorData.xml`, `ModelData.xml`, `SoundData.xml`, `ButtonData.xml`, icons/wireframes, and localized names/tooltips.
- Editor readability: `ObjectStrings.txt` names/prefixes/suffixes for every new catalog object, including actors, models, sounds, turrets, validators, and helper weapons.

Do an ID-level audit before handoff: every referenced custom or inactive-source ID must either exist in the active dependency chain or be copied into the project. Do not assume the SC2 Editor will tolerate missing model, sound, turret, validator, weapon, or button-face records just because the XML parser accepts the file.

When the Editor saves an object after changing `EditorCategories`, it may migrate or recreate rows in the standard catalog file for that object type, such as abilities in `AbilData.xml` or upgrades in `UpgradeData.xml`. Treat that as a canonicalization signal: keep the standard-catalog row, preserve any useful `Name`/`Tooltip` anchors from the old side row, and remove the duplicate old row from broad `GameData.xml`. Do not keep both rows with the same `(catalog type, id)`.

The Editor can also normalize an exact child copy of an inherited field such as `BuildModel`, or remove an explicit `CActorAction.Beam` value that duplicates the inherited token-derived value. Keep the normalized inheritance when the effective parent value is correct. When runtime presentation needs an unambiguous leaf binding, supply the token-matched actor (`<custom action id>Beam`) parented to the canonical beam actor. Audit localization after every save: an Editor move into `ObjectStrings.txt` does not replace a `GameStrings.txt` key still referenced by a runtime `Name` field.

After an Editor rewrite, keep the promoted typed-catalog row, remove any same-ID `GameData.xml` row, preserve non-default fields such as `CAbilWarpTrain` `IgnoreRampTest=1`, and rerun duplicate-provider and command-card `AbilCmd` audits.

---

## Custom Unit Creation Checklist

Use this when adding or auditing independent custom units:

- **Unit:** create an mod-owned `CUnit` instead of editing the vanilla unit. Set race/object type/family for organization, but treat gameplay fields separately: abilities, command cards, behaviors, weapons, mover/plane, attributes, flags, life/energy/shields, cargo, sight, score, and aliases.
- **Production cost:** do not rely on the unit editor's generic `Cost` field for train/build UI. Native production cost and time are governed by the producing `CAbilTrain`/`CAbilBuild` InfoArray entry plus the produced unit's `CostResource`/`Food`; ensure the produced unit allows resource display and the button does not hide resources, supply, or time. See "Command-Card Cost Display for Train/Build Buttons" below.
- **Ability/command card:** add the ability to the producer or unit first, then add command-card buttons that point to the exact ability command (`Type="AbilCmd"` + matching `AbilCmd`). A visible name/tooltip alone only proves the `Face` is valid, not that the cost/time command link is valid.
- **Weapons/effects:** clone or create the weapon's effect chain so the custom unit is independent. Confirm `CWeaponLegacy.Effect`, `DisplayEffect`, target filters, range, period, and icon. For missile/beam attacks, verify launch effect, impact effect, ammo/missile unit, movers, and action actors.
- **Actors:** every custom unit needs a unit actor linked to that unit. Prefer explicit event overrides for parented actors; actor tokens and unit-name macros can inherit the parent unit unexpectedly. Weapon visuals also need action/missile/beam actors linked to the custom launch/impact effects.
- **Models/sounds/turrets/validators:** actor and weapon chains often depend on `CModel`, `CSound`, `CTurret`, helper `CWeapon`, and `CValidator` rows outside the obvious unit/effect files. Trace and copy only the records actually referenced by the final actor/effect/weapon set.
- **Upgrades:** add the custom unit to relevant `AffectedUnitArray` entries and add explicit `EffectArray` entries for its armor/damage icons, levels, and stat changes. Repeat entries across all weapon/armor upgrade tiers.
- **Multi-form/burrowed units:** be extra cautious with copied multi-form units. Create independent units/actors for each form and wire morph, burrowed, splat, alias, and selection events explicitly instead of assuming the parent chain will retarget cleanly.
- **Localization/editor names:** add `GameStrings.txt` for player-facing unit/button/tooltips and `ObjectStrings.txt` for editor-facing names/prefixes for every new catalog ID. Add real XML `Name`, `Tooltip`, or `Description` anchors where needed so Editor saves do not prune important text.
- **Testing:** place or train the unit in-game, then test production UI, production completion, movement/pathing, command-card abilities, weapons against every intended target class, actors/VFX, upgrades at each tier, and campaign tech-tree unlocks.

Known editor caution: duplicated/copied data can leave parent links, tokens, and actor events pointing at the original object. When debugging a "data works but UI/VFX does not" issue, inspect the whole chain rather than only the unit row.

---

## Upgrade Stat Modification (simple stats — HP, speed, damage, armor, cost)

```xml
<CUpgrade id="MyUpgrade">
    <Level index="0">
        <EffectArray index="0">
            <Effect value="MyEffect"/>
        </EffectArray>
    </Level>
</CUpgrade>

<CEffectModifyUnit id="MyEffect">
    <Modification MaxVitalArray="Life" Value="30"/>  <!-- +30 HP -->
</CEffectModifyUnit>
```

---

## Behavior via BehaviorArray (passive, always on unit — gated by Requirements)

```xml
<!-- BehaviorData.xml -->
<CBehaviorBuff id="MyBehavior">
    <InfoFlags index="Hidden" value="1"/>
    <Requirements value="HaveMyUpgrade"/>  <!-- inert until upgrade applied -->
    <Period value="5"/>
    <PeriodicEffect value="MyPeriodicEffect"/>
</CBehaviorBuff>

<!-- UnitData.xml — use BehaviorArray, NOT DefaultBehaviorArray (that field does not exist) -->
<CUnit id="Mutalisk">
    <BehaviorArray Link="MyBehavior"/>
</CUnit>
```

---

## Ability Granting via XML

```xml
<!-- AbilData.xml: channeled targeted ability -->
<CAbilEffectTarget id="MyAbility">
    <PrepEffect value="MyAbilityChannelAB"/>
    <Effect index="0" value="MyAbilityEffect"/>
    <Range value="500"/>
    <Cost><Cooldown TimeUse="30"/></Cost>
    <CastOutroTime value="2"/>
    <UninterruptibleArray index="Channel" value="1"/>
    <CmdButtonArray index="Execute" DefaultButtonFace="Hyperjump" Requirements="HaveMyAbility"/>
    <CmdButtonArray index="Cancel" DefaultButtonFace="Cancel"/>
</CAbilEffectTarget>

<!-- UnitData.xml -->
<CUnit id="Mutalisk">
    <AbilArray Link="MyAbility"/>
</CUnit>
```

---

## Smart Command Routing

For ability classes that support it, `<Flags index="Smart" value="1"/>` makes the ability participate in the engine's generic Smart Command selection, normally invoked by right-click. `SmartPriority` ranks the ability against movement and other smart-capable commands, while `SmartValidatorArray` restricts the targets or situations in which it qualifies.

A copied or inherited targeted ability can therefore intercept right-click when ordinary attack or movement was intended. If that is not part of the design, clear **Stats: Flags -> Smart Command** in the Data Editor and verify the effective inherited value; command-card visibility does not control Smart Command routing.

Source and scope: the local SC2 catalog schema documents `SmartPriority` as the selector for smart commands, and exported Liberty/NovaStory ability rows pair the `Smart` flag with `SmartValidatorArray`. This is a generic ability rule; the community-reported Nova Break Neck case was not reproduced locally.

---

## Modification Field Syntax

```xml
<Modification UnifiedMoveSpeedFactor="0.3"/>  <!-- +30% movement speed additive -->
<Modification AttackSpeedMultiplier="1.5"/>   <!-- 1.5× = +50% attack speed -->
<!-- Both are TOP-LEVEL attributes on <Modification>, not child elements -->

<!-- Evasion (% chance to take zero damage) -->
<DamageResponse ModifyFraction="-1">
    <Chance value="0.3"/>  <!-- 30% evasion -->
</DamageResponse>
```

---

## Teleport Effect

```xml
<CEffectTeleport id="MyTeleport">
    <WhichUnit Value="Caster"/>
    <TargetLocation Value="TargetPoint"/>
    <TeleportFlags index="TestFog" value="0"/>
    <PlacementRange value="15"/>
</CEffectTeleport>
```

---

## Changing Weapon TargetFilters via Upgrade

`CWeaponLegacy.TargetFilters` is a **single field**, not an array — do not use `index` attribute. Use `Operation="Set"` directly:

```xml
<EffectArray Operation="Set" Reference="Weapon,ViperAir,TargetFilters" Value="Visible;Missile,Stasis,Dead,Hidden,Invulnerable"/>
```

---
