---
name: sc2-catalog-xml
description: StarCraft II GameData XML authoring for the AeonOfIhanrii campaign. Use when creating or modifying units, abilities, actors, behaviors, effects, weapons, upgrades, requirements, validators, or footprints. Covers schema rules, parent inheritance, effective-value evidence, localization, and editor round-trip safety.
---

# SC2 Catalog XML Authoring

## When to Use

Load this skill when writing or editing GameData XML in `*.SC2Mod/Base.SC2Data/GameData/*.xml` — units, abilities, actors, behaviors, effects, weapons, upgrades, requirements, validators, footprints, or any catalog object.

This skill is the **Catalog XML router**. It owns project-wide schema rules, parent inheritance, effective-value evidence, localization anchors, and editor round-trip safety. For deep XML work on a specific catalog family, route to the matching `sc2data-*` sub-skill under `skills/sc2data/`.

## Catalog Sub-Skill Router

For deep XML authoring on a specific catalog family, load the matching `sc2data-*` sub-skill under `skills/sc2data/`. This skill retains the project-wide **schema rules** and **effective-value workflow** that all sub-skills obey.

| Task | Sub-skill | Path |
|---|---|---|
| `CUnit` / `CAbil*` / `CMover` / `CTurret` XML | `sc2data-units-abilities` | `skills/sc2data/sc2data-units-abilities/SKILL.md` |
| `CBehavior*` / `CValidator*` XML | `sc2data-behaviors-validators` | `skills/sc2data/sc2data-behaviors-validators/SKILL.md` |
| `CEffect*` / `CWeapon` / `CUpgrade` / damage chain XML | `sc2data-effects-weapons` | `skills/sc2data/sc2data-effects-weapons/SKILL.md` |
| `CActor*` XML (Unit/Action/Model/Beam/Sound) | `sc2data-actors-visuals` | `skills/sc2data/sc2data-actors-visuals/SKILL.md` |
| `.BlizWiz` XML files, wizard templates | `sc2data-wizards` | `skills/sc2data/sc2data-wizards/SKILL.md` |
| Unit catalog reference (editor IDs, races, 18 co-op commanders) | `sc2data-units-reference` | `skills/sc2data/sc2data-units-reference/SKILL.md` |

> Sub-skills complement the existing top-level skills: `sc2-actor-system` (actor events/messages/extraction), `sc2-localization` (anchor strings), `sc2-map-triggers` (trigger XML wiring). When a sub-skill topic overlaps with a top-level skill, the top-level skill owns project conventions and the sub-skill owns schema reference.

## Pre-Edit Workflow (mandatory)

1. **Query first:** Run `python tools/sc2-catalog-query.py` for the target ID, unit, or family. Identify the current project and active-dependency providers. Do NOT guess field names or IDs — they are case-sensitive.
2. **Inspect one source:** Open the relevant current XML fragment. If field shape or a proven pattern is still needed, search one identified `DataEditorXML/*.txt` dump. For a component-level official/partner precedent, run `python tools/sc2-reference-query.py find <term> --area gamedata --family <Family> --component <name> --limit 20`. Reuse findings instead of repeating broad searches. Snapshot presence does not prove an active dependency.
3. **Read patterns:** Consult the relevant section of `wiki/implementation/xml-patterns.md` and `wiki/implementation/xml-patterns/catalog-rules.md`.
4. **Effective-value evidence:** Before editing a statistic, prove the effective value — record local unit, parent, inherited value at the exact field/index, and intended override. A missing child field may still be correct if the parent supplies the value.
5. **New rows go in typed catalogs:** `AbilData.xml`, `UnitData.xml`, `ButtonData.xml`, etc. — not in `GameData.xml`. Avoid duplicate `(catalog type, id)` entries across files.

## XML Schema Fundamentals

### Child Value Elements (not raw attributes)
Most catalog fields require child elements with `value="..."`:
```xml
<!-- WRONG -->
<CUnit id="Marine" LifeMax="100" Speed="3.15"/>

<!-- CORRECT -->
<CUnit id="Marine" parent="MarineBase">
    <LifeMax value="100"/>
    <Speed value="3.15"/>
    <CostResource index="Minerals" value="75"/>
</CUnit>
```

### Behavior Modification Nesting
```xml
<CBehaviorBuff id="MyBuff">
    <Modification WeaponRange="1">
        <DamageDealtFraction index="Melee" value="0.2"/>
    </Modification>
</CBehaviorBuff>
```

### Command Card Layout
```xml
<CardLayout37>
    <LayoutButtons index="0" Ability="Stimpack" AbilityCmd="Execute" Row="2" Column="0"/>
</CardLayout37>
```

### Array Indexing
`CmdButtonArray`, `InfoArray`, `CostResource`, `AffectedUnitArray`, `EffectArray` all require explicit `index=` or `value=` keys.

## Hard Rules

- **ASCII-only XML, no `AbilAutoCmd`, no `CBehaviorBuff.InitEffect`, no comment-only catalogs** — see `sc2-project-entry` Hard Rules #5-6 for the canonical list. (`InitialEffect` is a different field — do not confuse them.)
- **Check for duplicates** before adding a validator/entity that may already exist in the dependency chain.

## Inheritance & Parent Pitfalls

### `parent=` is data-field inheritance only
`parent="..."` does NOT create dependency relationships. For upgrades, never use `parent="HotS*"` on a custom `CUpgrade` — vanilla map triggers call `TechTreeUpgradeAddLevel` directly, causing double-apply. Write explicit `EffectArray` entries instead.

### Actor variant from named unit actor
When `parent="SomeUnitActor"`, the `##unitName##` macro resolves to the nearest ancestor defining `unitName`, NOT the leaf. Override every unit-name-specific event by index in the child actor. Red entries in the Editor are cosmetic (they indicate overrides).

### Morph variants
When using a copied `CAbilMorph`, override inherited morph target with `<InfoArray index="0" Unit="CustomTarget"/>`. Replace the inherited ability in the same `AbilArray` slot (use `index=`), don't append.

## Validators

- `CValidatorCombine` defaults to `Type="Or"`. Omit explicit `<Type value="Or"/>` (Editor canonicalizes it away). Use explicit `<Type value="And"/>` for AND, and `<Negate value="1"/>` to invert instead of `Type="Not"`.
- Pre-existing validator from Void.SC2Mod: `SourceIsNotStationary` (unit movement speed > 0) — do NOT redefine.

## Effects & Damage

- `CEffectDamage` only accepts `Amount` (and damage type fields). `ImpactLocation`, `WhichUnit`, `KillType` do NOT exist.
- `CBehaviorBuff.Modification.DamageDealtFraction` is **additive**: positive = bonus damage, negative = reduction. `0.6` means +60% (final multiplier 1.6), not 60% final.

## Zerg Upgrades

`ZergGroundArmorsLevel1/2/3` are separate upgrades that each fire once. A unit gets full +3 only if `EffectArray` entries exist on **all three** levels. Add `AffectedUnitArray` + `EffectArray` (LifeArmor and LifeArmorLevel, +1 each) to all three.

## Footprints

Consult `DataEditorXML/* Footprints.txt` before changing `CUnit.Footprint`. Footprints carry `Check`, `Place`, `Pathing` layers + `Shape`. For creep-friendly buildings, preserve size/shape/layers and only clear the creep blocker (`Negative[Creep]`).

## Localization Anchors

For player-visible text, add explicit XML anchors:
```xml
<CUnit id="MyUnit">
    <Description value="Unit/Tooltip/MyUnit"/>
</CUnit>
```

Then in `GameStrings.txt`:
```text
Unit/Tooltip/MyUnit=Player-facing description.
```
For new catalog objects readable in the Data Editor, update `ObjectStrings.txt` with `Type/EditorPrefix/ID` and `Type/Name/ID`.

After Editor save, run: `python tools/audit-gamestrings-anchors.py --fill`

## EditorCategories

Do not copy `EditorCategories` from inactive exports. Grep active `DataEditorXML/` for valid values. Collapse unsupported faction families (`FactionMecha`, `FactionPurifier`, etc.) to `ObjectFamily:Campaign` while preserving `ObjectType`.

## Post-Edit Validation

1. `python tools/validate-mod.py` — XSD schema + Galaxy syntax
2. `python tools/test-suite.py` — full pre-flight suite
3. Editor handoff: open mod in SC2 Editor, review XML warnings, save as Components
4. Run `python tools/audit-gamestrings-anchors.py --fill` after save

## Reference

- `wiki/implementation/xml-patterns.md` — main XML patterns
- `wiki/implementation/xml-patterns/catalog-rules.md` — deep catalog rules
- `wiki/implementation/xml-patterns/core.md` — core patterns
- `wiki/implementation/xml-patterns/production.md` — production chains
- `wiki/implementation/xml-patterns/editor-roundtrip-and-actors.md` — actor round-trip
- `wiki/reference/actors.md` — actor architecture
- `tools/schemas/sc2-xsd/Catalog.xsd` — formal schema

## Chinese Task Knowledge (Merged)

Distilled from `references/data-and-production.md` and `references/source-caveats.md`. Chinese narrative compressed to operational bullets; duplicates with sections above omitted.

### Production & Command Card Workflow
- Trace `Unit → Ability / Weapon → Effect → Behavior / Validator / Requirement`, then bring producer, button, Actor, Model, Sound, Mover, Turret, and localization into the same change.
- Verify, in order: producer `AbilArray`, the producing ability's `InfoArray`, target `Unit`, button `Face`, `Type="AbilCmd"` with exact `AbilCmd`, actual card layout & inherited slot, then `Show`/`Use` Requirements.
- Same-coordinate faction buttons rely on mutually exclusive requirements — check both the button and the command-card entry so only the intended one is active for the current player. Preserve inherited `Attack`/`Stop`/`Rally`/morph slots.
- Worker sub-menus must match both `CardLayouts index` and `CardId` — appending a same-named sub-card alone is insufficient.
- Units with weapons still need a valid `Attack` ability; movement/warp also require `Move`/`Warpable`.
- When copying abilities, audit `Smart`, `SmartPriority`, `SmartValidatorArray` to avoid the right-click being intercepted.
- Auto-cast filters handle generic target attributes; use validators for precise unit sets / quantity conditions. For scripted side effects, verify the actual caster and target events.

### Cost & Display Caveats
- Prefer native cost display; do not hardcode upgrade-variable numbers in tooltips.
- **Do NOT duplicate unit cost into `InfoArray.Resource` just to display a price.** The source documents contradict themselves here (`production.md` earlier asks to match, later says it's an increment beyond cost) — confirm via current parent chain and in-game test.
- For batch production, query original `Resource` first, then compute total batch cost; morph may involve cost deltas.
- `CostResource` `Multiply` is reported as not applicable — prefer existing `Add`/`Subtract`/`Set` examples and verify against actual data.

### Warp & Upgrades
- Multiple `CAbilWarpTrain` on the same building sharing one warp opportunity must share one charge link with `Location=Unit` — otherwise cross-ability cooldown bypass or all-buildings-share-cooldown bugs occur.
- `WarpTrain` repeated `Unit` sub-items are normalized by the Editor on save; multi-unit output needs independent completion-stage logic, not the standard `Train` batch example.
- Non-Protoss warp units: verify `Warpable`, birth/build Actor, `BuildModel`, and completion stages — successful normal training does not prove successful warp.
- For each form, verify tech-allow state. Weapon/armor per-level upgrades need each level + each form audited; if a shared damage effect was already modified by a vanilla upgrade, do not stack the same number again.
- New `CUpgrade` rows: do not treat `parent` as dependency or unlock. Vanilla campaign Bank triggers may grant the vanilla upgrade separately and stack with custom effects — test both grant paths.

### Requirement & Validator Notes
- `CRequirement` uses `NodeArray index="Show" Link="..."` for Show/Use; Not nodes use `OperandArray`. Confirm the active source before reusing a dependency validator.
- `CValidatorCombine` default is Or — check the default record; use explicit And for all-must-match, `Negate` to invert, never construct `Type="Not"`.

### Footprint Caveats (extend the section above)
- When adjusting creep placement, preserve original size, shape, `Check`/`Place`/`Pathing` layers, plus resource-building `NearResources`/`DropOff`/gas-vent constraints.

### Source Caveats (from `source-caveats.md`)
- **Production resource conflict:** `xml-patterns/production.md` first requires `InfoArray.Resource` match the unit price, then states it is an increment beyond cost. Do not blindly copy cost — verify parent chain, batch quantity, native display, and actual deduction.
- **Upgrade structure conflict:** `xml-patterns/core.md` shows a `CUpgrade`/`Level`/`Effect` effect-execution example not used elsewhere. Treat it as an unverified sample; check actual `CUpgrade` schema and official exports before adopting.
- **Export override conflict:** Folders may include Coop Commanders references; complete inactive XML folders may not exist. Confirm export inclusion and active-dependency enablement separately.
