# Offline-first builds and tests

[中文](offline-testing.md)

Tool, documentation and static-check tasks do not launch the Editor or game. For map runtime verification, prefer `sc2_validate_run_test(project_id, installation, product="s2_cn", sample_seconds=5, startup_timeout=120, probe_timeout=120)`. It returns a background job ID. Query `sc2_job_status`, then use the returned `probe_id` with `sc2_probe_result` for recovery.

The operation checks the explicit map and dependencies, generates Galaxy from GUI sources, checks types, packages and reads back an independent MPQ, then starts the game directly. Source and generated source files remain read-only. Mods support offline checking; runtime tests require an explicit map that uses the Mod. Never select a production map implicitly. Legacy `sc2_validate_launch_test` exports existing files and launches them; it does not rebuild scripts.

Each smoke test uses a unique Bank recording run identity, the map initialization event and a heartbeat after the specified game time, while retaining the offline execution message. Evidence binds source fingerprints, build and archive hashes, Bank and incremental logs. Existing clients or Editors block tests. Cancellation, timeout, old Banks, unknown identity and changed inputs cannot pass. Stop only verified test-owned processes.

`packaged_runtime_passed=true` certifies only `map_smoke`: this code executed, the game advanced briefly and no relevant script errors were found. Mission objectives, visuals, saved-game compatibility and complex gameplay need separate tests. Other warnings are listed separately. Launch success, absent errors or a generic PASS alone do not establish success.

## Timing and longer scenarios

Results include `stage_seconds` for dependencies, static checks, generation, packaging and runtime. Errors retain their original code and GUI node location, adding `phase` and `editor_required`; unknown errors do not automatically require Editor fallback.

`sample_seconds` supports 0.25 to 600 game seconds. Increase `probe_timeout` for longer scenarios; the default remains a five-second smoke test. Observing the full duration does not establish gameplay correctness: validate the scenario Bank separately.

Collection first verifies all source content, inventories and dependency resolution. Only when that verification covers every build input and script source does collection reuse it instead of parsing the trigger graph again. Partial coverage uses the original full parsing path. `freshness_validation` identifies the path; no stale cross-run cache is used.

## Editor fallback

Use the Editor for required native saves or specific Editor acceptance, explaining the reason and following the Editor handoff checklist. For unsupported offline structures, diagnose and repair the generation gap first. Errors retain the file, node and reason, returning `editor_required=false` and `next_action=diagnose_offline_generation`. Hand off concrete Editor operations only after confirming that the current tools cannot complete a necessary step. Diagnose missing dependencies, compiler errors and environment failures first.

## Evidence

Keep existing status names. The offline route can advance from `static validation passed` directly to a scoped `packaged runtime passed`, without granting `Editor accepted`.

Record `Validation Route: offline`, `Validation`, `Offline Validation` (build, archive and execution proof), and `Runtime Validation` (target, reproduction, observations and scope). The Editor route uses `editor`; old records default to `editor` and still require actual `Editor Validation`. Empty placeholders and skipped labels are not evidence.

<!-- translation-source: wiki/guides/offline-testing.md; sha256: 63c8bd4a06914c52df19beda3d3532b5527d9b4cffd202017aba00181d9655df -->
