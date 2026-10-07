# AI Personality Waves to GUI Triggers

Use this workflow when an SC2 component map contains attack waves in the AI module (`CustomAI`) and the user wants equivalent editable Trigger Editor logic. The goal is behavioral migration, not merely copying generated Galaxy.

## Sources and Ownership

- Treat `CustomAI` as the source description of personality, source/target players, gather point, wave order, difficulty values, arrival/gather timing, create points, waypoints, target points, and final-wave repetition.
- Treat the map's `Triggers` and localized `TriggerStrings.txt` as the editable destination.
- Read generated `ai<ID>.galaxy` and `MapScript.galaxy` only to understand effective behavior and initialization. Never edit them; the Editor regenerates them.
- Distinguish the AI personality's attack-wave scheduler from campaign AI itself. Removing the personality must not accidentally remove `AICampaignStart` for its source player.

## Preflight

1. Resolve the exact `.SC2Map` component directory and confirm it is closed in the SC2 Editor.
2. Back up `Triggers`, `TriggerStrings.txt`, and, before final personality removal, `CustomAI`.
3. Parse `CustomAI` and record:
   - definition ID and source/target players;
   - default gather point and repeated-final-wave count;
   - each wave's unit IDs and four difficulty counts;
   - timing semantics (`Arrival`, `GatherTime`), creation mode/point, waypoint order, and target point;
   - any step trigger or custom data hook.
4. Inspect existing GUI attack-wave triggers in the same map and reuse their actual function IDs, parameter shapes, subfunction types, presets, and location-reference patterns. Do not invent IDs from names.

## Build the GUI Trigger

Create one normal eventless trigger per migrated personality. Locate the map's existing AI orchestration trigger (commonly named `Start AI`) and run each migrated trigger from there with a non-waiting GUI `Run Trigger` action. Do not add separate map-initialization events to migrated wave triggers.

- Preserve wave order and timing semantics. An arrival interval is not automatically equivalent to a raw wait; compare the generated personality code and neighboring mission triggers.
- Use the same source player, targets, gather point, creation point, waypoint sequence, and send mode.
- Add one local integer `aiPlayer` to every migrated main trigger and every `Attack Wave <id> Async` helper, initialize it once to the personality's source player, and reference it from every attacking-player GUI parameter in that trigger. Do not repeat the same attacking-player-number literal across attack-wave target, gather, waypoint, creation, use-group, and send actions. Keep the separate target player's `PlayerGroupSingle(1)` value distinct.
- Initialize a constant target player group once with the GUI equivalent of `PlayerGroupSingle(1)` and reuse it throughout the migrated trigger. Recursively check loops, condition branches, and asynchronous helper triggers. Remove clear-plus-add actions for an unchanged target at every nesting level; hoist the one assignment after the personality-stop action in a main trigger, but replace the pair in place after any leading wait in an asynchronous helper. Target/gather/waypoint settings are different: they configure the current wave being assembled and must be repeated for each new wave after a send.
- Express difficulty-dependent counts with the map's existing GUI difficulty-value function, then apply the configured attack-wave modifier to the resulting unit-count expression.
- For native `AIAttackWaveAddUnits4`, bind the four Editor fields by semantic difficulty to the actual parameter definitions: easy `24D9A2D7`, normal `B52CD455`, hard `AD14DE85`, expert/brutal `A166DBF3`. Do not assign values using XML parameter-reference order; confirm the mapping against the Editor field labels.
- For waves that use `CreateUnits`, create the units at the recorded point, place the resulting group into the attack wave, then set waypoints/target and send it.
- Reproduce the final-wave loop with a GUI repeat/while container. Every nested action must have the exact child-action `SubFunctionType` used by a known-good loop in that map. A missing subtype makes the Editor remove the action as an orphan and then report its parameters as invalid references.
- Give every new `Element` a fresh uppercase eight-hex ID. A function-call element may have only one parent reference; clone subtrees instead of sharing them.
- Add readable names for new trigger/local-variable elements to `TriggerStrings.txt` using the file's existing syntax and encoding.
- Resolve each personality's display name from `ObjectStrings.txt` key `AI/Name/<definition-id>` and name the main trigger `<personality name> Attack Waves` (for example, `Protoss P02 Attack Waves`). Treat a missing display name as an error; do not substitute the internal hexadecimal ID.
- Remove local variables that become unreferenced after script actions are replaced with GUI trees; in particular, do not leave an unused `createPoint` variable when all resulting point arguments are direct GUI point references.
- Use `scripts/convert_custom_ai_to_gui.py` for the standard conversion. Its target artifact must contain GUI `FunctionCall` and `Param` elements only for the migrated waves; never hand the user an intermediate `ScriptCode` migration.
- If the map already contains the legacy intermediate migration marked `Codex migrated AI personality`, convert that existing attack-wave trigger in place. Preserve every existing modifier input, remove a map-initialization event only from that migrated attack-wave trigger, rename it from the internal ID to the personality display name, and wire it into `Start AI`. Do not rebuild its wave body from `CustomAI` or apply quantity scaling again.
- Treat `convert_custom_ai_to_trigger_scripts.py` as a private compatibility stage and `convert_migrated_scripts_to_gui.py` as a repair helper. Do not invoke the compatibility stage directly on the user's map.

## Cutover Strategy

Use one of these explicit strategies; do not leave two live schedulers.

### Staged cutover (preferred for first Editor round-trip)

Keep the AI personality temporarily. At the beginning of the replacement trigger, call the map's GUI action that stops that personality's waves, then run the migrated GUI sequence. This permits comparison and avoids deleting generated personality support before the new trigger is Editor-accepted.

Mirror every other existing map action that stops the legacy personality with a GUI `Stop Trigger` action targeting the migrated wave trigger. Do not replace it with a player-wide attack-wave stop: unrelated scripted wave triggers may use the same player. Exclude the stop-personality action at the beginning of the migrated trigger itself, so the replacement does not stop itself.

### Final cleanup

After the GUI trigger is Editor-accepted and runtime-tested:

1. Delete the personality from the AI module in the Editor; do not manually delete `CustomAI` or `ai<ID>.galaxy` files.
2. Remove the replacement trigger's stop-personality action so it does not become an invalid reference.
3. Ensure the source player still receives the normal campaign-AI start action. Add it to map initialization if deleting the personality no longer generates it.
4. Save in the Editor and verify the generated map script contains the new trigger registration, the source player's campaign-AI start, and no calls to the removed personality.

Setting “repeat final wave” to zero disables only repetition; it does not disable the earlier personality waves. Closing the AI module window also does not disable the personality.

## Structural Validation

Before handing the map back:

- parse `Triggers` as XML;
- reject duplicate `Element/@Id` values;
- ensure every new FunctionCall is referenced exactly once by its parent;
- ensure nested loop actions have the map's valid child `SubFunctionType`;
- ensure every referenced parameter and function-call ID has a declaration;
- ensure migrated personality triggers have no events and the existing AI orchestration trigger runs each one exactly once without waiting;
- ensure the migrated trigger contains no `ScriptCode` (pure GUI is mandatory for this workflow);
- verify each generated call's direct `ParameterDef/@Library` matches its `FunctionDef/@Library`; LotV difficulty parameters must use `Library="Lotv"`, and `AttackWaveModifier` input `4D4D221F` must use the owning mod library (`67AA1763` in the default profile), never `Ntve`;
- run `scripts/wrap_attack_wave_counts.py <Triggers> --check` and confirm all supported count parameters are wrapped;
- compare wave count, order, unit compositions, difficulty values, delays, points, and repetition against `CustomAI`.
- Include personality-owned `Attack Wave <id> Async` helper triggers in that comparison, expanded where the main trigger runs them. `NoWait` wave units live in those helpers and are not missing merely because they are absent from the main trigger body.

Static validation does not prove Editor acceptance. Require one Editor open/save round-trip, check warnings, inspect regenerated `MapScript.galaxy`, and test at least two difficulty settings. During staged cutover, also verify that only one scheduler sends waves.
