# Development conversation examples

[中文](development-conversations.md)

These 36 scenarios cover units, presentation, triggers, dialogue, persistence and validation. Select a project through the [initialization guide](project-initialization.en.md) first; read-only research can use an explicit target without selecting a project. Replace `<...>` with actual inputs. Names and values are examples.

Usually, send only the request in the code block. The agent should read the [workspace rules](../../AGENTS.en.md) and [entry skill](../../skills/sc2-project-entry/SKILL.md), retrieve facts already in configuration/source, then perform the listed checks and delivery. State when you want design only or read-only investigation. These are request templates, not completed acceptance evidence.

For terrain, migration, MCP and model collaboration, see [skill conversations](skill-conversations.en.md) and [terrain conversations](terrain-conversations.en.md).

## A. Units, effective values and abilities

### 1. Read a unit chain

```text
Investigate health, armor, weapons, abilities and production for Unit:<unit-id>. Read-only; do not change files.
```

Agent checks and delivery: Show local overrides, parent and active providers, including upgrade/behavior influences. Read-only. Return effective values/provenance, not reference assumptions.

### 2. Base health

```text
Set unupgraded base health of Unit:<unit-id> to 120, preserving upgrades and behaviors. Do not deploy yet.
```

Agent checks and delivery: Edit actual source, preserve upgrades/behaviors, run relevant checks; no deployment. Report before/after and scope.

### 3. Display mismatch

```text
Unit:<unit-id> has 120 health in the Editor but 150 in game. Find the cause and repair it.
```

Agent checks and delivery: Inspect `Unit:<unit-id>`, parent, upgrades, behaviors, triggers and loaded version. Confirm cause before repairing. Do not counteract an unknown cause with another override.

### 4. New unit variant

```text
Create a project-specific variant of Unit:<base-unit-id>, named <display-name>, costing <resource-cost>, trained by <building-id>.
```

Agent checks and delivery: Reuse assets, check training/card/Actor/text, follow actual project ID conventions. Deliver full production/presentation wiring.

### 5. Blink variant

```text
Add a separate Blink variant to Unit:<unit-id>, cooldown 10 seconds, named “Shadow Blink”. Keep the original.
```

Agent checks and delivery: Keep the original, inspect buttons/requirements/card/Actor and actual project string keys. Names follow the actual data locale; no assumed old prefixes.

### 6. Area damage

```text
Implement radius <radius>, damage <value>, filtering <factions-and-unit-types>.
```

Agent checks and delivery: Query existing ability/effect/search/Actor precedents and reuse active definitions. Explain the actual cast/effect/filter/visual chain and validate XML.

### 7. Temporary buff

```text
Buff <unit-id> for <duration-in-seconds>, changing <attributes-and-values>.
```

Agent checks and delivery: Check stack/refresh/removal and field shapes; provide repeat/early-removal game tests. Deliver lifecycle/scope.

### 8. Validator

```text
Allow <ability-id> only under <specific-condition>.
```

Agent checks and delivery: Check existing dependency validators and field shapes, then implement and validate references. Distinguish cast-entry restrictions from effect validation.

### 9. Upgrade

```text
Add <upgrade-name>, unlocked by <prerequisite-tech>, affecting <units-and-attributes>.
```

Agent checks and delivery: Check Requirement, research ability/button/entry and duplicate unlocks; preserve existing upgrades. Deliver independent IDs and checks.

## B. Actors, command cards and developer strings

### 10. Missing visuals

```text
<weapon-or-ability-id> deals damage but has no projectile/hit effect.
```

Agent checks and delivery: Trace effects, Actor events, models, attachments and creation/destruction; repair from evidence. A disconnected model alone is insufficient.

### 11. Asset replacement

```text
Use existing <model-or-sound-asset> for <object-id> without gameplay changes.
```

Agent checks and delivery: Check path/bindings/animation/audio events; report absent assets. Give birth/attack/death checks.

### 12. Command-card collision

```text
A new button on <unit-id> replaced <button>.
```

Agent checks and delivery: Inspect effective slots, Command indexes and Requirements; preserve positions unless a layout choice is needed. Report cause, final slots and ability binding.

### 13. Text surface

```text
Change <object-id>'s <selection-panel-name / command-card-button-text / tooltip / world-hover-text> in <data-locale>.
```

Agent checks and delivery: Identify field/key first. Do not confuse Editor names with player text or expand into whole-project translation.

### 14. Restore anchors

```text
After the Editor save, some player text shows keys. Restore missing anchors for <data-locale>, preserving existing text.
```

Agent checks and delivery: Inspect `<data-locale>` GameStrings/ObjectStrings, restore missing anchors and check encoding/references; preserve existing text. Never infer missing prose from object names.

## C. Initialization, objectives, timers and attack waves

### 15. Initialization

```text
Call the mod's exported GUI init action from <map.SC2Map>.
```

Agent checks and delivery: Check actual dependencies, Library and existing order; prevent repeats. Edit Triggers only; inspect generated Galaxy read-only. Deliver loading/wiring evidence.

### 16. Objective

```text
Complete ‘<objective-text>’ after destroying <three-building-or-unit-objects>.
```

Agent checks and delivery: Save a dedicated objective handle and count only specified objects; check initial state and duplicate deaths. Never complete another LastCreated objective.

### 17. Victory/defeat

```text
Lose when <base-object> is destroyed and win on <condition>.
```

Agent checks and delivery: Connect existing settlement/progress actions through GUI. Test both paths without bypassing campaign saves.

### 18. Region filter

```text
Trigger once when player <player-number>'s <hero-or-unit-type> enters <existing-region>.
```

Agent checks and delivery: Check real objects and state. Request missing Editor regions; test wrong players/units and reentry.

### 19. Countdown

```text
Show a two-minute timer at mission start, then <action>.
```

Agent checks and delivery: Save the timer and use the correct object for display/start/expiry. Check repeat starts, pause and cleanup; validate GUI.

### 20. Wave scaling

```text
Scale ordinary GUI attack waves in <map.SC2Map> by actual difficulty.
```

Agent checks and delivery: Check AI startup, target points, groups and counts; preserve scheduling and use loaded definitions. Report wrapped/unhandled scope and Editor steps.

### 21. Custom AI migration

```text
Convert Custom AI personality waves in <map.SC2Map> to editable GUI.
```

Agent checks and delivery: Preserve conditions/order/targets/count rules and AI entry. Never edit MapScript.galaxy; report non-equivalent parts and missing references/resources.

## D. Dialogue, dialogs and cinematics

### 22. One-shot dialogue

```text
When player <player-number> enters <region>, play <asset> with <model> portrait and <text-or-string-key> subtitles once.
```

Agent checks and delivery: Confirm send definition/resources/player scope/state. Library compatibility is not audiovisual acceptance.

### 23. Sequential dialogue

```text
Have <character-A>, <character-B>, <character-A> speak sequentially.
```

Agent checks and delivery: Compare Transmission with existing Conversation data and use target-compatible GUI. Save handles/context; explain waits, interruption and absent audio.

### 24. Choices and timeout

```text
Show two choices leading to <branch-A>/<branch-B>; default A after ten seconds.
```

Agent checks and delivery: Save handles and event player; share a single commit path for click/timeout and clean up timer/window. Multiplayer synchronization requires explicit design.

### 25. Skippable cinematic

```text
Run <cinematic-or-dialogue-segment>; normal finish and <key> skip both continue the mission.
```

Agent checks and delivery: Preserve camera/selection/pause/control and share cleanup. Existing objects: `<inputs>`. List missing Editor objects and test each exit.

## E. Banks, scripts and project records

### 26. Bank design only

```text
Design mission, difficulty and unit-unlock Bank storage for this campaign. Design only; no source edits.
```

Agent checks and delivery: Inspect name/format/preload; propose section/key/version/migration. No source edits. Base choices on current evidence; don't default to standalone Galaxy.

### 27. Bank implementation

```text
Implement the confirmed Bank save/load design, using agreed defaults for old files.
```

Agent checks and delivery: Keep old keys and existing GUI/settlement/preload order. Test new/old/missing/repeated saves.

### 28. Hand-written Galaxy

```text
Maintain <confirmed-handwritten-script-entry> with a difficulty multiplier function.
```

Agent checks and delivery: Confirm prefixes/include order from Triggers; edit only hand-written source and validate. Lib*.galaxy and MapScript.galaxy stay read-only.

### 29. Design intake

```text
Ingest <attachment-or-content> into current project data docs/design/ with sources in docs/sources.md.
```

Agent checks and delivery: Separate agreed needs, undecided choices and constraints. Project facts do not enter suite wiki/.

### 30. Cross-session issue

```text
Record <issue>, reproduction, confirmed cause and evidence in the project ledger.
```

Agent checks and delivery: Update current state/necessary decision reasons, linking rules; preserve uncommitted work. No duplicate change diary.

## F. Checks, deployment, troubleshooting and official references

### 31. Check only

```text
Run applicable static checks without edits.
```

Agent checks and delivery: Report actual target, dependency scope and passing/failing checks; use explicit map targets. Without Editor/game evidence the highest state is static validation passed.

### 32. Editor evidence

```text
After external edits, saving causes <disappearing-actions-or-changed-parameters>. Here are the before/after files and Editor version.
```

Agent checks and delivery: Compare GUI ownership/sub-actions/generated calls, then repair source. Keep static and Editor results separate.

### 33. Runtime logs

```text
The package shows <observed-behavior>; steps <steps>, logs/screenshots <path>.
```

Agent checks and delivery: Check loaded version, calls/assets, confirm cause and repair. Give matched retest steps; static success is not runtime success.

### 34. Deployment preview

```text
Preview current source_mode deployment: source, target, overwrite scope; no copy.
```

After reviewing the preview, you can send:

```text
Deploy in that verified direction, retain recovery and verify copying.
```

Agent checks and delivery: For `in_place`, confirm the actual source and whether deployment is needed. Give Editor reload/save steps. Preview alone does not authorize copying; publish/ is never source.

### 35. Reference index

```text
Official Mods are in <directory>; Campaigns are in <directory>. Build an external trigger reference index without selecting a project or editing official sources.
```

Agent checks and delivery: Build an external trigger reference index and list curated mechanisms. No project selection/source edits; report missing metadata. Return fingerprints; target availability still needs target evidence.

### 36. Suite maintenance

```text
Fix <tool-or-documentation-issue> in this workspace, preserve uncommitted work and project selection.
```

Agent checks and delivery: Reuse current paths/implementation and run tools/docs checks. Deliver reasons, scope and untested behavior without modifying projects or official sources.

More setup requests: [installation](../../setup.en.md). Trigger-specific conversations: [44 scenarios and two dialogues](../reference/trigger-agent-dialogue-examples.en.md); underlying mechanisms: [in-game cases](../reference/trigger-dialogue-examples.en.md).

<!-- translation-source: wiki/guides/development-conversations.md; sha256: ed26101667290556e279b60f0b267a798c75afe171834cee874603004671ec69 -->
