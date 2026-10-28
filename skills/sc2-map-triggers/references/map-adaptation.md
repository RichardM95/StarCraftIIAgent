# GUI behavior when adapting a campaign map

Use when adding mission objects, replacing a side objective or organizing a large inherited GUI tree. Follow the [entry skill](../SKILL.md) for dependency-aware function signatures and generated-source boundaries. The [terrain composition workflow](../../sc2-terrain-editing/references/map-adaptation.md) owns physical layout and occupancy.

## Preserve the inherited story

Identify the original initialization, main cutoff, defeat, cinematic setup/cleanup and skip paths. Bind placed objects by their actual typed IDs. Keep original trigger identities and references when replacing only a sidequest; replacing the whole tree loses more than the visible objective logic.

Inspect both event-driven and explicit execution paths to retired triggers. Disabling an event trigger does not establish that an explicit execution can no longer run its body. Remove or redirect conflicting active calls and disconnected expression nodes deliberately, keeping a recoverable record. Inspect generic loops too: the local rescue work found an inherited civilian cheer loop issuing stop orders that could compete with new movement.

**Integration check:** the original story still has its entry/exit and skip paths, replaced rewards cannot also fire, and the added workers stop at the defined mission cutoff.

## Model physical interactions as explicit states

For civilians that must walk to equipment, inspect owner, pause, selectable/commandable state, movement ability, current order, distance and actual route. A change to player color alone is not a completed rescue. A selectable unit may still be paused. Creating a new unit at a distance can conceal a failed movement path.

Keep the original unit until its replacement has actually been created. On success, remove that original within the same action sequence, without a wait between the two operations. Validate a live newly created handle rather than accepting a stale LastCreated value. Keep the original recoverable when creation fails.

When an equipment vehicle represents boarding, hiding the civilian and deleting it have different recovery consequences. A useful implementation retains hidden originals and per-person roles until the declared boarding condition is met; it then destroys the equipment vehicle and creates the corresponding recruits. Failed replacements restore their originals and retry without duplication. Bind escort and equipment vehicles independently even if their types or models match.

For repeated sites, track each site's state and update one aggregate objective exactly once per completed site. Decide explicitly whether partial losses complete a site and what an all-dead site means; do not inherit the local campaign's six-site policy by accident. Keep these amounts and success rules in the project design.

**Behavior check:** cover partial arrival, obstruction/recovery, casualties, failed creation, repeat execution, save/load and mission cutoff. GUI state execution can verify branches and counters; actual movement still requires the game.

## Voice is a resource and a queue

Inspect a real Sound/Conversation entry and its subtitle, speaker and portrait. A transmission constructed only from a portrait and new text is not voiced dialogue. Reuse a compatible official audio line when requested; make the chosen content match its actual recorded words.

Trigger thanks from rescue and reporting from actual recruitment. Queue short lines with the retained campaign dialogue rather than starting an independent overlapping stream. Give each intended line its own once-only state, recheck cinematic/cutoff state when dequeuing, and release the queue if its speaker died. Consult the [dialogue mechanisms](../../../wiki/reference/trigger-dialogue-examples.md) for native transmission and conversation patterns.

For permanent sidequest rewards, load [sc2-bank-system](../../sc2-bank-system/SKILL.md). Identify the actual campaign reward path and mission identity before changing fields; an objective panel or in-map mineral grant does not prove campaign credits. Campaign epochs, receipts and replay rules depend on the selected project, not on a universal Bank name.

## Organize by feature without changing logic

Keep original story folders and group added declarations by function: initialization, each repeated site, scientist/escort interactions, warehouse, voice and settlement as applicable. Co-locate a site's variables and actions under its feature. Preserve intentionally retained compatibility declarations in a named folder rather than silently deleting them.

For a directory-only operation:

1. Snapshot `Triggers` and the actual locales' `TriggerStrings.txt` from the latest Editor save.
2. Reparent the existing declarations through Root/Category `Item` references; allocate IDs only for new categories. Match the target library's explicit reference ownership.
3. Change only category display names. Preserve identifiers, declaration IDs, parameters, event/action order, initial values and non-category localization keys.
4. Compare every non-category element before/after. Ignore structural formatting whitespace, but retain meaningful leaf text and child order, including embedded code and string values.
5. Verify exactly one category membership for each organized item and an idempotent second pass. Unknown new features should be classified deliberately rather than automatically dumped into compatibility.
6. Use the same classifier in the build path, then verify the actual output and save/reopen in the Editor.

This reorganizes the GUI; it does not require rewriting generated Galaxy or mission behavior. The local organizer lives at `projects/liberation-day-expanded/tools/organize_uprising_gui.py`. It is a project-specific example with fixed targets and classification names, not a generic command for an arbitrary map.

## Save the shared library before the map

After changing an exported mod GUI action, save/rebuild the mod before rebuilding its dependent map. The Editor can display the new definition while the saved compiled library still lacks it. In the local case, a reported compilation problem disappeared after the user saved LoyalWOL; no signature repair was needed. Inspect the first real error and current source/output before changing a correct interface.

Read generated scripts to confirm the function definition, map call and event registrations; make fixes in GUI sources. Capture the raw Editor save before restoring any required localization anchors. Use the exact target and locale for that restoration.

## Evidence scope

On 2026-10-27 the user confirmed that the Uprising map and LoyalWOL mod retained their organized folders after saving, closing and reopening and compiled normally. The organizer preserved all 20,725 map and 7,521 mod non-category elements while grouping 224 map and 15 mod named declarations. The result is `Editor accepted` for GUI organization and compilation, not for the map's gameplay.

The movement/replacement and reward examples have GUI state-test evidence, not `packaged runtime passed`. Their use in another mission requires that mission's own branches, resources, persistence contract and playtest. Local provenance is retained in `projects/liberation-day-expanded/reports/uprising-gui-organization.json` and `uprising-current-handoff.md`; missing generated records are not replaced with assumed acceptance.
