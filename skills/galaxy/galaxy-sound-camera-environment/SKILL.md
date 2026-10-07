---
name: galaxy-sound-camera-environment
description: Sound playback, music, camera movement and snapshots, cinematic mode, weather, lighting, and environment effects in Galaxy script. Use when playing sounds or music, moving or configuring the camera, entering cinematic mode, or controlling weather and lighting. Do not use for actor-level sound messages (use galaxy-actor-and-visuals).
---

## Loading Boundary

- **This sub-skill owns:** sound playback, music, camera movement/snapshots, cinematic mode, weather, lighting, and environment effects
- **Parent root skill (`sc2-galaxy-scripting`) owns:** project conventions, schema/syntax rules, source-of-truth, naming prefixes
- **Sibling sub-skills own:** `galaxy-actor-and-visuals` (actor-level sound messages), `galaxy-ui-and-dialogs` (HUD messages), `galaxy-players-and-alliances` (player camera)

# Galaxy Scripting – Sound, Camera & Environment

## Prerequisite

Load [`sc2-galaxy-scripting`](../../sc2-galaxy-scripting/SKILL.md) first for project-wide Galaxy syntax constraints (variable hoisting, no `++`/`--`, `while` not `for`, include paths without extensions), source-of-truth rules, modular script boundaries, and naming conventions (e.g. `libMy_` function prefix, `libMy_g_` global prefix). This sub-skill owns deep API reference only; project conventions live in the router skill.

## Key References

| Resource | URL |
|---|---|
| Native function reference | https://mapster.talv.space/galaxy/reference |
| Galaxy syntax definition | https://github.com/Talv/vscode-sc2-galaxy/blob/master/syntaxes/galaxy.json |
| **SC2-IngameDevTools (PRIMARY — #1 codebase)** | https://github.com/abrahamYG/SC2-IngameDevTools/tree/main/DevToolsIngame.SC2Mod/Script |
| SSF codebase (secondary style) | https://github.com/Cristall/SC2-SwarmSpecialForces/tree/main/SwarmSpecialForces.SC2Map/scripts |
| NativeLib camera helpers | `TriggerLibs/NativeLib.galaxy` — `libNtve_gf_SwooshCamera`, `libNtve_gf_CopyOfCameraObject`, `libNtve_gf_CinematicMode` |
| Camera Actions guide | https://s2editor-guides.readthedocs.io/New_Tutorials/03_Trigger_Editor/046_Camera_Actions/ |
| SC2Mapster wiki | https://sc2mapster.wiki.gg/ |

---

## Sound

### Playing sounds

```galaxy
// Play a sound by SoundLink (preferred — uses data-defined volumes)
sound lv_snd = SoundPlayForPlayer(
    SoundLink("UI_ButtonClick", -1),  // link name + index (-1 = any)
    lv_player
);

// Play at a 3D world position — single player
sound lv_snd2 = SoundPlayAtPointForPlayer(
    SoundLink("Zerg_Hydralisk_Death1", -1),
    lv_player,
    lv_point,
    0.0,    // min distance
    30.0,   // max distance
    100.0   // volume
);

// Play at a 3D world position — playergroup (use this for campaign / multi-player maps)
sound lv_snd3 = SoundPlayAtPoint(
    SoundLink("Zerg_Hydralisk_Death1", -1),
    PlayerGroupAll(),
    lv_point,
    0.0,    // min distance
    100.0,  // volume
    0.0     // fade-in duration
);

// Play attached to a unit (follows it) — playergroup form (6 params)
// See Sound – Advanced section for the correct signature

// Wait for sound to complete (blocks trigger thread)
SoundWait(lv_snd);

// Stop a playing sound
SoundStop(lv_snd, true);    // true = fade out
SoundStopAllTriggerSounds(true, PlayerGroupAll());
```

### Sound channels

```galaxy
// mute/unmute a channel
SoundChannelMute(c_soundChannelMusic, true, false);
SoundChannelMute(c_soundChannelSFX,   false, false);

// Set volume
SoundChannelSetVolume(c_soundChannelSFX, 80.0, 0.5);  // (channel, volume, duration)

// Common channel constants
c_soundChannelMusic
c_soundChannelSFX
c_soundChannelAmbient
c_soundChannelSpeech
c_soundChannelUI
```

### Music

```galaxy
// Play/stop music
libNtve_gf_PlayMusicForPlayer(lv_player, "Sound/Music/Terran/TerranMain1.ogg", 0, true);
SoundChannelMute(c_soundChannelMusic, false, false);
```

---

## Camera

### Panning the camera

```galaxy
// Pan to a point for a player
CameraPan(lv_player, lv_point, 0.0, -1, 10.0, false);
// (player, point, distance, yaw, pitch, sync)

// Snap instantly
CameraSetTarget(lv_player, lv_point, 0.0, -1, 10.0, false);

// Smoothed pan using camera object
CameraApply(lv_player, lv_camInfo, 2.0, false);
```

### Camera info / position

```galaxy
// Get current camera position
point lv_camPos = CameraGetTarget(lv_player);
fixed lv_yaw    = CameraGetYaw(lv_player);
fixed lv_dist   = CameraGetDistance(lv_player);

// Save and restore camera state
CameraSave(lv_player);
CameraRestore(lv_player, 0.0, false);
```

### Camera sweep / swoosh

```galaxy
// Swoosh camera — confirmed NativeLib function
// (player, startDistance, endDistance, targetPoint, duration)
libNtve_gf_SwooshCamera(lv_player, 10.0, 5.0, lv_point, 1.5);

// Copy of camera info object (useful for saving/restoring cinematic cameras)
camerainfo lv_camCopy = libNtve_gf_CopyOfCameraObject(lv_camInfo);

// NOTE: CameraShake is not exposed via NativeLib helpers.
// Use CameraShake() native directly if available in your build:
// CameraShake(lv_player, lv_intensity, lv_duration, lv_frequency);
```

---

## Environment – Fog

```galaxy
// Enable / disable fog
FogSetEnabled(true);

// Fog settings
FogSetDensity(0.3);
FogSetColor(Color(0.1, 0.1, 0.3));
FogSetFallOff(2.0);
FogSetStartHeight(0.0);
```

## Environment – Terrain / Water

```galaxy
// Terrain height at a point
fixed lv_h = WorldHeight(lv_p);

// Show/hide environment (terrain, water, sky)
EnvironmentShow(lv_player, true);

// Disable/enable no-fly zones dynamically
PathAddNoFlyZone(lv_region);
PathRemoveNoFlyZonesInRegion(lv_region);
```

---

## Leaderboard

The leaderboard is the default scoreboard panel.

```galaxy
// Create a leaderboard
LeaderboardCreate(PlayerGroupAll(), StringToText("Kills"), c_leaderboardSortNone,
    c_leaderboardValueUInt, "", Color(1.0,1.0,1.0));
int lv_board = LeaderboardLastCreated();

// Show / hide
libNtve_gf_ShowHideLeaderboard(lv_board, PlayerGroupAll(), true);

// Add a row item for each player
LeaderboardAddItem(lv_board, PlayerGroupAll(), lv_player, IntToText(lv_kills),
    Color(1.0,1.0,1.0), "", Color(1.0,1.0,1.0));

// Set value of a player's row
LeaderboardSetItemValue(lv_board, PlayerGroupAll(), lv_player, IntToText(42),
    Color(1.0,0.8,0.0));

// Sort
LeaderboardSortByValue(lv_board, c_leaderboardSortDescending, false);

// Destroy
BoardDestroy(lv_board);
```

---

## Objectives Panel

```galaxy
// Create objective
ObjectiveCreate(
    PlayerGroupAll(),
    StringToText("Destroy Enemy Base"),
    StringToText("Eliminate all enemy structures."),
    c_objectivePrimary
);
int lv_obj = ObjectiveLastCreated();

// Show/update state
ObjectiveShow(lv_obj, true, false);
ObjectiveSetState(lv_obj, c_objectiveStateCompleted);

// State constants
c_objectiveStateActive
c_objectiveStateCompleted
c_objectiveStateFailed

// Destroy
ObjectiveDestroy(lv_obj);
```

---

## Transmission (Portrait Speech)

```galaxy
// Play a scripted speech transmission
TransmissionSend(
    PlayerGroupAll(),               // who sees/hears it
    TransmissionSourceFromUnit(lv_unit),  // portrait
    StringToText("Speaker"),        // speaker name
    "",                             // sound link (or "" for none)
    StringToText("Your base is under attack!"),  // subtitle
    c_transmissionDurationAdd,      // how duration is applied
    3.0,                            // extra duration
    true                            // block until done
);

// Clear a specific transmission or all active transmissions
TransmissionClear(TransmissionLastSent());
TransmissionClearAll();
```

---

## Campaign Transmission Pattern (libCamp / libLbty)

WoL campaign maps use a specific pipeline for all transmissions. **Always** call `libLbty_PlayTransmissionCueSound` first to set appropriate audio channels, then `libCamp_gf_SendTransmissionCampaign` to play the actual speech.

```galaxy
// 0. Duck game audio (lower non-speech channels during transmissions)
libCamp_gf_SetAllSoundChannelVolumesCampaign(libNtve_ge_VolumeChannelMode_Speech);

// 1. Set audio channels to speech mode (required before each campaign transmission)
libLbty_gf_PlayTransmissionCueSound(PlayerGroupAll());

// 2. Send the transmission (blocks until it finishes when last param is true)
libCamp_gf_SendTransmissionCampaign(
    lv_unit,                         // portrait unit (or null for narrator)
    SoundLink("SoundName", -1),      // audio cue (-1 = any variation)
    c_transmissionDurationAdd,       // duration mode
    0.0,                             // extra seconds added
    true                             // wait (block) until done
);

// 3. After all transmissions, restore normal game audio
libCamp_gf_SetAllSoundChannelVolumesCampaign(libNtve_ge_VolumeChannelMode_Game);

// Simple non-portrait transmission (narrator/radio with no unit portrait)
libNtve_gf_SendTransmissionSimple(
    TransmissionSourceFromModel(null),
    c_invalidPortraitId,
    SoundLink("TransmissionSound", 0),
    0.0,
    c_transmissionDurationAdd,
    true
);

// Wait for a specific transmission to finish (non-blocking variant)
TransmissionWait(TransmissionLastSent(), 0.0);

// Tip text that shows in the upper-right of the screen
libNtve_gf_ShowTip(libNtve_gf_FormatTipTitle(StringExternal("Param/TipTitle/..."), 1), StringExternal("Param/TipBody/..."), PlayerGroupAll());
```

---

## Sound – Advanced

```galaxy
// Play sound attached to a unit (follows it; different param order from basic variant)
sound lv_snd = SoundPlayOnUnit(
    SoundLink("UnitDeath", -1),
    PlayerGroupAll(),    // player group (NOT single player like basic variant)
    lv_unit,
    0.0,                 // min distance
    100.0,               // volume
    0.0                  // fade-in duration
);

// Get the last played sound (for stopping/waiting)
sound lv_last = SoundLastPlayed();

// Stop with optional fade
SoundStop(lv_last, true);   // true = fade out

// Wait for a sound to finish (blocks trigger thread)
SoundWait(lv_last, 0.0, c_soundOffsetEnd);

// Time a Wait() to an exact sound length
Wait(SoundLengthSync(SoundLink("MySpeech", -1)), c_timeGame);
```

### Soundtrack (Background Music)

```galaxy
// Start, pause, and restore background music tracks
SoundtrackDefault(PlayerGroupAll(), c_soundtrackCategoryMusic, "TrackName",
    c_soundtrackCueAny, c_soundtrackIndexAny);
SoundtrackPlay(PlayerGroupAll(), c_soundtrackCategoryMusic, "TrackName",
    c_soundtrackCueAny, c_soundtrackIndexAny, false);

// Pause / resume music (e.g. during a cinematic)
SoundtrackPause(PlayerGroupAll(), c_soundtrackCategoryMusic, true,  false);  // pause
SoundtrackPause(PlayerGroupAll(), c_soundtrackCategoryMusic, false, false);  // resume
```

---

## Camera – Advanced

```galaxy
// Apply a named camera object from the editor (by ID)
CameraApplyInfo(lv_player, CameraInfoFromId(lv_camId), lv_duration, -1, 10, true);

// Pan with smooth approach
CameraPan(lv_player, lv_point, lv_distance, -1.0, 20.0, false);
// (player, point, distance, yaw, pitch, synchronize?)

// Lock camera input during scripted pan (prevents player moving camera)
CameraLockInput(lv_player, true);
// ... (camera movement) ...
CameraLockInput(lv_player, false);

// Save and restore camera position
CameraSave(lv_player);
CameraRestore(lv_player, 1.5);   // restore over duration (seconds)

// Swoosh camera (cinematic sweep)
libNtve_gf_SwooshCamera(lv_player, lv_startDist, lv_endDist, lv_targetPoint, lv_duration);
```

---

## Cinematic Mode & Sequences

Full cinematic pipeline used in campaign maps:

```galaxy
// 1. Enter cinematic mode (letterbox + disable UI)
libNtve_gf_CinematicMode(true, PlayerGroupAll(), 0.5);   // (enable, players, transition time)
// Alternate: use GlobalCinematicSetting if letter-boxing all players at once
libNtve_gf_GlobalCinematicSetting(true);

// 2. Set fullscreen mode (removes game HUD completely)
UISetMode(PlayerGroupAll(), c_uiModeFullscreen, 0.0);

// 3. Register a skip key (allows player to jump to end)
TriggerSkippableBegin(PlayerGroupAll(), 0, null, true, false);

// 4. Cinematic fade in/out
CinematicFade(true,  1.5, c_fadeStyleNormal, ColorWithAlpha(0, 0, 0, 0), 0.0, true);  // fade in from black
CinematicFade(false, 1.0, c_fadeStyleNormal, ColorWithAlpha(0, 0, 0, 0), 0.0, true);  // fade to black

// 5. Close the skippable block (must match every TriggerSkippableBegin)
TriggerSkippableEnd();

// 6. Restore HUD at end of cinematic
UISetMode(PlayerGroupAll(), c_uiModeGame, 0.0);
libNtve_gf_CinematicMode(false, PlayerGroupAll(), 0.5);
libNtve_gf_GlobalCinematicSetting(false);
```

---

## Mission Trigger Queue

The trigger queue serializes long-running cinematic/narrative sequences so they don't overlap.

```galaxy
// Enter / exit the queue (wraps around a cinematic trigger body)
TriggerQueueEnter();
// ... all the cinematic steps ...
TriggerQueueExit();

// Pause / resume queue (blocks next trigger from starting)
TriggerQueuePause(true);
TriggerQueuePause(false);

// Discard pending queue items
TriggerQueueClear(c_triggerQueueRemove);

// Check if the queue is empty (no pending triggers)
bool lv_done = TriggerQueueIsEmpty();
```

---

## Environment – Skybox / Background

```galaxy
// Set the skybox (background) for all players
GameSetBackground(c_backgroundFixed, "ShakurasSkyBox", 100.0);
// (mode, name, weight)

// Clear the skybox (restore default)
GameSetBackground(c_backgroundFixed, null, 100.0);

// Time of day (affects lighting/shadows)
GameTimeOfDaySet("08:00:00");
GameTimeOfDayPause(true);   // freeze time of day
GameTimeOfDayPause(false);  // unfreeze
```

---

## Video Recording (Briefings)

Used for in-engine cutscene recording passed directly to a video player (campaign briefings):

```galaxy
// Start recording a named video clip
MovieStartRecording("BriefingVideo");

// ... play the scene ...

// Stop recording
MovieStopRecording();
```

---

## Campaign Mission Completion

```galaxy
// Run the standard mission victory cinematic + score screen
libCamp_gf_RunMissionVictorySequence(lv_trigger);
```
