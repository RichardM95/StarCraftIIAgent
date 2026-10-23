# Runtime diagnosis and mechanism boundaries

[中文](runtime-diagnostics.md)
<!-- translation-source: wiki/implementation/runtime-diagnostics.md; sha256: 2372089246c269231ad30482b0258c5877aa9890d2f902a8faa69e38603149a1 -->

For lag, crashes, UI, ability state and mission events. [Retrospective sources](../../docs/agents/retrospective.en.md) support methods/local cases, not laws for every SC2 version. Follow [feedback gates](testing-feedback-workflow.en.md).

## Prove which version ran

Check component, active dependencies, editing mode and key generated actions. An XML node does not prove implementation or generation; inspect cleanup calls and execution paths. Generated Galaxy is read-only; regenerate using [handoff](../guides/editor-handoff.en.md).

Separate fresh starts, ordinary saves, victory transitions, cross-mission transitions and repeated casts. Old saves may preserve variables/units/behaviors and cannot alone prove new initialization failed. Reuse confirmed test conditions within the same investigation.

## Lag and crashes

Identify the phase: loading, initialization, aiming, casting, accumulating afterward, unit death or cinematic exit. Record map, unit scale, concurrent actions and log times.

- Moving the camera to empty terrain helps separate rendering from simulation; it does not prove the bottleneck.
- Compare timers, temporary units, active effects/searches with a baseline before repeated casts and after cleanup. Many creations in source are not leak evidence (S1).
- Change one performance factor at a time under matching save/start/camera/actions. Lower search frequency can affect moving-target hits and total damage; preserve requested gameplay and consider a dedicated visual chain first (S1/S2/S4).
- Match crash stack/logs to the same occurrence; standing warnings or unrelated script errors are not automatically causal. If disabling UI does not stop crashes, inspect the remaining chain (S7).
- Confirm campaign AI/subsystem startup before periodic scans. Without unit-event context, use the iterated unit rather than EventUnit. Query exact APIs (S7).

## UI, actors and assets

Gather functional and visual evidence separately: test hotkeys when buttons vanish; inspect energy numbers, bindings, water animation and ability availability separately. Read layout bounds/anchors and actual animation names before adding visibility actions or refresh loops (S1/S5).

Actual providers for same-name models/DDS depend on active dependencies/precedence. For black blocks, highlights or repeated effects, inspect Graphics logs, material/emissive textures, inherited events and overlapping units. Actor alpha may not affect every emissive layer; decodable DDS need not load correctly in game. Back up isolation tests of official-path overrides before changing terrain (S2/S3/S6).

For visual reductions use dedicated Actor/model overrides while preserving projectiles, indicators, unit counts and combat outcomes. Only matched retests support appearance/FPS improvement claims.

## Abilities and event state

- Repeated creation/region events can affect the same unit again. Before granting unique powers check its behavior; release slots on death, lost behavior or ownership changes. Player ownership is not selected-unit behavior evidence (S2).
- Check whether autocast accepts units, points or both; separate targeting, acquisition and settlement validators. Test manual/auto, normal/morphed and near/far (S6).
- Enumerate deployment, casting, evolution, respawn, cancel and abnormal exits for cooldown/shield/reversion state. Initialization handles initial state; normal casts avoid duplicate native cooldown. Settle cleanup/rewards once (S6).
- Define per-attack/per-damage, primary/secondary and spell boundaries for lifesteal/sharing/counts. Exclude recursion and expiry/self-destruct damage; test shields, invalid hits, death and temporary-unit cleanup (S2/S6).

## Objectives and persistence

Handle rescue-before-discovery and repeated events idempotently. Recheck objective state before queued dialogue creates an obsolete in-progress objective (S3).

Survival rewards track designated initial units; reinforcement/respawn does not restore eligibility. Freeze results before the final animation, commit on victory and preserve prior unlocks. Storage keys/commit points come from the actual project (S3).

Text, counters and victory logic share one threshold. Distinguish current versus cumulative resources, initial stock versus capacity. Replaced resource structures require checking underlying resource/building relationships; increasing a limit alone does not solve depletion (S2/S3).

For missing Bank progress, inspect disk, memory and destination map load/apply chains via the [Bank reference (Chinese original)](bank-system.md) (English technical original).
