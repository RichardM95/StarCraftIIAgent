# SC2 Actor System Reference

Actors control everything visible or audible in the game — unit models, impact sounds, ability VFX, beams, splats, and more. They are calculated asynchronously on the player's local machine and are **not synchronized across the network**, so actor state cannot be compared reliably across clients. Actors with certain graphic settings may not exist on lower-end machines.

---

## How Actors Work

Actor logic is **event-driven**: the actor declares what events it listens for and what it does when they fire. This is the reverse of gameplay data (abilities, effects, weapons), which are forward-declared — an ability says which effect to run; an actor says when to create itself.

For campaign Terran drop pods, `BarracksDropPod` is a `CActorModel` that creates on `Effect.DropTrain.Start` and uses the `BarracksDropPod` model (`DropPodFalling.m3`). The gameplay side is `DropTrainSet` → `MakePrecursor` + `DropTrain`; projects can reuse that chain for Terran field-warp production. See [xml-patterns.md](../implementation/xml-patterns.md#terran-drop-pod-visuals-for-field-warp-production).

Three elements make up every actor event:

| Element | Parallel in Triggers | Description |
|---------|---------------------|-------------|
| Event | Trigger event | What happened (e.g. `UnitBirth.Marine`) |
| Terms | Condition | Extra conditions that must be true |
| Message/Send | Action | What to do (e.g. `Create`, `AnimPlay`, `SetTintColor`) |

Messages without a target are sent by the actor to itself. Actors can address one another by **name**, by **alias** (e.g. `_Unit` is the standard alias for a unit actor), or by **system reference** (e.g. `::Creator`).

Actor events can also be triggered from the Trigger Editor using the `Send Actor Message` action, letting triggers drive actor behaviour directly.

---

## Common Actor Fields

| Field | Description |
|-------|-------------|
| Aliases | Alternate reference names. `_Unit` is the standard unit-actor alias used by other actors to address the unit without knowing its exact ID. |
| Copy Source | Sets another actor as a proxy parent. Child actors inherit from the Copy Source if the relevant properties are listed in `Accepted Property Transfers` (source) and `Inherited Properties` (child). |
| Filter | Restricts actor visibility to Ally / Enemy / Neutral / Self groups. |
| Filter Player | Per-player visibility override. |
| Flags — Suppress Creation Errors | Silences missing-asset errors. Use when an actor is intentionally designed to fail creation under certain conditions. |
| Fog Visibility | Dimmed / Hidden / Snapshot / Visible — controls how the actor appears under fog of war. |
| Events | The actor event list (event + terms + message triples). |
| Macros | Reusable event macro collections that can be attached to multiple actors. |
| Remove | Explicitly removes unwanted inherited events from the parent chain. |
| Terms | Short-circuit creation condition — identical to the creation event's term, overwrites it if both are set. Useful for data organisation. |
| Host Supporter | A supporting actor; when it dies, `SupporterDestruction` is sent to the hosting actor (often used to destroy it or play a death animation). |
| Accepted Property Transfers | Which properties this actor will pass to child actors (model scale, opacity, team color, visibility, decal, textures, fog color, position, rotation, etc.). |
| Inherit Type | `Once` (inherit on creation), `Continuous` (dynamically updated), `None`. |
| Inherited Properties | Which properties this actor inherits from its host on creation. Must match the host's `Accepted Property Transfers`. |

**Editor colour coding in the Events field:**
- Gray = inherited from core game data
- Blue = from a Blizzard dependency mod
- Green = from the current project
- Red = indexed override of an inherited parent event (cosmetic only — not an error)

---

## Useful Parent Actors

| Actor Type | Parent Name | When to Use |
|-----------|-------------|-------------|
| Unit | `GenericUnitStandard` | Default for all unit actors. Handles birth, death, selection, attack animations, etc. |
| Action | `GenericAttack` | Default for attack/ability action actors. Provides `Attack`, `Launch`, and `Impact` effect tokens. For beam/instant attacks set `Attack`; for missile attacks set `Launch` + `Impact`. Do **not** set all three. |
| Model | `ModelAddition` | Attach a model to another actor (e.g. a buff visual on a unit). |
| Model | `ModelAnimationStyleContinuous` | Persistent non-attached model where you control destruction (e.g. Psi Storm area). |
| Model | `ModelAnimationStyleOneShot` | Auto-cleans up after its animation finishes (e.g. explosions). Prefer over manual cleanup for one-shot VFX; for attacks use GenericAttack's built-in launch/impact models instead. |
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

### Action Actor Missile Defaults

For a `CActorAction` based on `GenericAttack`, a missile actor named exactly `<ActionActorId>Missile` is the default missile binding. In XML this may appear as an explicit `<Missile value="..."/>`, but the SC2 Editor can remove that field on save because the resolved preload token is already `##id##Missile`.

Treat that removal as normal when all of these are true:

- The action actor uses `parent="GenericAttack"` or another parent whose missile token already resolves to `##id##Missile`.
- The intended missile actor ID is exactly the action actor ID plus `Missile`.
- `PreloadAssetDB.txt` still shows the action actor resolving the missile slot through `##id##Missile`.

Do not generalize this to action actors that inherit a specific named missile from their parent. For example, an action actor based on `MarauderAttackBase` may inherit `MarauderAttackMissile`; if the custom projectile should be `<CustomActionId>Missile`, keep an explicit `<Missile value="..."/>` override.

### Texture Declarations and Inherited Swaps

`TextureDeclares` on a model map texture prefixes and filename adaptations to texture slots; they do not initiate a swap by themselves. Actor messages such as `TextureSelectById`, `TextureSelectByMatch`, and `TextureSelectBySlot` perform the selection. A copied model or skin can therefore appear corrupted when it retains declarations that inherited actor events target through campaign upgrades such as `DarkProtoss` or `PurifierProtoss`.

Removing a declaration can make the unwanted selection stop resolving, but it also disables any legitimate dynamic texture swap that needs that slot. Prefer removing or overriding the inherited actor events, or preventing their enabling upgrade, when the variant still needs dynamic texture selection. Omit the declarations only when the model is intentionally self-contained and no retained actor event should swap its textures.

Source and scope: the local catalog schema defines a declaration prefix as the reference used for a model's textures and defines the `TextureSelect*` actor messages separately. Void Campaign data supplies both the model declarations and upgrade-driven `TextureSelectById` events; this rule concerns dynamic texture selection, not ordinary textures embedded in an `.m3` model.

---

## Extracting Actors From Inactive XML

When recreating a unit from `XMLFromDependenciesWeDontUse/`, treat the primary `CActorUnit` as the presentation root. It commonly links the live model, build/placement model, portrait model, wireframe, group icon, unit icon, death models, voice sounds, footprint actor, attack animation events, morph/model-swap events, and hosted secondary actors.

Action actors (`CActorAction`) are the usual bridge from gameplay to visuals/audio. Match them by `effectAttack`, `effectLaunch`, or `effectImpact`, then copy only the launch/impact models and sounds they actually reference.

Be strict about co-op-specific actor terms. Events using `ValidatePlayer Is...CoopCommander`, `CommanderPrestige*`, mutator IDs, top-bar signals, or commander-only morph/revive hooks should normally be removed or rewritten for the project. Actor event terms are exact string references, so renamed units, weapons, abilities, effects, behaviors, validators, models, and sounds must be renamed consistently.

See [`unit-extraction-from-inactive-xml.md`](unit-extraction-from-inactive-xml.md) for the full reduced extraction workflow.

For authored examples, use the active dependency dumps and the project's own mod catalogs; do not rely on a separate local reference mod.

---

## Custom Parents

You can create your own parent actors to share event logic across multiple actors. Not recommended until you are comfortable with the event system — incorrect parents silently inherit broken behaviour.

---

## Actors vs Triggers

Both systems can accomplish similar things, but the correct choice depends on scope:

- **Actor events** — describe the general behaviour of a *type* of unit/effect (what a Marine always looks like, sounds like, animates like).
- **Triggers** — adjust *specific instances* of units or objects during gameplay (tint this particular Marine blue when a bonus objective completes).

When triggers need to drive actor changes, use `Send Actor Message` to push messages into the actor event system from trigger code.
