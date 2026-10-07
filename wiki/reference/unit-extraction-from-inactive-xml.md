# Unit Extraction From Inactive XML

Reference workflow for recreating selected units from `XMLFromDependenciesWeDontUse/` without adding their source dependency as an active dependency.

The goal is not to clone an inactive dependency. The goal is to extract the smallest reliable data chain needed for a project campaign unit: gameplay, required visuals/audio, command-card integration, and localization.

Use the active dependency dumps and the project's own mod catalogs as the authored reference. Do not assume a separate local reference mod is present.

## Source Catalogs

| Catalog | Role in extraction |
|---|---|
| `Units.txt` | Start here. Defines stats, flags, ability links, weapon links, behavior links, command-card buttons, costs, cargo, footprints/movers, death settings, and create/death effect hooks. |
| `Abilities.txt` | Train/build/morph/research/cast data, command button faces, costs, cooldowns, charges, autocast validators, ability effects, and produced units. |
| `Weapons.txt` | Attack period/range/filters and the first attack effect link. |
| `Effects.txt` | Gameplay execution chain: damage, launch missile, search, set, persistent, switch, apply/remove behavior, create unit, modify unit, teleport, and issue-order effects. |
| `Behaviors.txt` | Passive state, buffs, auras, veterancy, cloaking, timed life, damage response, weapon switching, and morph helpers. |
| `Actors.txt` | Visual/audio event layer. Unit actors bind to `unitName`; action actors bind to effects; model/sound actors create secondary VFX/audio. |
| `Models.txt` | Model data IDs used by actors: unit models, portraits, death models, missiles, splats, glazes, placement models, impact/launch VFX, and animation-timed sound payloads. |
| `Sounds.txt` | Sound data IDs used by actors and model events: combat sounds, unit voice, UI sounds, loop sounds, cutscene/commander voice, volume/pitch/rolloff, subtitles, and portrait metadata. |
| `Buttons.txt` | Button faces, icons, hotkeys, tooltips, and passive command-card entries. |
| `Requirements.txt` / `Requirement Nodes.txt` | Show/use gating. These are often the noisiest co-op-specific pieces and should usually be rewritten for the project. |
| `Validators.txt` | Targeting, autocast, behavior, player, and actor guards. Keep behavior-critical validators; simplify commander/prestige validators. |
| `Movers.txt` / `Turrets.txt` | Needed only when a missile, unit, or weapon references custom movement or turret tracking. |
| `Upgrades.txt` | Field mutation patterns. Copy only upgrades that represent the actual campaign unit mechanic; skip commander progression upgrades. |

## Dependency Graph

Trace a candidate unit in this order:

1. `CUnit id="..."`.
2. Every `AbilArray`, `WeaponArray`, `BehaviorArray`, `EffectArray`, `CardLayouts`, `TechAlias`, cargo, footprint, mover, and turret reference on the unit.
3. Every `CAbil*` linked by the unit, including `InfoArray Unit`, `Effect`, `CmdButtonArray`, `AutoCastValidatorArray`, `Requirement`, `Cost`, and cooldown/charge links.
4. Every `CWeapon*` linked by the unit, then its `Effect` / `DisplayEffect`.
5. Every `CEffect*` reached from abilities and weapons until all effect chains terminate.
6. Every `CBehavior*` reached from the unit, abilities, and effects.
7. Every `CValidator*` reached from abilities, effects, behaviors, weapons, and actors.
8. Every `CRequirement*` and requirement node reached from abilities, command cards, train entries, and buttons.
9. The primary `CActorUnit` where `unitName` matches the unit ID, plus any parent/copy-source assumptions it depends on.
10. Every actor referenced from that actor's events and death/customization fields, especially `CActorAction`, `CActorModel`, `CActorSound`, `CActorRange`, `CActorSplat`, and `CActorBeam`.
11. Every `CModel*` and `CSound` referenced by actors or model animation events.
12. Every `CButton` and localization key needed for visible names, tooltips, buttons, alerts, and editor object names.

Always compare the candidate IDs against `DataEditorXML/` before copying. Some inactive records are only overrides on top of active campaign records.

A reduced extraction that includes units, effects, behaviors, and actors can still be incomplete if it omits models, sounds, turrets, helper weapons, validators, and editor localization. See the Editor round-trip checklist in [xml-patterns.md](../implementation/xml-patterns.md#editor-round-trip-checklist).

## Full Unit vs Override Patch

Inactive dependency exports contain two different shapes:

- Full or near-full units, where the inactive catalogs define the unit, weapon, actors, models, sounds, and most supporting gameplay.
- Override patches, where the inactive export modifies an already-existing campaign unit with dependency-specific behavior.

For override patches, copy only the fields that are intentionally needed. If the active LotV/HotS/WoL dependency already provides the base unit, actor, model, sound, death setup, or weapon, prefer that base and avoid duplicating the co-op patch.

## Reduction Rules

- Strip commander progression: `CommanderPrestige*`, mastery, commander levels, co-op achievements, top-bar resources, mutation hooks, ally-commander synergies, and commander announcer/mission response sounds.
- Replace co-op requirements with project requirements. Typical replacements should check campaign tech or a project upgrade with the configured project prefix.
- Keep gameplay validators only when removing them would break target legality, autocast sanity, behavior cleanup, or actor creation. Remove validators that only identify a co-op commander/player.
- Keep only sounds referenced by the final actor set. Skip cutscene, `ACVO_*`, commander response, tutorial, and UI sounds unless the unit specifically needs them.
- Keep only models referenced by the final actor set. Many catalogs include unrelated mutator, prestige, placement-preview, top-bar, or mission-only models.
- Rename final custom data IDs with the project's data ID prefix (verify against `AGENTS.md`; use a generic `My` prefix in code examples). Record the original source ID in implementation notes.
- After renaming, update actor string terms by hand. `UnitBirth.X`, `WeaponStart.X`, `Effect.X.Start`, `Abil.X.Start`, `MorphTo X`, `MorphFrom X`, `ValidateUnit X`, and `ValidatePlayer X` are exact string links.

## Catalog-Specific Notes

`CUnit` command cards often contain passive locked buttons for co-op progression. These are visual only unless backed by requirements and abilities. Remove passive locked buttons that advertise commander levels or mastery.

`CActorUnit` is often the largest required copy. It may reference inherited parent events, death customization, footprint actors, wireframes, icon paths, voice sets, placement models, portrait models, and many exact unit/weapon/effect terms. A unit can work mechanically while looking wrong if this chain is incomplete.

`CActorAction` is the bridge from gameplay effects to attack/ability visuals. For direct attacks, `effectAttack` usually points to the damage effect. For missile attacks, action actors may use `effectLaunch` and `effectImpact`. Do not copy unrelated action actors with similar names unless they are referenced by the selected unit's effects.

`CModel` entries sometimes inherit all useful art from a parent and only override scale/radius. A model with no `<Model value="..."/>` can still be valid if its parent supplies the `.m3`; verify the parent in active or inactive model catalogs.

`CSound` entries may use direct `AssetArray File` paths, `TemplateParam` placeholders, or only parent inheritance. Direct combat/effect sounds are usually safe to copy with their actor. Voice and commander response sounds often depend on broader localization/audio infrastructure and should be skipped for normal unit extraction unless already referenced by the kept unit actor.

## Representative Examples

A full inactive unit often mixes useful unit forms, morph abilities, actor model swaps, death models, and weapon sounds with dependency-specific progression, top-bar, and mission systems. Keep only the records required by the selected design, then rewrite or remove dependency-specific systems.

A lean unit variant that reuses active campaign attack visuals and adds only a model, portrait, icon, stat changes, and a small mechanic is usually easier to maintain than a whole-dependency copy.

When the active campaign dumps already define a close base unit, start there and add only the intended behavior. Do not import commander validation or revive hooks unless the design explicitly requires them.

## Pre-Extraction Checklist

Before editing project data for a chosen unit, create a short implementation note with:

- Source unit ID and target project-prefixed ID (e.g. `My...` in code examples; verify against `AGENTS.md` for actual project prefix).
- Whether the inactive source is a full unit or an override patch.
- Active dependency IDs that will be reused instead of copied.
- Required gameplay records: unit, abilities, weapons, effects, behaviors, validators, requirements, movers, turrets, upgrades.
- Required presentation records: unit actor, action actors, model/sound actors, models, sounds, buttons, icons/wireframes, localization.
- Co-op systems deliberately excluded.
- Any actor event terms that need exact renaming.

## Pre-Handoff Extraction Checklist

Before handing off an extracted unit/faction pass:

1. Parse every touched catalog as XML.
2. List all new top-level `id` values by catalog; verify each has an `ObjectStrings.txt` `Name` (add `EditorPrefix`/`EditorSuffix` where helpful).
3. Search touched XML for inactive-source ID references. Each must exist in active dependency dumps or be copied into the project intentionally.
4. Confirm command-card `Face` IDs exist in active dependencies or local `ButtonData.xml`. Prefer active campaign `Attack` over co-op-only faces.
5. Confirm player-facing units have `Unit/Name` and `Unit/Tooltip` in `GameStrings.txt`, with tooltips anchored by `CUnit.Description`.
6. Confirm production buttons have `Button/Name` and `Button/Tooltip` in `GameStrings.txt` unless they inherit from an active campaign button.
7. Confirm actor chains include required `CModel`, `CSound`, `CTurret`, helper `CWeapon`, and `CValidator` rows.
8. Strip co-op status-frame hooks (`CustomUnitStatusFrame`, `StatusBarOn`, `SuppressDefaultStatusBar`) when the active dependency set lacks the referenced UI file desc.
9. Run duplicate `(catalog type, id)` scan across all `GameData/` XML files before assuming an Editor warning is an external collision.

Missing presentation rows surface as blank icons/text, missing VFX/audio, `GenericUnitFallback`, or Editor warnings — not XML parse errors.
