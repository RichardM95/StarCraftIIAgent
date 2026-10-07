---
name: galaxy-actor-and-visuals
description: Actors, visual effects, model attachments, animations, and tint/scale/opacity control in Galaxy script. Use when working with ActorSend, AttachModelToUnit, PlayAnimation, SetTintColor, SetScale, SetOpacity, doodad visibility, or any purely visual/audio actor operation. Do not use for unit gameplay logic or sound triggers (use their dedicated skills).
---

## Loading Boundary

- **This sub-skill owns:** actors, visual effects, model attachments, animations, tint/scale/opacity control, and doodad visibility in Galaxy script
- **Parent root skill (`sc2-galaxy-scripting`) owns:** project conventions, schema/syntax rules, source-of-truth, naming prefixes
- **Sibling sub-skills own:** `galaxy-sound-camera-environment` (sound/camera), `galaxy-ui-and-dialogs` (UI), `sc2data-actors-visuals` (CActor* XML schema)

# Galaxy Scripting – Actors & Visual Effects

## Prerequisite

Load [`sc2-galaxy-scripting`](../../sc2-galaxy-scripting/SKILL.md) first for project-wide Galaxy syntax constraints (variable hoisting, no `++`/`--`, `while` not `for`, include paths without extensions), source-of-truth rules, modular script boundaries, and naming conventions (e.g. `libMy_` function prefix, `libMy_g_` global prefix). This sub-skill owns deep API reference only; project conventions live in the router skill.

## Key References

| Resource | URL |
|---|---|
| Native function reference | https://mapster.talv.space/galaxy/reference |
| Galaxy syntax definition | https://github.com/Talv/vscode-sc2-galaxy/blob/master/syntaxes/galaxy.json |
| **SC2-IngameDevTools (PRIMARY — #1 codebase)** | https://github.com/abrahamYG/SC2-IngameDevTools/tree/main/DevToolsIngame.SC2Mod/Script |
| SSF codebase (secondary style) | https://github.com/Cristall/SC2-SwarmSpecialForces/tree/main/SwarmSpecialForces.SC2Map/scripts |
| NativeLib actor helpers | `TriggerLibs/NativeLib.galaxy` — all `libNtve_gf_Attach*`, `libNtve_gf_Create*`, `libNtve_gf_PlayAnimation*`, `libNtve_gf_Set*`, `libNtve_gf_SendActorMessage*` functions |
| SC2 editor guides | https://s2editor-guides.readthedocs.io |
| SC2Mapster wiki | https://sc2mapster.wiki.gg/ |
| Actor Events (wiki) | https://sc2mapster.wiki.gg/wiki/Data/Actors/Events |
| Actor Terms (wiki) | https://sc2mapster.wiki.gg/wiki/Data/Actors/Terms |

---

## What is an Actor?

An **Actor** is the visual/audio representation of something in-game — a model, an attachment, a beam effect, etc. Actors are separate from the simulation (units, regions) and communicate via **messages**.

Most visual scripting goes through `ActorSend` (send a message to an actor) or by spawning actors directly with `ActorCreate`.

---

## Actor Types and Handles

```galaxy
actor lv_a;            // model/effect actor
actorscope lv_scope;   // actor scope (groups related actors)
```

---

## Creating Actors

```galaxy
// Spawn a named actor within a scope (name defined in data)
// ActorCreate(actorscope, actorName, content1, content2, content3)
lv_a = ActorCreate(lv_scope, "MyEffectActor", "", "", "");

// Simple: create model actor at a point (returns actor)
lv_a = libNtve_gf_CreateModelAtPoint(
    "Assets\\Units\\Zerg\\Hydralisk\\Hydralisk.m3",
    lv_point
);

// Attach model to unit — 3 params: (unit, modelPath, attachPoint)
lv_a = libNtve_gf_AttachModelToUnit(
    lv_unit,
    "Assets\\Units\\Zerg\\Hydralisk\\Hydralisk.m3",
    "Chest"     // attach point
);

// Attach model and inherit unit visibility (same params, separate function)
lv_a = libNtve_gf_AttachModelToUnitInheritVisibility(
    lv_unit,
    "Assets\\Effects\\SomeGlow.m3",
    "Origin"
);

// Attach an existing named actor (from data) to a unit at an attach point
// (unit, actorName, attachPoint) — returns actor
lv_a = libNtve_gf_AttachActorToUnit(lv_unit, "TalkIcon",         "Ref_Origin");
lv_a = libNtve_gf_AttachActorToUnit(lv_unit, "BriefingUnitSelectRed", "Ref_Center");

// Attach named actor from data to another actor
lv_a = libNtve_gf_AttachActorToActor(lv_hostingActor, "SomeEffectActor", "Ref_Center");
// (hostingActor, attachingActorName, attachPoint)

// Get the last actor created by any actor operation
actor lv_last = libNtve_gf_ActorLastCreated();
// Thread-safe variant (uses LastCreatedSend)
actor lv_lastSend = libNtve_gf_ActorLastCreatedSend();

// Get the last created actor scope
actorscope lv_scope2 = libNtve_gf_ActorScopeLastCreated();
ActorScopeKill(lv_scope2);   // destroy all actors in the scope

// Attach model to another actor (actor as host)
lv_a = libNtve_gf_AttachModelToActor2(
    lv_hostActor,
    "Assets\\Effects\\SomeEffect.m3",
    "Origin"
);
// (hostActor, modelPath, attachPoint)

// Create named actor (from data) at a point
lv_a = libNtve_gf_CreateActorAtPoint("SomeActorName", lv_point);
// Create a model (raw path) at a point
lv_a = libNtve_gf_CreateModelAtPoint("Assets\\Effects\\Explosion.m3", lv_point);

// Scope — ActorScopeCreate takes ONE optional actor name, not two params
lv_scope = ActorScopeCreate("");           // empty scope
lv_scope = libNtve_gf_ActorScopeLastCreated();
actorscope lv_scopeSend = libNtve_gf_ActorScopeLastCreatedSend();

// Get the main visible actor of a unit (use this instead of ActorFrom(unit))
actor lv_unitActor = libNtve_gf_MainActorofUnit(lv_unit);
```

---

## Sending Actor Messages

Messages control everything about an actor — animations, tints, scale, visibility, etc.

```galaxy
// Send a constructed message string to an actor
ActorSend(lv_a, "SetTintColor {1,0,0,1}");
ActorSend(lv_a, "SetScale 0.800000");   // scale by string

// Using library message constructors:
ActorSend(lv_a, libNtve_gf_SetTintColor(1.0, 0.0, 0.0, 1.0));
ActorSend(lv_a, libNtve_gf_SetScale("1.5 1.5 1.5"));
ActorSend(lv_a, libNtve_gf_SetVisibility("Hide"));
ActorSend(lv_a, libNtve_gf_SetVisibility("Show"));

// Destroy actor
ActorSend(lv_a, "Destroy");

// Team color
ActorSend(lv_a, libNtve_gf_SetTeamColor(lv_player));

// Send to a unit's main actor
ActorSendTo(ActorFrom(lv_unit), libNtve_gf_SetTintColor(1.0, 0.5, 0.5, 1.0));

// Send actor message to a unit (shortcut — targets the unit’s own actor)
libNtve_gf_SendActorMessageToUnit(lv_unit, "AnimGroupApply Stand,Victory");
libNtve_gf_SendActorMessageToUnit(lv_unit, "StatusSet MarinePortrait 7");
```

### Common message constructors

| Message | Constructor | Effect |
|---|---|---|
| Set tint | `libNtve_gf_SetTintColor(r,g,b,a)` | Color tint |
| Set scale | `libNtve_gf_SetScale("x y z")` | Scale model |
| Set visibility | `libNtve_gf_SetVisibility("Show"/"Hide")` | Show/hide |
| Set bearings | `libNtve_gf_SetBearings(x,y,z,fx,fy,fz)` | Position+facing |
| Signal | `libNtve_gf_Signal("EventName")` | Trigger data event |
| Play animation | `MakeMsgAnimPlay("Walk Stand Birth Death",flags,blend,0,0)` | Animation |

---

## Animations

```galaxy
// Play animation on an ACTOR (not unit!) — 5 params:
// (actor, identifier/track, animName, flags, blendTime)
libNtve_gf_PlayAnimation(lv_unitActor, "Attack", "Attack", c_animFlagPlayForever, 0.0);
// Get the actor first:
actor lv_unitActor = libNtve_gf_MainActorofUnit(lv_unit);
libNtve_gf_PlayAnimation(lv_unitActor, c_animNameDefault, "Stand Work", c_animFlagPlayForever, 0.0);

// Clear animation on an ACTOR — (actor, identifier/track)
libNtve_gf_ClearAnimation(lv_unitActor, c_animNameDefault);

// Using raw actor messages with bracket animations:
ActorSend(lv_a, MakeMsgAnimBracketStart(
    "Walk",                   // opening anim
    "Stand",                  // content anim
    "",                       // closing anim
    "WalkBracket",            // bracket name
    c_animFlagPlayForever,    // flags
    c_animTimeVariantAsAutomatic,  // time variant
    0.0                       // time value
));
ActorSend(lv_a, MakeMsgAnimBracketStop("WalkBracket", c_animGroupApplyFlagInstant, 0.0));

// Simple anim message via MakeMsgAnimPlay:
ActorSend(lv_a, MakeMsgAnimPlay(
    "Attack",                 // anim props (space-separated hints)
    c_animFlagPlayForever,    // flags
    c_animTimeVariantAsAutomatic,
    0.0,                      // time value
    -1                        // variation (-1 = random)
));

// Turn on/off animation properties — (actor, propName) — 2 params each!
libNtve_gf_TurnAnimationPropertiesOn(lv_unitActor, "Charred");
libNtve_gf_TurnAnimationPropertiesOff(lv_unitActor, "Charred");
// Variant with blend-in / blend-out animations:
libNtve_gf_TurnAnimationPropertiesOnWithBlendInOut(
    lv_unitActor, "Charred", "Death", "Birth"
);
libNtve_gf_TurnAllAnimationPropertiesOff(lv_unitActor);

// Set animation completion / duration / time
libNtve_gf_SetAnimationCompletion(lv_unitActor, c_animNameDefault, 0.5);  // 50%
libNtve_gf_SetAnimationDuration(lv_unitActor, c_animNameDefault, 2.0);
libNtve_gf_SetAnimationTimeScale(lv_unitActor, c_animNameDefault, 2.0);   // 2x speed
libNtve_gf_SetAnimationTime(lv_unitActor, c_animNameDefault, 1.0, false); // (actor, id, time, scaled)

// On doodads in region — 6 params:
// (region, doodadType, identifier, animName, flags, blendTime)
libNtve_gf_PlayAnimationOnDoodadsInRegion(
    lv_region,
    "",                    // empty = all doodad types in region
    c_animNameDefault,     // animation track identifier
    "Stand Work",          // animation name
    c_animFlagPlayForever, // flags
    c_animTimeDefault      // blend time
);
libNtve_gf_ClearAnimationOnDoodadsInRegion(lv_region, "", c_animNameDefault);
libNtve_gf_KillDoodadsInRegion(lv_region);

// Wait for an animation length — AnimLengthQueryByName has 3 params:
// (actor, animName, scaledTime)
AnimLengthQueryByName(lv_unitActor, "Attack", false);
AnimLengthQueryWait();   // NO args — waits for the query to complete
generichandle lv_qHandle = AnimLengthQueryLastCreated();
fixed lv_len = AnimLengthSync(lv_qHandle);
fixed lv_rem = AnimLengthRemainingSync(lv_qHandle);
```

---

## Actor Texture / Appearance

```galaxy
// Swap out a texture group
ActorSend(lv_a, libNtve_gf_TextureGroupApply("ZergPlayerColor"));
ActorSend(lv_a, libNtve_gf_TextureGroupRemove("ZergPlayerColor"));

// Swap model — (modelName, variation)
ActorSend(lv_a, libNtve_gf_ModelSwap("NewModelName", 0));

// Select texture by ID
ActorSend(lv_a, libNtve_gf_TextureSelectByID("TextureId"));

// Apply texture group globally (all actors)
ActorTextureGroupApplyGlobal("TextureGroupName");
ActorTextureGroupRemoveGlobal("TextureGroupName");

// Kill (destroy) a model actor
libNtve_gf_KillModel(lv_a);

// Make a model face an angle
libNtve_gf_MakeModelFaceAngle(lv_a, 90.0);  // (actor, angleDegrees)
```

---

## Cinematic Fade & Cinematic Mode

```galaxy
// Fade to black (and back)
CinematicFade(true, 1.5, c_fadeStyleLinear, Color(0.0, 0.0, 0.0), 1.0, PlayerGroupAll());
// (fadeIn, duration, style, color, alpha, players)

CinematicFade(false, 1.0, c_fadeStyleLinear, Color(0.0, 0.0, 0.0), 1.0, PlayerGroupAll());

// Full cinematic mode — correct param order: (bool onOff, playergroup, fixed duration)
libNtve_gf_CinematicMode(true, PlayerGroupAll(), 0.0);   // enter cinematic mode
libNtve_gf_CinematicMode(false, PlayerGroupAll(), 1.0);  // exit cinematic mode

// Check if a player is in cinematic mode
bool lv_inCine = libNtve_gf_PlayerInCinematicMode(lv_player);

// Global cinematic mode (affects all players, fixed seed)
libNtve_gf_GlobalCinematicSetting(true);
libNtve_gf_GlobalCinematicSettingFixedSeedOnOff(true, true);

// Cinematic transition style
libNtve_gf_SetCinematicTransitionStyle(libNtve_ge_CinematicTransitionStyle_Mission);
// Constants: libNtve_ge_CinematicTransitionStyle_Mission, _Story

// Swoosh camera to a location (player, dist1, dist2, point, duration)
libNtve_gf_SwooshCamera(lv_player, 10.0, 5.0, lv_point, 1.0);
```

---

## Doodads

```galaxy
// Show/hide doodads by region — (bool showHide, region, string doodadType)
// doodadType is the doodad type string; empty string = all doodads
libNtve_gf_ShowHideDoodadsInRegion(true,  lv_region, "");  // show all doodads
libNtve_gf_ShowHideDoodadsInRegion(false, lv_region, "SomeDoodadType");  // hide specific type
// NOTE: NO playergroup parameter — this affects doodads globally on the map

// Remove doodads by type in region
libNtve_gf_RemoveDoodadsinRegion(lv_region, "");  // (region, doodadType)

// Remove death models from a region (cleanup)
libNtve_gf_RemoveDeathModelsinRegion(lv_region);
libNtve_gf_RemoveDeathModelsinRegionImmediately(lv_region);

// Send actor message to all actors in a game region
libNtve_gf_SendActorMessageToGameRegion(lv_region, "Destroy");
// With class/term filters:
libNtve_gf_SendActorMessageToGameRegionWithFilters(
    lv_region,
    c_actorIntersectAgainstCenter,  // intersect type
    "Destroy",                      // message
    "",                             // class filters
    ""                              // terms
);
```

---

## Portrait

```galaxy
// Get the game portrait (bottom-left)
portrait lv_p = PortraitGetGame();

// Set portrait to a unit
PortraitSetUnit(lv_p, lv_unit, 0.0, "", false);

// Portrait actors are accessed via ActorScopeFromPortrait / ActorFromPortrait:
actorscope lv_pScope = ActorScopeFromPortrait(lv_portraitIndex);
actor      lv_pActor = ActorFromPortrait(lv_portraitIndex);
```

## Actor Refs & Scope Access

```galaxy
// Get a named actor within a scope or actor
actor lv_child = ActorRefGet(lv_a, "::Main");
actor lv_child2 = ActorScopeRefGet(lv_scope, "::Main");

// Set a named ref
ActorRefSet(lv_a, "::Target", lv_targetActor);
ActorScopeRefSet(lv_scope, "::Target", lv_targetActor);

// Get scope from a unit
actorscope lv_unitScope = ActorScopeFromUnit(lv_unit);

// Get actor from a scope by name
actor lv_named = ActorFromScope(lv_scope, "SomeActorInScope");

// Get actor from parent actor by name
actor lv_sub = ActorFromActor(lv_a, "SubActorName");
```
