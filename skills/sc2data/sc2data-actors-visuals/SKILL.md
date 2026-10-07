---
name: sc2data-actors-visuals
description: SC2 Data Editor — Actors, visual effects, animations, sounds, and the actor event system in XML. Use when creating or modifying CActorUnit, CActorModel, CActorAction, CActorSound, CActorBeam, CActorSite, or any <On Terms="..." Send="..."/> event wiring. Covers actor creation, parent types, aliases, macros, death arrays, sound arrays, and all common actor messages. Always consult the catalogsData.xsd schema for exact fields and structure — do not assume unsupported fields exist. Do not use for game logic/damage (use sc2data-effects-weapons) or unit/ability data (use sc2data-units-abilities). Actors are client-side only — they cannot affect gameplay.
---

## Loading Boundary

- **This sub-skill owns:** CActor* (Unit, Model, Action, Sound, Beam, Site), the actor event system, parent types, aliases, macros, death/sound arrays, and actor messages
- **Parent root skill (`sc2-catalog-xml`) owns:** project conventions, schema/syntax rules, source-of-truth, naming prefixes
- **Sibling sub-skills own:** `sc2data-units-abilities` (CUnit/CAbil XML), `galaxy-actor-and-visuals` (Galaxy actor API), `sc2data-effects-weapons` (CEffect/CWeapon that actors present)

# SC2 Data Editor – Actors & Visuals

## Prerequisite

Load [`sc2-catalog-xml`](../../sc2-catalog-xml/SKILL.md) first for project-wide Catalog XML schema rules (child value elements not raw attributes, ASCII-only, no `AbilAutoCmd`, no `CBehaviorBuff.InitEffect`, no comment-only catalogs), parent inheritance pitfalls, effective-value evidence workflow, localization anchors, and Editor round-trip safety. This sub-skill owns deep schema reference only; project conventions live in the router skill.

Actors are the **visual and audio layer** of StarCraft II data. They respond to game events and play animations, spawn VFX models, and play sounds. Actors run **locally on each client** and are **not network-synchronized** — they have zero effect on gameplay state.

## Key References

| Resource | URL |
|---|---|
| Actors guide | https://s2editor-guides.readthedocs.io/New_Tutorials/04_Data_Editor/060_Actors/ |
| Actor Messages Rundown | https://s2editor-guides.readthedocs.io/New_Tutorials/04_Data_Editor/061_Actor_Messages_Rundown/ |
| SC2Mapster wiki | https://sc2mapster.wiki.gg/ |
| Actors (wiki) | https://sc2mapster.wiki.gg/wiki/Data/Actors |
| Actor Events (wiki) | https://sc2mapster.wiki.gg/wiki/Data/Actors/Events |
| Actor Terms (wiki) | https://sc2mapster.wiki.gg/wiki/Data/Actors/Terms |
| Blizzard Tutorials – Actors.md | https://github.com/SC2Mapster/blizzard-tutorials/blob/master/docs/New_Tutorials/04_Data_Editor/060_Actors.md |
| ShadowDragon Base.SC2Data (real GameData XML reference) | https://github.com/ShadowDragonSC2/Base.SC2Data/tree/main/GameData |
| **Source of Truth: CatalogsData XSD Schema** | https://github.com/ShadowDragonSC2/Base.SC2Data/raw/refs/heads/main/.vscode/schemas/catalogsData.xsd — Always consult this for exact fields, attributes, and structure of each actor type. Do not assume fields exist; verify against the schema. |
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

> **File placement:** When creating actors for a new unit, put them in the unit's own self-contained XML file (`GameData/Faction/UnitName/UnitName.xml`), not in a monolithic `ActorData.xml`. Register the file via `<Catalog path="..."/>` in `GameData.xml`. See the sc2data-units-abilities skill for the full file template.

## Actor File

File: `Base.SC2Data/GameData/ActorData.xml`

All actor entries are children of `<Catalog>`:

```xml
<?xml version="1.0" encoding="utf-8"?>
<Catalog>
    <CActorUnit id="MyUnitActor" parent="GenericUnitStandard" unitName="MyUnit">
        ...
    </CActorUnit>
</Catalog>
```

---

## Actor Types

| XML Type | Purpose |
|---|---|
| `CActorUnit` | Main visual wrapper for a unit — links model, sounds, animations |
| `CActorModel` | A standalone or attached 3D model |
| `CActorAction` | Powers a weapon's attack animation sequence |
| `CActorSite` | Attachment point / positional anchor |
| `CActorBeam` | Laser/beam line between two points |
| `CActorRange` | Range indicator circle drawn under a unit |
| `CActorSound` | Plays a sound as an actor event |
| `CActorModelMaterial` | Modifies material/shader parameters on a model |
| `CActorTerrain` | Applies terrain effects (squibs, burn marks) |
| `CActorMissile` | Visual projectile (no event system) |
| `CActorDoodad` | Environmental object (tree, rock) |
| `CActorQuad` | 2D sprite/quad overlay |
| `CActorQuery` | Actor that queries game state |
| `CActorRegion` | Region-based actor |
| `CActorSiteOp` | Site operation actor |
| `CActorSplat` | Ground decal/splat |
| `CActorTurret` | Turret actor |
| `CActorVideo` | Video playback actor |

> **Note:** This is not an exhaustive list. Always consult the catalogsData.xsd schema for the complete set of actor types and their exact fields/attributes. The schema is the definitive source of truth for what fields each actor type supports.

---

## Event System — `<On Terms="..." Send="..."/>`

Actors are **event-driven and reversed**: the actor itself declares when it activates, not the thing that triggers it.

```xml
<On Terms="EventName.DataId.SubEvent; AnotherTerm; !NegatedTerm" Send="MessageName [Arg1] [Arg2]"/>
```

### Terms syntax

| Syntax | Meaning |
|---|---|
| `ActorCreation` | Actor has been created |
| `ActorOrphan` | Actor's host unit died |
| `UnitBirth.UnitId` | Unit of this type was born |
| `UnitDeath.UnitId` | Unit of this type died |
| `UnitDeathCustomize` | Unit death triggered (more flexible) |
| `WeaponStart.WeaponId.AttackStart` | Weapon attack began |
| `WeaponStop.WeaponId.AttackStop` | Weapon attack ended |
| `Abil.AbilId.SourcePrepStart` | Ability cast started |
| `Abil.AbilId.SourceFinish` | Ability finished casting |
| `Abil.AbilId.SourceStop` | Ability interrupted |
| `AbilMorph.*.Finish` | Any morph ability completed |
| `Upgrade.UpgradeId.Add` | Player researched this upgrade |
| `Upgrade.UpgradeId.Remove` | Upgrade removed/lost |
| `ValidateUnit UpgradeId` | Test if upgrade is researched |
| `IsStatus DeathSuicide 0` | Negate: unit did NOT suicide |
| `MorphTo UnitId` | Unit morphed into this type |
| `MorphFrom UnitId` | Unit morphed away from this type |

Semicolons `;` are **AND** — all terms must be true.  
`!` prefix negates a term.  
`*` is a wildcard for a single segment.

---

## Common Actor Messages (Send)

| Message | Effect |
|---|---|
| `Create` | Create this actor (or a referenced actor) |
| `Destroy` | Destroy this actor |
| `DestroyFinal` | Destroy immediately, no death animation |
| `AnimPlay Attack` | Play animation named "Attack" once |
| `AnimBracketStart Attack Attack` | Start looping anim: Opening/Content/Closing tokens |
| `AnimBracketStop Attack` | Stop the bracketed animation |
| `AnimClear Attack` | Clear a running animation |
| `AnimGroupApply Superior` | Apply animation group (variation set) |
| `SetTintColor {255 128 0 255}` | Tint colour (R G B A 0–255) |
| `SetOpacity 0.5 0` | Set opacity (0.0=opaque, 1.0=transparent); 0=no blend |
| `ModelSwap NewModelId` | Swap the model at runtime |
| `GlowStart` | Start pulsing glow |
| `GlowStop` | Stop pulsing glow |
| `HaloStart` | Start outline halo |
| `HaloStop` | Stop outline halo |
| `HaloSetColor {R G B}` | Set halo colour |
| `StatusSet Status 1` | Set status flag (e.g. Cloak) |
| `SetWalkAnimMoveSpeed 3` | Adjust walk animation playback rate |
| `TerrainSquibActivateGroup MyGroup` | Activate a terrain squib group |
| `SendToRef ::Target Create` | Tell the target actor to Create |

---

## CActorUnit — Full Example

```xml
<CActorUnit id="MyUnitActor" parent="GenericUnitStandard" unitName="MyUnit">
    <!-- Cross-actor messaging alias (e.g. _UnitMedium for medium-sized units) -->
    <Aliases value="_UnitMedium"/>

    <!-- Reusable event macro (defined elsewhere, expands into multiple On entries) -->
    <Macros value="StandardDeathMacro"/>

    <!-- Primary model -->
    <Model value="MyUnitModel"/>
    <AnimBlendTime value="0.300000"/>

    <!-- Construction model shown while building -->
    <BuildModel value="MyUnitBuildModel"/>

    <!-- Portrait model for unit info panel -->
    <PortraitModel value="MyUnitPortrait"/>

    <!-- Placement ghost model -->
    <PlacementModel value="MyUnitPlacement"/>

    <!-- Death variations -->
    <DeathArray index="Normal" ModelLink="MyDeathModel" SoundLink="MyDeathSound" VoiceLink=""/>
    <DeathArray index="Blast" ModelLink="MyBlastDeathModel"/>

    <!-- Unit sounds -->
    <SoundArray index="Ready" value="MyUnit_Ready"/>
    <SoundArray index="What" value="MyUnit_What"/>
    <SoundArray index="Yes" value="MyUnit_Yes"/>
    <SoundArray index="Attack" value="MyUnit_Attack"/>
    <SoundArray index="Pissed" value="MyUnit_Pissed"/>

    <!-- UI icons -->
    <GroupIcon><Image value="Assets\Textures\wireframe-myunit.dds"/></GroupIcon>
    <UnitIcon value="Assets\Textures\btn-unit-myunit.dds"/>
    <HighlightTooltip value="Unit/Tooltip/MyUnit"/>

    <!-- Health bar positioning -->
    <BarOffset value="25"/>
    <BarWidth value="90"/>

    <!-- Actor events -->
    <On Terms="ActorCreation" Send="AnimPlay Birth"/>
    <On Terms="UnitBirth.MyUnit" Send="Create MyBirthEffectActor"/>
    <On Terms="WeaponStart.MyWeapon.AttackStart" Send="AnimBracketStart Attack Attack"/>
    <On Terms="WeaponStop.MyWeapon.AttackStop" Send="AnimBracketStop Attack"/>
    <On Terms="Abil.MyAbility.SourcePrepStart" Send="AnimPlay Spell"/>
    <On Terms="Upgrade.MyUpgrade.Add" Send="AnimGroupApply Superior"/>
    <On Terms="UnitDeathCustomize; IsStatus DeathSuicide 0" Send="Create MyDeathSound"/>
    <On Terms="ActorOrphan" Send="Destroy"/>
</CActorUnit>
```

---

## CActorAction — Weapon Attack Sequence

Used with the `GenericAttack` parent. The three tokens are **Attack**, **Launch**, and **Impact**:

```xml
<CActorAction id="MyWeaponAction" parent="GenericAttack">
    <!-- Attack: play windup animation on the unit actor -->
    <On Terms="ActionStart" Send="AnimPlay Attack ::Creator"/>

    <!-- Launch: spawn projectile model at weapon launch point -->
    <On Terms="ActionLaunch" Send="Create MyProjectileModel ::Creator"/>

    <!-- Impact: spawn explosion model at target -->
    <On Terms="ActionImpact" Send="Create MyImpactModel ::Target"/>
</CActorAction>
```

---

## Actor Parents Reference

| Parent | What it provides |
|---|---|
| `GenericUnitStandard` | Default unit actor — selection circle, health bar, standard events |
| `GenericAttack` | Weapon action actor — Attack/Launch/Impact event tokens |
| `ModelAddition` | Attaches a model to another actor (buff visuals, attachments) |
| `ModelAnimationStyleContinuous` | Looping model (persistent AoE like Psi Storm) |
| `ModelAnimationStyleOneShot` | One-shot model (explosions, birth effects) |
| `BehaviorGlaze` | Applies glaze (overlay) while a behavior is active; uses `buff` token |
| `SoundOneShot` | Plays sound once then auto-destroys |
| `SoundContinuous` | Plays sound until destroyed |
| `Range Abil` | Range indicator for an ability |
| `Range Behavior` | Range indicator for a behavior/aura |
| `Range Weapon` | Range indicator for a weapon |
| `Cursor Splat` | AoE targeting cursor shown during ability targeting |

> **Warning:** When using `Range *` or `Cursor Splat` parents via the editor UI, the editor generates default `<On` events. After creation, **Reset To Parent Value** on the Events field, or manually delete the generated `<On` lines in XML view to avoid duplicate/broken event wiring.

---

## Aliases

Aliases let other actors address this actor by a shorthand type name:

```xml
<Aliases value="_UnitMedium"/>
```

Common system aliases used in `Terms`:
- `::Creator` — the actor that created this actor
- `::Host` — the unit this actor is attached to
- `::Target` — the target of an action
- `::Main` — the main actor of the host unit
- `_Unit` — any unit actor (generic)
- `_Structure` — any structure actor
- `_UnitSmall` / `_UnitMedium` / `_UnitLarge` — by size class

---

## Macros

Macros expand into a set of `<On>` entries at runtime. Defined in a `CActorMacro` entry, referenced by name:

```xml
<Macros value="ZergBurrowStandardAnimMacro"/>
```

Blizzard provides many reusable macros for common patterns (burrow/unburrow, death, cloak, etc.). Check existing units of the same race/type for applicable macros before writing manual `<On>` events.

---

## CActorModel — Standalone or Attached Model

```xml
<!-- Birth VFX: one-shot model, auto-destroys after animation plays -->
<CActorModel id="MyBirthEffectActor" parent="ModelAnimationStyleOneShot">
    <Model value="MyBirthModel"/>
    <On Terms="ActorCreation" Send="AnimPlay Birth"/>
    <On Terms="AnimDone" Send="Destroy"/>
</CActorModel>

<!-- Persistent looping area model -->
<CActorModel id="MyAuraModel" parent="ModelAnimationStyleContinuous">
    <Model value="MyAuraModel"/>
</CActorModel>
```

---

## CActorSound

```xml
<CActorSound id="MyReadySound" parent="SoundOneShot">
    <Sound value="MyUnit_Ready"/>
    <On Terms="ActorCreation" Send="AnimPlay"/>
    <On Terms="ActorOrphan" Send="Destroy"/>
</CActorSound>
```

---

## CActorBeam — Laser Beam

```xml
<CActorBeam id="MyLaserBeam">
    <Model value="MyBeamModel"/>
    <!-- Beam connects ::Creator (source) to ::Target -->
</CActorBeam>
```

---

## CActorMissile — Projectile Actor

**Important:** CActorMissile does **NOT** have an `<On>` array for event wiring. It is purely a visual projectile with no event system. Use CActorAction or other actors for event handling around missile launches/impacts.

```xml
<CActorMissile id="MyMissileActor">
    <Model value="MyMissileModel"/>
    <!-- Missile follows its mover/physics, no events -->
</CActorMissile>
```

---

## Advanced Event Patterns

### Timer Pattern — per-actor delays and loops

A timer lives entirely on the actor. Set it on creation and respond to its expiry:

```xml
<!-- Start a 3-second timer (with up to 1 second random variance) on creation -->
<On Terms="ActorCreation" Send="TimerSet MyTimer 3 1"/>

<!-- Respond when that timer fires, identified by the TimerName term -->
<On Terms="TimerExpired; TimerName MyTimer" Send="AnimPlay Attack"/>
```

`TimerSet <Name> <BaseDuration> <RandomRange>` — adds a random 0–RandomRange seconds on top. Use `TimerStop MyTimer` to cancel before expiry.

### Signal Pattern — cross-actor events

Signals send an artificial event from one actor to another via a reference alias:

```xml
<!-- From a buff actor: tell the host unit actor to play a flash -->
<On Terms="ActorCreation" Send="Signal AbilityFlash ::Host"/>

<!-- In the main unit CActorUnit: listen for that signal -->
<On Terms="Signal AbilityFlash" Send="AnimPlay Flash"/>
```

Signals bypass the normal game event system and go directly from sender to receiver.

### Status Set — actor state machine

Use `StatusSet` + `IsStatus` to track internal actor state without needing external data:

```xml
<!-- Track burrow state -->
<On Terms="Abil.BurrowDown.SourceFinish" Send="StatusSet Burrowed 1"/>
<On Terms="Abil.BurrowUp.SourceFinish"   Send="StatusSet Burrowed 0"/>

<!-- Conditionally act only when burrowed -->
<On Terms="WeaponStart.MyWeapon.AttackStart; IsStatus Burrowed 1" Send="AnimPlay BurrowedAttack"/>
```

### Cap — limit event to fire N times per actor lifetime

The `Cap N` term prevents an event from triggering more than N times over the actor's life:

```xml
<!-- Play birth anim only once even if creation somehow fires again -->
<On Terms="ActorCreation; Cap 1" Send="AnimPlay Birth"/>
```

### From Effect Tree Descendant — isolate per-effect-instance actors

When multiple instances of the same effect run simultaneously (e.g. multiple persistent effects), use `FromEffectTreeDescendant` to restrict each actor's response to its **own** effect tree only:

```xml
<On Terms="Effect.TentacleHit; FromEffectTreeDescendant TentacleEffect" Send="AnimPlay Hit"/>
```

Without this term, every active instance of that actor type would respond to every matching event.

### Upgrade Event — Affected Unit Array requirement

The `Upgrade.UpgradeId.Add` actor event **only fires if the unit type is in the upgrade's `Affected Unit Array`** in the Data Editor. If the event never fires in playtesting, add the unit to that array:

```xml
<CUpgrade id="MyUpgrade">
    <AffectedUnitArray value="MyUnit"/>   <!-- required for Upgrade actor event to fire on MyUnit -->
</CUpgrade>
```

### Ability Charge/Cooldown Actor Events

Charge and cooldown actor events only fire if the corresponding flags are set on the ability:

| Ability flag (`Shared Flags`) | Enables actor events |
|---|---|
| `Register Charge Event` | `Abil.MyAbility.ChargeStart`, `.ChargeUse`, `.ChargeExpire` |
| `Register Cooldown Event` | `Abil.MyAbility.CooldownStart`, `.CooldownExpire` |

---

## Best Practices

- Actors **do not affect gameplay** — never use actors to track game state.
- Prefer macros over manual `<On>` events when the unit race/type has matching macros.
- Keep actor ids consistent with unit ids: unit `MyUnit` → actor `MyUnitActor`.
- Use `parent="ModelAnimationStyleOneShot"` for all one-time VFX (explosions, birth effects).
- Always add `<On Terms="ActorOrphan" Send="Destroy"/>` to orphan non-unit actors that should clean up.
- Test animations in the editor with the Actor Viewer (F7 in the editor).
