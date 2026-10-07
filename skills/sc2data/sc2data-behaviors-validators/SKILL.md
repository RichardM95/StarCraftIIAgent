---
name: sc2data-behaviors-validators
description: SC2 Data Editor — Behaviors (buffs, debuffs, auras, timers) and Validators (conditional tests) in XML. Use when creating or modifying CBehavior* (buff, attribute modifier, unit tracker, reveal) or CValidator* (unit type, unit order, comparison, combine) entries. Also covers behavior stacking, duration, Vitals modification, and how validators gate effects, abilities, and behaviors. Always consult the catalogsData.xsd schema for exact fields and structure — do not assume unsupported fields exist. Do not use for applying a behavior via an effect (use sc2data-effects-weapons) or actor visuals tied to a behavior (use sc2data-actors-visuals).
---

## Loading Boundary

- **This sub-skill owns:** CBehavior* (buffs, debuffs, auras, timers) and CValidator* (unit type, order, comparison, combine) XML schema, behavior stacking, duration, and Vitals modification
- **Parent root skill (`sc2-catalog-xml`) owns:** project conventions, schema/syntax rules, source-of-truth, naming prefixes
- **Sibling sub-skills own:** `sc2data-effects-weapons` (apply behavior via effect), `sc2data-actors-visuals` (actor visuals tied to behavior), `sc2data-units-abilities` (unit/ability containers)

# SC2 Data Editor – Behaviors & Validators

## Prerequisite

Load [`sc2-catalog-xml`](../../sc2-catalog-xml/SKILL.md) first for project-wide Catalog XML schema rules (child value elements not raw attributes, ASCII-only, no `AbilAutoCmd`, no `CBehaviorBuff.InitEffect`, no comment-only catalogs), parent inheritance pitfalls, effective-value evidence workflow, localization anchors, and Editor round-trip safety. This sub-skill owns deep schema reference only; project conventions live in the router skill.

**Behaviors** are persistent passive effects on a unit — buffs, debuffs, auras, timed life, stat modifications. **Validators** are boolean tests used anywhere in data to gate whether something happens — in effects, abilities, behaviors, and actors.

## Key References

| Resource | URL |
|---|---|
| Validators guide | https://s2editor-guides.readthedocs.io/New_Tutorials/04_Data_Editor/071_Validators/ |
| Data Editor Introduction | https://s2editor-guides.readthedocs.io/New_Tutorials/04_Data_Editor/058_Data_Editor_Introduction/ |
| SC2Mapster wiki | https://sc2mapster.wiki.gg/ |
| Behaviors (wiki) | https://sc2mapster.wiki.gg/wiki/Data/Behaviors |
| Validators (wiki) | https://sc2mapster.wiki.gg/wiki/Data/Validators |
| ShadowDragon Base.SC2Data (real GameData XML reference) | https://github.com/ShadowDragonSC2/Base.SC2Data/tree/main/GameData |
| **Source of Truth: CatalogsData XSD Schema** | https://github.com/ShadowDragonSC2/Base.SC2Data/raw/refs/heads/main/.vscode/schemas/catalogsData.xsd — Always consult this for exact fields, attributes, and structure of behaviors and validators. Do not assume fields exist; verify against the schema. |
| **Recommended VS Code Extension** | Red Hat XML (redhat.vscode-xml) — Install this extension for XML validation, auto-completion, and error detection using the catalogsData.xsd schema. Configure it in .vscode/settings.json for automatic validation.

## XML Schema Error Check and Fix Workflow

When editing SC2 data XML, always run this loop until diagnostics are clean:

1. Validate with Red Hat XML diagnostics (Problems panel).
2. For each error, identify whether it is an invalid element, invalid attribute, invalid enum value, or invalid field path/array index.
3. Verify the exact allowed structure in `catalogsData.xsd` before changing anything.
4. Fix the XML by aligning to schema-supported fields only; remove guessed or unsupported fields.
5. Re-validate and repeat until no schema errors remain.

If a user asks to fix XML errors, perform this end-to-end workflow rather than only describing it.

---

> **File placement:** When creating behaviors for a new unit or ability, put them in the unit's own self-contained XML file (`GameData/Faction/UnitName/UnitName.xml`), not in a monolithic `BehaviorData.xml`. Register the file via `<Catalog path="..."/>` in `GameData.xml`. See the sc2data-units-abilities skill for the full file template.

## Behaviors (`BehaviorData.xml`)

File: `Base.SC2Data/GameData/BehaviorData.xml`

Behaviors are applied to units via `CEffectApplyBehavior` and removed via `CEffectRemoveBehavior` or expiry.

### Behavior Types

| XML Type | Purpose |
|---|---|
| `CBehaviorBuff` | General-purpose buff/debuff; most common type |
| `CBehaviorAttributeModifier` | Modify unit stats (Speed, Armor, HP, etc.) |
| `CBehaviorUnitTracker` | Track units and fire effects at count thresholds |
| `CBehaviorReveal` | Reveal unit (remove stealth or reveal allies to enemies) |
| `CBehaviorAbilityModifier` | Modify ability parameters dynamically |
| `CBehaviorResource` | Resource regeneration (minerals, vespene) |

---

### CBehaviorBuff — General Buff/Debuff

```xml
<CBehaviorBuff id="MyStunBehavior">
    <EditorCategories value="AbilityorEffectType:Targeted"/>
    <Duration value="3"/>                          <!-- seconds; 0 = permanent until removed -->
    <DurationBonusArray index="HeroKills" value="1"/>  <!-- duration bonus per hero kill (if applicable) -->
    <MaxCount value="1"/>                          <!-- max stacking instances on one unit -->

    <!-- While active: disable unit's movement and attack -->
    <DisableArray index="Move" value="1"/>
    <DisableArray index="Attack" value="1"/>

    <!-- Validators to keep behavior active; false = disable while condition fails -->
    <ValidatorArray type="Disable" index="0" value="IsTargetAlive"/>

    <!-- Validators to permanently remove behavior -->
    <ValidatorArray type="Remove" index="0" value="IsTargetAboveHalfHP"/>

    <!-- Periodic effect while behavior is active -->
    <PeriodicEffectArray index="0" value="MyDoTEffect" Period="1"/>

    <!-- Effects fired on apply/expire -->
    <OnUnitBirth value="MyBuffApplyEffect"/>
    <OnRemove value="MyBuffExpireEffect"/>
</CBehaviorBuff>
```

### Key CBehaviorBuff fields

| Field | Purpose |
|---|---|
| `Duration` | How long the behavior lasts (0 = permanent) |
| `MaxCount` | Maximum stacking instances on one unit |
| `DisableArray` | Disable a unit command while active (Move, Attack, Hold, etc.) |
| `PeriodicEffectArray` | Effect fired every N seconds while active |
| `OnUnitBirth` | Effect fired when behavior is first applied |
| `OnRemove` | Effect fired when behavior expires/is removed |
| `InitVitalArray` | Modify a vital when applied (e.g. heal on apply) |
| `VitalMaxArray` | Modify max vital while active |

---

### CBehaviorAttributeModifier — Stat Modifier

```xml
<CBehaviorAttributeModifier id="SpeedBoost">
    <Duration value="10"/>
    <Modification>
        <SpeedMultiplier value="1.5"/>     <!-- 50% speed increase -->
    </Modification>
</CBehaviorAttributeModifier>

<CBehaviorAttributeModifier id="ArmorReduction">
    <Duration value="0"/>                  <!-- permanent until removed -->
    <Modification>
        <LifeArmorBonus value="-2"/>       <!-- reduce armor by 2 -->
    </Modification>
</CBehaviorAttributeModifier>
```

### Common Modification fields

| Field | Meaning |
|---|---|
| `SpeedMultiplier` | Multiply movement speed (1.0 = no change) |
| `LifeArmorBonus` | Add/subtract armor |
| `ShieldArmorBonus` | Add/subtract shield armor |
| `KillBountyModifier` | Multiply kill bounty |
| `DamageDealtFraction` | Multiply outgoing damage |
| `DamageTakenFraction` | Multiply incoming damage |
| `LifeRegenRate` | HP per second regeneration |

---

### Behavior Stacking

```xml
<CBehaviorBuff id="PoisonStack">
    <MaxCount value="10"/>          <!-- allow up to 10 stacks -->
    <Stack value="Duration"/>       <!-- stacking resets duration each application -->
</CBehaviorBuff>
```

Stack modes: `Duration` (reset timer), `None` (add count only), `Any` (max of duration and count).

---

### Aura Pattern (Behavior + Search Effect + Apply)

Auras are implemented as a looping effect on a behavior:

```xml
<!-- 1. The aura behavior on the source unit -->
<CBehaviorBuff id="HealingAuraBehavior">
    <Duration value="0"/>
    <PeriodicEffectArray index="0" value="HealingAuraSearch" Period="1"/>
</CBehaviorBuff>

<!-- 2. A search effect finds nearby allies -->
<CEffectSearch id="HealingAuraSearch">
    <AreaArray index="0" Radius="3" Effect="HealingAuraApply"
               TargetFilters="Alive;Self,Enemy,Neutral,Dead"/>
</CEffectSearch>

<!-- 3. Apply a heal behavior to each found unit -->
<CEffectApplyBehavior id="HealingAuraApply">
    <Behavior value="HealingAuraHeal"/>
</CEffectApplyBehavior>
```

---

## Validators (`ValidatorData.xml`)

File: `Base.SC2Data/GameData/ValidatorData.xml`

Validators return **true or false**. They are used in:
- **Effects** — false = effect not applied
- **Behaviors** `Disable` — false = behavior disabled (dormant) while condition fails
- **Behaviors** `Remove` — false = behavior permanently removed
- **Abilities** — false = ability unavailable / grayed out
- **Actor** `Terms` — via `ValidateUnit UpgradeId` term

### Naming Convention

Named as sentence fragments describing the **true condition**:

```
"CasterNotBurrowed"       — true when caster is not burrowed
"TargetIsAlive"           — true when target is alive
"IsPhoenix"               — true when unit type is Phoenix
"PlayerHasBarracks"       — true when player owns at least one Barracks
```

---

### Validator Types

| XML Type | Tests |
|---|---|
| `CValidatorUnitType` | Is unit a specific type? |
| `CValidatorUnitOrder` | Is unit performing a specific order/ability? |
| `CValidatorUnitComparison` | Compare a unit vital/value to a threshold |
| `CValidatorPlayerComparison` | Compare a player resource to a threshold |
| `CValidatorCombine` | AND / OR / NOT of other validators |
| `CValidatorPlayerRequirement` | Does player meet a tech requirement? |
| `CValidatorLocationPathable` | Is a location pathable? |
| `CValidatorConditionCustom` | Galaxy-script custom condition (advanced) |

---

### CValidatorUnitType — check unit type

```xml
<CValidatorUnitType id="IsZergling">
    <UnitType value="Zergling"/>
    <!-- Negate field not set = true when IS Zergling -->
</CValidatorUnitType>

<CValidatorUnitType id="IsNotHero">
    <UnitType value="HeroBase"/>
    <Negate value="1"/>   <!-- true when unit is NOT a hero -->
</CValidatorUnitType>
```

### CValidatorUnitComparison — compare unit stat

```xml
<CValidatorUnitComparison id="TargetBelowHalfHP">
    <WhichUnit value="Target"/>
    <Value index="0" value="Life"/>
    <Value index="1" value="LifeMax"/>
    <Fraction value="0.5"/>         <!-- 50% threshold -->
    <Compare value="LT"/>           <!-- Less Than: life < 50% max -->
</CValidatorUnitComparison>
```

Compare operators: `LT` (less than), `LE` (≤), `EQ` (equal), `GE` (≥), `GT` (greater than), `NE` (not equal).

### CValidatorPlayerComparison — check player resource

```xml
<CValidatorPlayerComparison id="PlayerHasEnoughMinerals">
    <Value index="0" value="Minerals"/>
    <Compare value="GE"/>
    <Threshold value="100"/>
</CValidatorPlayerComparison>
```

### CValidatorCombine — boolean logic

```xml
<!-- AND: both must be true -->
<CValidatorCombine id="TargetAliveAndNotShielded">
    <Type value="And"/>
    <ValidatorArray index="0" value="TargetIsAlive"/>
    <ValidatorArray index="1" value="IsNotShielded"/>
</CValidatorCombine>

<!-- OR: at least one must be true -->
<CValidatorCombine id="IsGroundOrStructure">
    <Type value="Or"/>
    <ValidatorArray index="0" value="IsGround"/>
    <ValidatorArray index="1" value="IsStructure"/>
</CValidatorCombine>

<!-- NOT: negate a validator -->
<CValidatorCombine id="NotCloaked">
    <Type value="Not"/>
    <ValidatorArray index="0" value="IsCloaked"/>
</CValidatorCombine>
```

### CValidatorUnitOrder — check if unit is performing an order

```xml
<CValidatorUnitOrder id="TargetIsAttacking">
    <WhichUnit value="Target"/>
    <Abil value="Attack"/>
</CValidatorUnitOrder>
```

---

## Validators in Context

### In effects (gates application):

```xml
<CEffectDamage id="FinisherDamage">
    <Amount value="200"/>
    <ValidatorArray index="0" value="TargetBelowHalfHP"/>  <!-- only deal if below 50% HP -->
</CEffectDamage>
```

### In behaviors — Disable (temporarily dormant):

While the validator returns false, the behavior is suppressed but stays on the unit:

```xml
<CBehaviorBuff id="AuraOnlyWhileMoving">
    <ValidatorArray type="Disable" index="0" value="TargetIsMoving"/>
</CBehaviorBuff>
```

### In behaviors — Remove (permanently stripped):

When the validator returns false, the behavior is removed entirely:

```xml
<CBehaviorBuff id="ExpiresWhenFullHP">
    <ValidatorArray type="Remove" index="0" value="TargetBelowHalfHP"/>
</CBehaviorBuff>
```

### In abilities (gates availability):

Ability is grayed out / uncastable when validator returns false:

```xml
<CAbilEffectTarget id="MyAbility">
    <ValidatorArray index="0" value="NotBurrowed"/>
</CAbilEffectTarget>
```

### In actor Terms:

```xml
<On Terms="ActorCreation; ValidateUnit MyUpgrade" Send="AnimGroupApply Superior"/>
```

---

## Best Practices

- Name validators as true-condition fragments: prefer `"TargetIsAlive"` over `"NotDead"`.
- Use `CValidatorCombine` with `type="And"` rather than stacking multiple `ValidatorArray` entries if you need to reuse the combination elsewhere.
- `Disable` validators keep the behavior instance alive (useful for toggleable auras). `Remove` permanently strips — use when the behavior should be gone forever if the condition fails.
- Set `MaxCount value="1"` on most buffs to prevent unintended stacking.
- For auras: put the `PeriodicEffectArray` on the source unit's behavior, and use a `CEffectSearch` to reach nearby targets — never apply directly to all units from the behavior.
- Keep validators simple and composable — build complex logic from `CValidatorCombine` of simple validators.
