# In-game Transmission, Conversation and Dialog cases

[中文](trigger-dialogue-examples.md)
<!-- translation-source: wiki/reference/trigger-dialogue-examples.md; sha256: fc03d2f74ac127d0b2633c3bb0eb3a4d9eb5ddf6fd0ac23fd0b0d59436d9901c -->

This is an on-demand companion to [trigger knowledge](trigger-knowledge.en.md). Transmission is a mission voice/portrait/subtitle message; Conversation data binds story actors, lines and cameras; Dialog is interactive UI. A trigger name containing Conversation does not prove it uses Conversation data.

Twenty curated additions plus seven original categories provide 27 cases. [Case records](trigger-cases.json) preserve source paths/fingerprints/local calls/variables/resources/full closure counts. Behavior below comes from inspecting root events/actions and reachable GUI calls, not name matches. Originals are not drop-in minimal templates; old template static results do not extend to these additions, and no new Editor/game evidence is asserted.

## Queries

```text
python tools/sc2-trigger-query.py --ui-language en --reference examples transmissions --summary
python tools/sc2-trigger-query.py --ui-language en --reference examples conversations --case conversation-data --summary
python tools/sc2-trigger-query.py --ui-language en --reference examples dialogs --case dialog-add-button --max-nodes 50
python tools/sc2-trigger-query.py --ui-language en --reference examples cinematics --case cinematic-skip-key --summary
```

--case accepts case_id or exact element ID; no match fails. Display defaults to 200 nodes/resources/local-graph nodes; full validation is not truncated. --max-nodes 0 displays all. Start with summaries for complex stories. Add --target "`<target.SC2Map>`" --mods-dir "<Mods>" --campaigns-dir "<Campaigns>" before the subcommand for compatibility. --reference preserves incompatibility reasons without granting libraries to a target.

Source abbreviations are relative to the external Campaigns root:

| Code | Component |
|---|---|
| H | `liberty.sc2campaign/base.sc2maps/maps/campaign/thanson02.sc2map` |
| V | `liberty.sc2campaign/base.sc2maps/maps/campaign/tvalerian02a.sc2map` |
| S | `liberty.sc2campaign/base.sc2maps/maps/campaign/tstory01.sc2map` |
| A | `liberty.sc2campaign/base.sc2maps/maps/campaign/tarcade.sc2map` |
| Z | `swarm.sc2campaign/base.sc2maps/maps/campaign/swarm/zstorychar.sc2map` |

Each entry is in that component’s Triggers with empty Library; query indirect providers separately. A reference closure is not proof of target loading.

## Transmission: voice, portrait, subtitles and queues

| case_id | Source / Type / Id | Inspected behavior | Migration checks |
|---|---|---|---|
| queued-line | H / Trigger / FEB457C3 | ActionQueueAdd queues a campaign Transmission through Camp volume wrappers and Lbty alert sound. | Recipients, queue, sound, subtitles and portrait; closure requires Camp/Lbty/Ntve. |
| damage-alert | H / Trigger / 651BD0DC | Unit-damage event, conditions and state filter enemy introductions before queuing dialogue. | Replace unit/state conditions; check repeat suppression and related alerts; Camp/Lbty/Ntve. |
| day-night-warning | H / Trigger / 54EBCB95 | Mission-state branches choose day/night warning lines and enqueue them. | Verify call timing, day/night state and both resource branches; 30 seconds in a name does not establish a timer event. |
| stop-dialogue | S / FunctionDef / 6747CDBF | TransmissionClearAll, ConversationDataStop and actor messages to the game region. | Check clear-all scope, Conversation ID, actor reset and later state; stopping audio alone is insufficient. |
| portrait-create | S / FunctionDef / 3D41585C | Creates a briefing portrait from parameters, sets offscreen behavior and saves/returns its handle. | Model, player, layout, caching and destruction; this function itself sends no line. |

## Conversation: sequences, actors and cameras

| case_id | Source / Type / Id | Inspected behavior | Migration checks |
|---|---|---|---|
| sequential-lines | V / Trigger / B7578668 | Region-entry/conditions queue multiple Transmissions using TransmissionWait and TransmissionLastSent. | InitOff enable entry, region, sound order, players and queue; sequential Transmission, not ConversationDataRun. |
| character-callbacks | Z / Trigger / D0BDE235 | Registers character pre/post/camera callbacks through Swarm story utilities. | Character ID, callbacks, story state and camera; also needs 281DEC45, SwaC and Ntve. |
| conversation-data | S / Trigger / 531F9080 | Registers character units/cameras and runs Conversation data inside a skippable segment. | Conversation Catalog entry, map units, camera mappings, entry/cleanup; Ntve alone does not supply story assets. |
| conversation-camera | S / FunctionDef / 9A3FDB96 | Selects cameras from current line, sound duration and room/character helper calls. | Camera models/IDs, current Conversation context and character state; not a generic random-camera template. |

## Dialog: controls, clicks, layout and text

| case_id | Source / Type / Id | Inspected behavior | Migration checks |
|---|---|---|---|
| dialog-create | S / FunctionDef / DD616E37 | Checks an existing window, saves DialogLastCreated and adds buttons through helpers. | Dialog variables/button array/text/player/layout; official debug UI, use only its ownership pattern. |
| dialog-add-button | S / FunctionDef / A13A2608 | Sets text and size after DialogControlCreate. | Parent dialog/text/size; the caller immediately saves LastCreated control, since this action does not return a handle. |
| dialog-button-response | S / Trigger / 95B3EC65 | DialogControl event compares EventDialogControl with saved camera-button handles and branches. | Save control/player and branch mapping; replace debug camera behavior for story choices. |
| dialog-hide | S / FunctionDef / E083003A | Hides the existing room-cheat dialog. | Player visibility/reopen policy; hiding is not destruction. |
| dialog-close-event | S / Trigger / D33A6E05 | Filters the close button, hides the briefing dialog and restores surrounding story UI state. | Buttons/dialog/player/cleanup; original is a debug entry. |
| dialog-layout-update | S / FunctionDef / 8F17FF90 | Updates button placement/state and dialog position/size. | Actual layout variables, anchors, offsets, controls/player; remove debug-camera assumptions. |
| dialog-typewriter | A / FunctionDef / C8BD04E5 | Camp grid wrappers create controls and configure typewriter timing/style/alpha and display/destruction. | Text/style/duration/handles/player; Camp/Ntve closure. |

## Cinematic: setup, skip and restoration

| case_id | Source / Type / Id | Inspected behavior | Migration checks |
|---|---|---|---|
| cinematic-setup | V / Trigger / 11268265 | Fades, cinematic settings, saving camera/unit selection and entering the scene flow. | Player, playable area, pause/UI state, camera and scene worker. |
| cinematic-cleanup | V / Trigger / 3BEC60F6 | Cleans scene objects/effects, stops shake, restores camera/game state and continues the mission. | Restore pre-entry state, temporary units/behaviors, selection and continuation; UI alone is not enough. |
| cinematic-skip-key | A / Trigger / 225D2E39 | Key event stops multiple cinematic workers and transitions to the ending state. | Skip key/player, stop list, temporary objects and common cleanup; names do not make every entry skippable. |
| cinematic-skippable | A / Trigger / A97413B1 | TriggerSkippableBegin sequences control visibility/alpha and portrait actor messages. | Controls/portrait actors/animation messages and cleanup shared by normal completion/skip. |

Campaign-wrapped Transmission cases require Camp/Lbty; for a single native line query target-supported primitives rather than fabricate those libraries. Save Transmission/Conversation contexts before waits, including event unit/player/handles, so later events cannot overwrite LastSent/LastCreated. Check audio length, subtitle duration, wait mode and skipping separately against definitions and game behavior.

Minimal choices: create dialog → create/save buttons → show to recipients → filter saved control handle → save event player → commit branch → hide/destroy and clear state. Ordinary clicks and synchronized business state are separate; single-player debug originals are not co-op synchronization evidence.

Before cinematics save incoming camera/selection/pause/control/UI state. Normal/skip/interruption paths share cleanup: stop correct workers/dialogue, restore music/camera/selection/control, remove temporary objects, and avoid duplicate objectives/progress saves.

## Coverage and remaining target acceptance

| Requirement | Current sources | Target checks still required |
|---|---|---|
| Single/multiple lines, audio/portrait/subtitles/queues | Transmission/sequential cases | Resource pairing, volume, recipients and exclusion |
| Map events/repeat suppression/mission branches | damage-alert/day-night-warning/sequential-lines | Actual units/regions, cooldown and reset |
| Story data/callbacks/cameras | Conversation cases | Catalog/audio/model resources, map bindings, callback timing |
| Choices/close/reopen/layout/typewriter | Dialog cases | Window lifetime, text lengths, resolutions/input |
| Skip/interruption/restoration | stop-dialogue/Cinematic cases | Cleanup for every exit, load/repeat behavior |
| Timeout defaults/list inputs/branch merge | Compose target Timer/Dialog definitions; no curated original here | Click/timeout race, default, duplicate submission and recovery |
| Co-op independent UI/spectators/global synchronization | Native definitions only; originals do not establish multiplayer semantics | Player scope, shared state, sync/disconnect |
| Unvoiced subtitles/audio substitution/language switching | Compose target resources; not newly accepted templates | Anchors/actual locale assets, not whole-project translation |
| Load/restart/subtitle settings/fast-forward/missing resources | Requires project test scenarios | Handle/state restoration, setting effects and resource fallback |

Function existence does not establish implementation of extensions. Follow target → dependencies → complete definitions → cases → GUI → static → Editor → packaged runtime. New minimal templates need separate implementation and actual acceptance records.
