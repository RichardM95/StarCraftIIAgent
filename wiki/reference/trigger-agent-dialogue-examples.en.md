# Trigger conversations between users and the agent

[中文](trigger-agent-dialogue-examples.md)
<!-- translation-source: wiki/reference/trigger-agent-dialogue-examples.md; sha256: 6093d34d97526b3a10dbf59a30a1b295cb6a09177bfa771279c2f0db88ed472b -->

These examples show requests, actions and handoff expectations. They are illustrative, not records of completed work or new acceptance evidence. Replace paths, characters, units, regions, text and progress entry points with actual inputs. Query the current target for function and parameter IDs. Follow [trigger knowledge](trigger-knowledge.en.md); see [in-game dialogue mechanisms](trigger-dialogue-examples.en.md).

The agent reads facts available in configuration and source, asks for missing inputs that affect implementation, and completes authorized edits and checks. Its reply describes behavior, evidence and remaining acceptance. The notes below are guidance, not fixed response scripts.

## Targets, dependencies and reference research

| Scenario | User request | Agent actions and response |
|---|---|---|
| 01 Research without selecting a project | “Find how the official maps sequence dialogue. Don't edit any map.” | Use explicit reference queries and inspect cases. Return provenance, calls and resource needs as reference_only; do not initialize a project. |
| 02 Explicit map edit | “Add dialogue on entering the base in `<map.SC2Map>`; here are the Mods/Campaigns directories.” | Resolve the explicit target; check region and dialogue assets, then edit its actual Triggers. Identify specific missing objects. |
| 03 Configured project | “Add an exported GUI action to the current mod to display a mission hint.” | Resolve the editing source from source_mode; confirm library identity/loading, implement the action and show the map call. |
| 04 Initialization requested | “Select this primary Components mod: `<primary.SC2Mod>`.” | Run initialization directly, verify identity/source, and continue authorized work. Do not ask for manual JSON editing. |
| 05 Liberty dependencies only | “This map only loads Wings of Liberty; use this LotV function.” | Query root definitions and indirect dependencies. If unavailable, find a target-supported alternative; report incompatibility without adding dependencies silently. |
| 06 Dependency change authorized | “I've added the required component in the Editor. Check again.” | Read updated declarations, registrations and fingerprints; confirm the complete chain rather than reuse old availability. |
| 07 Only a library file exists | “VoidLib is on disk. Why can't I use it?” | Distinguish component loading from library registration; identify missing declarations/references. Reference research can continue. |
| 08 Missing network dependency | “Can we ignore this Battle.net dependency?” | Identify the exact reference and affected chain. Explicit reference research is possible; target checks still fail. Ignoring it does not confirm availability. |
| 09 Map versus mod scope | “Can the mod call this map-local function directly?” | Check each scope. Map-local definitions are unavailable to the mod; implement a shared mod GUI action called by the map if needed. |
| 10 Conflicting providers | “Two versions have the same Library/Id. Which one should I use?” | Compare loaded providers/fingerprints and report conflicts. A reference version does not replace an active source; unresolved ambiguity blocks checks. |

## Full definitions and official cases

| Scenario | User request | Agent actions and response |
|---|---|---|
| 11 Search by localized name | “Show all parameters of ‘Send Transmission’.” | Search available definitions by English, Chinese and internal names. Disambiguate using intent/signatures; return the exact reference and XML. |
| 12 Exact element | “Explain `Ntve:FunctionDef:3E151A17`, including defaults and return value.” | Query full parameter IDs, types, order, default structure, presets and flags. Confirm target availability; do not invent a signature from memory. |
| 13 Default-value assumption | “Can I omit these Param nodes because defaults exist?” | Check definition/call requirements. Defaults are definition facts; explicitly bind required GUI parameters rather than infer omission permission. |
| 14 Cross-library parameters | “The action resolves but its ParamDef doesn't.” | Follow each parameter's Library/Type/Id to the missing library or wrong ownership. Do not change its Library to the action's just to silence errors. |
| 15 Sub-action disappears | “The If action's Then branch disappears after saving.” | Check allowed SubFunctionType and child references; repair GUI structure. Editor save behavior needs actual before/after evidence; static success alone does not prove it fixed. |
| 16 Native case from a Void map | “Can this Void map timer be used in a Liberty map?” | Compare the real reference closure with target libraries; the source campaign's age alone is not exclusion evidence. Migrate map objects, strings, variables and local IDs separately. |
| 17 Oversized example | “I only need a button event, not the whole story UI.” | Select dialog-button-response / dialog-add-button, inspect event/handles, and replace debug behavior instead of importing the entire story flow. |
| 18 Browse all cases | “List dialogue, dialogs, cameras and skip examples.” | Give four categories with summaries/case_id, dependencies and resources. Expand exact calls on demand; distinguish curated originals from unverified extensions. |

## Seven basic trigger mechanisms

| Scenario | User request | Agent actions and response |
|---|---|---|
| 19 Initialization | “Initialize the mod once when the map starts.” | Check existing initialization, exported GUI actions and order to prevent duplicate entries. Confirm Bank/project identity from source. |
| 20 Objectives | “Complete this objective after three buildings are destroyed.” | Query objects/create/complete actions; save the objective handle immediately. Count/filter events without completing a different LastCreated objective. |
| 21 Victory and defeat | “Lose when the base is destroyed; win when the enemy is eliminated.” | Inspect units, players, settlement/progress saving and GUI conditions. Check both paths; a generic end-game action does not replace campaign progression. |
| 22 Regions | “Only player 1's hero entering this region should trigger it.” | Resolve region/hero/player filters and one-shot versus repeat behavior. Request an Editor-created region if missing; do not guess its ID. |
| 23 Timers | “Start the mission after two minutes and show a countdown.” | Create/save a timer; use that same object for start, display and expiry events. Check timing/repeat policy; manage window and timer separately. |
| 24 Attack waves | “Send units to the base every three minutes, with more units on higher difficulties.” | Check AI startup, groups, destinations and scheduling. Query actual difficulty/wave definitions, prefer editable GUI and keep generated Galaxy read-only. |
| 25 Difficulty branches | “Give five units on Normal and eight on Hard.” | Query actual presets/ValueId and branch parameters. Do not permanently equate a sample numeric value 3 with a difficulty label. |

## In-game dialogue and interaction

| Scenario | User request | Agent actions and response |
|---|---|---|
| 26 Voiced line | “Play a voice line with portrait and subtitles.” | Confirm recipients, sound, portrait and subtitle assets; query the target send definition. Check actual Camp/Lbty dependencies if campaign wrappers are needed. |
| 27 Three sequential lines | “A, B, then A should speak, without overlapping.” | Inspect sequential-lines/wait definitions; immediately save each send handle. Plan queues/interruption and prevent other dialogue replacing LastSent. |
| 28 Unvoiced dialogue | “No audio yet; implement text and portrait first.” | Query supported text/portrait operations, duration and closing. Do not invent sounds or treat static checks as visual acceptance. |
| 29 Conversation data | “Use this existing Conversation; its characters and cameras are already in the map.” | Query Catalog entry and actor/camera bindings, register actual objects then run it. Identify missing data/objects rather than copy only Run. |
| 30 Two choices | “Show two buttons leading to different objectives.” | Save dialog/button handles; filter by button/player, prevent duplicate submissions and clean up. Store objective handles separately from player choices. |
| 31 Timeout default | “Choose the first option if nobody clicks within ten seconds.” | Share a single commit path between click and timer; check uncommitted state before one branch/cleanup. This combination is not a verified original; implement and test it. |
| 32 One-shot and cooldown | “Say this hint once, and that one at most every 30 seconds.” | Check state/cooldown before the action, update state before queuing; define cleanup/restart/load behavior. |
| 33 Mission-dependent lines | “Clicking this character should give different lines before and after the objective.” | Read the confirmed mission-state entry and select resources. If absent, propose concrete state choices for confirmation. |
| 34 Skippable sequence | “ESC should skip the dialogue and continue the mission.” | Query actual key/skip definitions. Share cleanup across normal/skip exits; stop the correct worker, restore camera/control/UI and prevent duplicate advancement. |
| 35 Independent co-op choices | “Each co-op player should choose a reward separately.” | Separate individual UI/results from shared mission state; check player/control definitions, store by player and plan synchronization tests. Single-player originals do not prove multiplayer correctness. |
| 36 Reopen and layout | “Let players reopen the window, and keep long text inside it.” | Define hide/destroy policy, handle reuse, layout and text scope. Check actual fonts, resolution and input; static checks cover structure/references only. |

## Diagnosis, migration and handoff

| Scenario | User request | Agent actions and response |
|---|---|---|
| 37 ID collision | “Import this GUI fragment into an existing map.” | Determine its local closure, remap declaration/reference IDs and synchronize TriggerStrings/GameStrings. Set mod Library ownership separately. |
| 38 Stale reference index | “I replaced the official libraries, but results still look old.” | Check inventory/fingerprints; rebuild old/stale indexes from original external roots. Recheck changed case provenance and tags. |
| 39 Truncated display | “Only 50 nodes are shown. Did you check just 50?” | Explain display limits versus full checks; report totals and hidden errors. Limited output is not complete availability evidence. |
| 40 Editor changes | “Static checks passed, but an action vanished after saving.” | Preserve before/after source/generated code, compare calls/parameters, and record Editor version/reproduction. Do not claim Editor accepted before verification. |
| 41 Stuck in game | “Camera and controls don't return after the dialogue.” | Inspect normal/skip/interruption cleanup, pause/UI state, wait context and logs. Repair editable source and provide specific reproduction steps. |
| 42 Skip dependency checks | “Just check the primary mod and ignore dependencies.” | Explain that Catalog investigation may narrow scope, but trigger availability needs complete active dependencies. Identify exact gaps; incomplete dependencies cannot pass acceptance. |
| 43 Editor evidence | “I reloaded and saved it; here are the before/after files and version.” | Check retained GUI objects/generated calls before recording Editor accepted. Runtime acceptance still requires game evidence. |
| 44 Packaged runtime evidence | “Normal, skip and repeated triggers worked in the package; here are logs and video.” | Check version, packaging and coverage; record observed outcomes per scenario. Only supported scenarios reach packaged runtime passed. |

## Two complete conversations

### Research first when no target exists

**User:** “Give me an example with a portrait, three lines and two final choices. Don't edit a map yet.”

**Agent:** “I'll query sequential Transmission and Dialog button events separately, then outline how to combine them and which inputs are required. Without a target, the results are references.”

**User:** “Use only ordinary native libraries, no campaign wrappers.”

**Agent actions:** Query Ntve send/wait/dialog/control definitions; explicitly exclude Camp/Lbty calls. Provide GUI orchestration and player/sound/text/portrait/handle inputs plus target validation steps. Without generated and checked XML, label it a design, not a statically validated template.

**Completion reply:** “The native design is documented; the official sequential dialogue is a mechanism reference. Actual map evidence is still needed for loading, resource replacement and XML checks.” Include actual query sources.

### Complete authorized work before handoff

**User:** “In `<target.SC2Map>`, add a one-shot line when player 1 enters `<region>`. Here are the sound, subtitle and portrait assets; use loaded libraries only.”

**Agent actions:** Resolve target/dependencies, check region/resources, query full definitions, write GUI/string anchors and one-shot state, then run target checks. Complete these authorized actions when inputs are available.

**Completion reply template:** “Added the one-shot region-entry line. Recipient, state variable and resource references were checked; target checks reached `<actual-status>`. Follow the attached steps to test sound/portrait/subtitles and repeated entry.”

**User:** “The Editor saved correctly, but subtitles don't appear in the packaged game.”

**Agent actions:** Record the Editor gate supported by save evidence. Investigate subtitle settings, anchors, player scope and resources; update the current issue and runtime reproduction. Preserve the failed/unverified packaged result instead of carrying static success forward.
