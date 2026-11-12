# Editor handoff checklist

[中文](editor-handoff.md)
<!-- translation-source: wiki/guides/editor-handoff.md; sha256: 0315a7508c5d5ccef0eeaea50ef67e0fb3899deeb087f3c068b91364a75ca6a3 -->
## Offline-first validation

Ordinary checks launch neither the Editor nor the game. Map runtime tests prefer `sc2_validate_run_test`: offline generation, checking, packaging, direct game launch, Bank and incremental-log collection. Use the Editor only for unsupported structures, required native saves or specific Editor acceptance, explaining the reason first. See [offline testing](offline-testing.en.md) for routing and evidence.

`Editor accepted` is an optional branch. An offline run may advance from `static validation passed` directly to scoped `packaged runtime passed`, without claiming Editor acceptance. Ledgers with `Validation Route: offline` require `Offline Validation` and runtime evidence; legacy ledgers default to `editor`.


After source changes and before playtesting, provide steps relevant to the change. Use exact [lifecycle gates](../implementation/testing-feedback-workflow.en.md): reported → root cause confirmed → source fixed → static validation passed → Editor accepted → packaged runtime passed. Static success cannot cross the Editor gate. The operator checks the right dependencies, warnings, compilation and Components save, and records scenario/results. State the highest actual gate, such as “static validation passed; awaiting Editor accepted”.

## Source and deployment mode

Read project.source_mode. in_place uses configured paths.mods_dir/primary_mod as the only source; no extra editable copy or deployment is needed. workspace_copy uses project.source_mod (workspace-relative or absolute); missing source stops writes. Preview tools/deploy-mod.py --dry-run, then deploy in the verified direction. Never copy the deployed version back over the editing source. Automatic deployment preserves primary_mod subdirectories; explicit --source deploys by folder name. Never find another same-name source when the configured one is missing.

## Galaxy changes

1. Save hand-written source; deploy only in workspace_copy after preview.
2. Open `<ModName>.SC2Mod` in the Editor and confirm the Custom Script block/include targets.
3. Compile and File → Save as Components. Let the Editor regenerate Lib*.galaxy; never paste code into generated libraries.

## XML and GUI changes

Open the affected mod, inspect XML warnings, resolve Catalog type/ID problems and save as Components. For map Triggers changes, reopen the affected .SC2Map and save to regenerate MapScript.galaxy.

For maps, open paths.campaign_maps_dir/<Category>/<MapName>.SC2Map/, confirm Modules → Dependencies contains `<ModName>.SC2Mod`, and save. Never open Blizzard maps while the project mod is active as an external override.

## Source-to-runtime verification

For command-line Components loading, pass the directory's `ComponentList.SC2Components` to `-loadfile`, rather than the `.SC2Mod`/`.SC2Map` directory. In an isolated B98370 mod experiment, the directory argument selected archive saving and an ordinary save replaced it with a failed MPQ; the explicit descriptor preserved the directory. Refuse a missing descriptor and validate a new entry point on a complete independent copy first. Save As alone may also preserve stale generated libraries; inspect the actual code as described below.

Before external edits close affected Editor documents and back up; reuse a still-valid confirmation of closure. When dependencies need regeneration, reload/compile/save them before the primary mod/map.

After saving inspect generated calls, global declarations, event registrations and initialization order read-only. Timestamps alone prove nothing. Old loops, missing actions or undeclared lv_ mean new source has not reached the tested runtime. Fix generation before stacking candidate repairs. Empty GUI Custom Script actions do not prove cleanup executes. See [archived evidence](../../docs/agents/retrospective.en.md).

Recheck changed Triggers references/structure after Editor normalization, then audit string anchors for the actual target/data locale; --fill is a separate write. Distinguish fresh starts, old saves, ordinary loads and victory transitions. A passing idle/display scenario covers only that scenario.

After playtests, extract logs with tools/extract-playtest-bugreport.py when authorized, triage with [feedback](../implementation/testing-feedback-workflow.en.md), and maintain the project ledger using the [template (Chinese original)](../implementation/bug-reports/latest.md) (English original).
