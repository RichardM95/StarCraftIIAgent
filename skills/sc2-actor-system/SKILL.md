---
name: sc2-actor-system
description: StarCraft II actor system (events, terms, messages, parents) for the AeonOfIhanrii campaign. Use when creating or modifying CActorUnit/CActorAction/CActorModel/CActorBeam/CActorSound actors, troubleshooting VFX/audio/visibility issues, or extracting actors from inactive XML. Covers actor event-driven model, parent actor selection, missile defaults, texture swaps, indexed construction events, and editor round-trip pitfalls.
---

# SC2 Actor System

## When to Use

Load this skill when the task involves actor XML in `ActorData.xml` (or any `CActor*` catalog object): creating or modifying unit actors (`CActorUnit`), action/attack actors (`CActorAction`), model actors (`CActorModel`), beams, sounds, ranges, splats, or morph transition visuals. Also load when debugging invisible units, missing VFX/audio, broken texture swaps, or "more than one CActorUnit persisting in the same unit scope" warnings, and when extracting actors from inactive dependency XML.

## How Actors Work

Actor logic is **event-driven**: the actor declares what events it listens for and what it does when they fire. This is the reverse of gameplay data (abilities, effects, weapons), which are forward-declared — an ability says which effect to run; an actor says when to create itself.

Actors are calculated asynchronously on the player's local machine and are **not synchronized across the network**. Actor state cannot be compared reliably across clients, and actors with certain graphics settings may not exist on lower-end machines.

Three elements make up every actor event:

| Element | Parallel in Triggers | Description |
|---|---|---|
| Event | Trigger event | What happened (e.g. `UnitBirth.Marine`) |
| Terms | Condition | Extra conditions that must be true |
| Message / Send | Action | What to do (e.g. `Create`, `AnimPlay`, `SetTintColor`) |

Messages without a target are sent by the actor to itself. Actors can address one another by **name**, by **alias** (e.g. `_Unit` is the standard alias for a unit actor), or by **system reference** (e.g. `::Creator`).

Actor events can also be triggered from the Trigger Editor using the `Send Actor Message` action.

## Common Actor Fields

| Field | Description |
|---|---|
| Aliases | Alternate reference names. `_Unit` is the standard unit-actor alias used by other actors to address the unit without knowing its exact ID. |
| Copy Source | Sets another actor as a proxy parent. Child actors inherit from the Copy Source if the relevant properties are listed in `Accepted Property Transfers` (source) and `Inherited Properties` (child). |
| Filter | Restricts actor visibility to Ally / Enemy / Neutral / Self groups. |
| Filter Player | Per-player visibility override. |
| Flags — Suppress Creation Errors | Silences missing-asset errors. Use when an actor is intentionally designed to fail creation under certain conditions. |
| Fog Visibility | Dimmed / Hidden / Snapshot / Visible — controls how the actor appears under fog of war. |
| Events | The actor event list (event + terms + message triples). |
| Macros | Reusable event macro collections that can be attached to multiple actors. |
| Remove | Explicitly removes unwanted inherited events from the parent chain. |
| Terms | Short-circuit creation condition — identical to the creation event's term, overwrites it if both are set. |
| Host Supporter | A supporting actor; when it dies, `SupporterDestruction` is sent to the hosting actor. |
| Accepted Property Transfers | Which properties this actor passes to child actors (model scale, opacity, team color, visibility, decal, textures, fog color, position, rotation). |
| Inherit Type | `Once` (inherit on creation), `Continuous` (dynamically updated), `None`. |
| Inherited Properties | Which properties this actor inherits from its host on creation. Must match the host's `Accepted Property Transfers`. |

**Editor colour coding in the Events field:**

- Gray = inherited from core game data
- Blue = from a Blizzard dependency mod
- Green = from the current project
- Red = indexed override of an inherited parent event (cosmetic only — not an error)

## Useful Parent Actors

| Actor Type | Parent Name | When to Use |
|---|---|---|
| Unit | `GenericUnitStandard` | Default for all unit actors. Handles birth, death, selection, attack animations. |
| Action | `GenericAttack` | Default for attack/ability action actors. Provides `Attack`, `Launch`, `Impact` effect tokens. For beam/instant attacks set `Attack`; for missile attacks set `Launch` + `Impact`. Do **not** set all three. |
| Model | `ModelAddition` | Attach a model to another actor (e.g. a buff visual on a unit). |
| Model | `ModelAnimationStyleContinuous` | Persistent non-attached model where you control destruction (e.g. Psi Storm area). |
| Model | `ModelAnimationStyleOneShot` | Auto-cleans up after its animation finishes (e.g. explosions). Prefer over manual cleanup for one-shot VFX. |
| ModelMaterial | `BehaviorGlaze` | Applies a glaze/tint to a unit while a behavior is active. Set the `Buff` token and `Model`. |
| Beam | `Beam Simple Animation Style Continuous` | Beam that persists until destroyed. |
| Beam | `Beam Simple Animation Style One Shot` | Beam that plays once and destroys itself. |
| Range | `Range Abil` | Shows ability range ring during targeting. Set the `Ability` token — reads cast range automatically. |
| Range | `Range Behavior` | Shows a range ring while a behavior is on a unit. Set range manually. |
| Range | `Range Weapon` | Shows weapon range ring (same auto-read pattern as Range Abil). |
| Splat | `Cursor Splat` | Splat at cursor position for AOE previews (e.g. Psi Storm). Set `Abil` token and `Model`. |
| Sound | `SoundOneShot` | Plays sound once then destroys itself. |
| Sound | `SoundContinuous` | Plays sound until actor is destroyed. |

**Known editor bug with Range/Splat parents:** After setting the token in the Data Module, the generated `<On>` events may be malformed. Fix by right-clicking the Events field → `Reset To Parent Value` → select the parent name. Alternatively open XML view and delete the generated `<On>` lines for the new actor.

## Action Actor Missile Defaults

For a `CActorAction` based on `GenericAttack`, a missile actor named exactly `<ActionActorId>Missile` is the default missile binding. In XML this may appear as an explicit `<Missile value="..."/>`, but the SC2 Editor can remove that field on save because the resolved preload token is already `##id##Missile`.

Treat that removal as normal when all of these are true:

- The action actor uses `parent="GenericAttack"` or another parent whose missile token already resolves to `##id##Missile`.
- The intended missile actor ID is exactly the action actor ID plus `Missile`.
- `PreloadAssetDB.txt` still shows the action actor resolving the missile slot through `##id##Missile`.

Do **not** generalize this to action actors that inherit a specific named missile from their parent. For example, an action actor based on `MarauderAttackBase` may inherit `MarauderAttackMissile`; if the custom projectile should be `<CustomActionId>Missile`, keep an explicit `<Missile value="..."/>` override.

## Texture Declarations and Inherited Swaps

`TextureDeclares` on a model map texture prefixes and filename adaptations to texture slots; they do not initiate a swap by themselves. Actor messages such as `TextureSelectById`, `TextureSelectByMatch`, and `TextureSelectBySlot` perform the selection. A copied model or skin can therefore appear corrupted when it retains declarations that inherited actor events target through campaign upgrades such as `DarkProtoss` or `PurifierProtoss`.

Removing a declaration can make the unwanted selection stop resolving, but it also disables any legitimate dynamic texture swap that needs that slot. Prefer removing or overriding the inherited actor events, or preventing their enabling upgrade, when the variant still needs dynamic texture selection. Omit the declarations only when the model is intentionally self-contained and no retained actor event should swap its textures.

## Indexed unit-actor construction events

`CActorUnit` rows that retarget the inherited `GenericUnitMinimal` event array must preserve the inherited index meanings:

- index `4`: `UnitConstruction.<unit>.Start` (creates the unit actor for construction/warp presentation)
- index `5`: `UnitConstruction.<unit>.Finish` (finishes the construction presentation)

Do **not** use a bare `UnitConstruction.<unit>` term at either index, and do **not** put `.Start` at index 5. The latter overwrites the inherited finish handler and can leave two persistent models or a fallback warp sphere. A `BuildModel` alone cannot correct a shifted event override. After an Editor round trip, audit all project `CActorUnit` rows for these exact suffixes because the Editor may rematerialize inherited indexed events.

## Morph Transition Presentation Actors

For project-owned visual-only morph transitions, prefer `CActorModel parent="ModelAdditionNoAnims"` hosted on `_Selectable` through inheritance. Create it on `AbilMorph.*.Start`, play the desired morph animation on `ActorCreation`, destroy it on morph finish, and include `ActorOrphan -> Destroy` as a fallback.

Avoid importing a visual overlay as `CActorUnit parent="GenericUnitBaseMorphTransition"` or as `CActorMissile`. Even when its `unitName` points at a dummy morph ID, creation from a custom unit's morph event can place it in the real unit scope and emit `More than one CActorUnit persisting in the same unit scope`. The Editor may preserve the XML exactly; the warning is a runtime scope problem, not a serialization problem.

For variant-specific morph visuals, verify the referenced `CModel` has an explicit `.m3` asset path in the active dependency chain. A reduced row copied from an inactive dependency may contain only radius/scale metadata because its original dependency supplied the asset elsewhere. That can produce an invisible morph or silently fall back to a generic vanilla model. Prefer a project-owned model ID with the explicit asset path, then point the transition actor at that ID.

## Extracting Actors From Inactive XML

When recreating a unit from inactive `XMLFromDependenciesWeDontUse/`, treat the primary `CActorUnit` as the presentation root. It commonly links the live model, build/placement model, portrait model, wireframe, group icon, unit icon, death models, voice sounds, footprint actor, attack animation events, morph/model-swap events, and hosted secondary actors.

Action actors (`CActorAction`) are the usual bridge from gameplay to visuals/audio. Match them by `effectAttack`, `effectLaunch`, or `effectImpact`, then copy only the launch/impact models and sounds they actually reference.

Be strict about co-op-specific actor terms. Events using `ValidatePlayer Is...CoopCommander`, `CommanderPrestige*`, mutator IDs, top-bar signals, or commander-only morph/revive hooks should normally be removed or rewritten for the project. Actor event terms are exact string references, so renamed units, weapons, abilities, effects, behaviors, validators, models, and sounds must be renamed consistently.

## Actors vs Triggers

Both systems can accomplish similar things, but the correct choice depends on scope:

- **Actor events** — describe the general behaviour of a *type* of unit/effect (what a Marine always looks like, sounds like, animates like).
- **Triggers** — adjust *specific instances* of units or objects during gameplay (tint this particular Marine blue when a bonus objective completes).

When triggers need to drive actor changes, use `Send Actor Message` to push messages into the actor event system from trigger code.

## Editor Round-Trip Pitfalls

- After Editor save, scan `GameData/` for duplicate `(catalog type, id)` pairs across `GameData.xml` and typed side catalogs. Keep one canonical row per ID.
- Editor warnings, blank editor names, blank command-card icons/text, and preload churn are signals of an incomplete extraction graph — not cosmetic output.
- Recheck child-unit indexed command-card overrides. The Editor can expand inherited indexed `LayoutButtons` fields into local child elements and preserve inherited requirements that do not belong on the custom unit.
- Strip copied or inherited actor UI hooks when the active dependency/UI context lacks the referenced file desc:
  - `CustomUnitStatusFrame value="Coop_UnitStatus_.../..."`
  - `CustomUnitStatusFrame value="HotS_UnitStatus/..."`
  - `CustomUnitStatusFrame value="LotV_UnitStatus/..."`
  - `StatusBarOn index="Custom" value="1"`
  - `UnitFlags index="SuppressDefaultStatusBar" value="1"`
- If a local actor inherits a problematic status frame from its parent, prefer a direct safe parent such as `GenericUnitStandard` plus copied visual fields over keeping the inherited custom UI chain.

## Reference

- `wiki/reference/actors.md` — full actor system reference
- `wiki/implementation/xml-patterns/editor-roundtrip-and-actors.md` — round-trip checklist & actor XML patterns
- `wiki/reference/unit-extraction-from-inactive-xml.md` — full reduced extraction workflow
- `wiki/implementation/xml-patterns.md` — XML patterns including Terran drop pod actor usage
- `tools/audit-actor-and-card-integrity.py` — actor/card integrity auditor
- `sc2-catalog-xml` skill — broader XML authoring rules that interact with actor inheritance

## Chinese Task Knowledge (Merged)

Distilled from `references/actors-and-extraction.md` and `references/source-caveats.md`. Duplicates with sections above omitted.

### Unit Extraction Checklist
1. Distinguish a full unit definition from a patch overlay on an existing unit. Prefer reusing the active dependency's base data; only copy the minimal complete chain the design needs.
2. Trace from the unit through abilities, weapons, effects (until terminator), behaviors, validators, requirements, production & command card, Mover/Turret/Footprint.
3. Then trace Unit Actor, attack/ability Action Actors, Missile/Beam/Model/Sound Actors, down to the actual Model, Sound, icon, wireframe, and localization.
4. List source IDs, target project IDs, reused active definitions, definitions to copy, and excluded systems. Co-op commander levels, prestige, masteries, top-bar, and voice systems are kept only when the design requires them.
5. After renaming, audit string events `UnitBirth.X`, `Effect.X.Start`, `Abil.X.Start`, `MorphTo X`, `MorphFrom X`, `ValidateUnit X` — plain XML link replacement does not cover all event text.
6. Inactive exports are reference material only; inclusion in an index does not prove the dependency is enabled. Confirm `XMLFromDependenciesWeDontUse/` paths actually exist.

### Common Presentation Faults (priority-trace table)
| Symptom | Trace first |
|---|---|
| GenericUnitFallback / white sphere | Unit Actor creation event, Model active parent chain & .m3, Missile Actor, warp ability |
| Multiple `CActorUnit` in same scope | Inherited birth events targeting the vanilla unit, extra morph Actors, duplicate build events |
| Multiple `CActorAction` per effect | Inherited vanilla effect listener AND custom listener both firing |
| Damage without projectile/beam/sound | Weapon → Launch/Impact Effect → Action → Missile/Beam/Model/Sound |
| Disappears or duplicates after save | Standard catalog migration, duplicate definitions, array-index & parent-field normalization |

### Inheritance Caveats
- When inheriting from a named unit Actor, changing only `unitName` does not redirect all parent events. Override unit-specific events by their actual parent-chain index; do not blindly append a new birth listener.
- Do not apply an old Ravager index table to every Actor — the construction Start/Finish index docs disagree across source pages. Always check the current `GenericUnitMinimal` and named parent.
- Project-specific projectiles can reference `GenericAttackMissile`, attack actions can reference `GenericAttack`; copy the required attach points, models, impact maps, physics, flags, and animations.
- A custom Beam must actually be referenced by an Action — an unbound Beam edits nothing.
- Morph transition visual-only actors: prefer `CActorModel parent="ModelAdditionNoAnims"`, create on morph start, destroy on morph finish, include `ActorOrphan → Destroy`. Do not make a visual overlay a second persistent Unit Actor.
- A model export that only has `scale`/`radius` may depend on an unexported parent model asset; the same applies to Sounds and their templates/parents. Trace to the actual asset, do not stop at ID existence.

### Save Round-Trip
- Editor save may relocate mixed catalog objects to standard files. Keep canonical rows, clean same-mod duplicate rows, preserve effective fields and localization anchors. Compare by ID or by ignoring whitespace to spot real changes.
- If the active UI does not provide a copied `CustomUnitStatusFrame`, trace and handle that field, `StatusBarOn`/`Custom`, `SuppressDefaultStatusBar`, and the parent chain — do not blindly clear valid UI. Then test training, warp, morph, death/revive, attack, and audio.

### Source Caveats (from `source-caveats.md`)
- **Actor index conflict:** `catalog-rules.md`'s Ravager table (indices 4/5 and bare `UnitConstruction`) disagrees with `editor-roundtrip-and-actors.md`'s Start/Finish rules. Always inspect the live parent Actor's `On` array; do not copy a fixed index table.
- **Sound export conflict:** `catalog-rules.md` claims no active sound dumps exist, but `DataEditorXML/` actually contains layered `Sounds.txt`. Use actual files and dependency-enablement state as ground truth.
