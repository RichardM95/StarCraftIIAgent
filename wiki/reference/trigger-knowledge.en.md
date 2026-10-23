# Trigger queries, dependencies and examples

[中文](trigger-knowledge.md)
<!-- translation-source: wiki/reference/trigger-knowledge.md; sha256: 141ce8a005a73a3eac43cea3997f9f19f0c55b3249ab9cb882ba52e85589a247 -->

This is the GUI-trigger query entry. Keep raw definitions, official cases and target availability separate: a reference hit does not prove loading. See [in-game dialogue cases](trigger-dialogue-examples.en.md) and [44 user scenarios](trigger-agent-dialogue-examples.en.md). There are 27 curated entries across 11 mechanisms; the seven original templates retain their own acceptance scope.

## Development workflow

1. Identify the actual map/mod editing source from source_mode.
2. Run libraries to confirm dependency completeness and each library's loading source.
3. Query find/show for full signatures, presets and sub-actions.
4. Choose compatible examples and migrate local variables/object requirements.
5. Write editable GUI, run check, then hand off to Editor/game tests.

When evidence is missing, explicit --reference permits read-only research while target availability remains unconfirmed.

## Commands and output

Common options precede the subcommand; external paths below are placeholders, not selected projects.

```text
python tools/sc2-trigger-query.py --ui-language en build --reference-root "<官方 Mods>" --reference-root "<官方 Campaigns>"
python tools/sc2-trigger-query.py --ui-language en --reference find TriggerAddEvent
python tools/sc2-trigger-query.py --ui-language en --reference show Ntve:FunctionDef:6D565EB4
python tools/sc2-trigger-query.py --ui-language en --reference examples waves --summary
python tools/sc2-trigger-query.py --ui-language en --reference examples dialogs --case dialog-add-button --summary
python tools/sc2-trigger-query.py --ui-language en --reference check --templates
python tools/sc2-trigger-query.py --ui-language en --target "<地图.SC2Map>" --mods-dir "<目标 Mods>" --campaigns-dir "<目标 Campaigns>" libraries
python tools/sc2-trigger-query.py --ui-language en --target "<地图.SC2Map>" --mods-dir "<目标 Mods>" --campaigns-dir "<目标 Campaigns>" check
```

Configured projects can omit target/Mods; Campaigns uses explicit input or the configured installation. Supply paths for nonstandard layouts. show accepts Library:Type:Id; use local for map-local definitions and --source to disambiguate reference providers. Param, ParamDef, PresetValue and SubFuncType are also queryable.

Dialogue mechanisms are transmissions/conversations/dialogs/cinematics. --case accepts case_id or exact element ID; no selection lists all curated entries for that mechanism. JSON preserves raw XML, parameter order/defaults, locations, fingerprints and compatibility. name is preferred; names retains identifier/zhCN/enUS, all searchable without duplicate definitions. Display limits (normally 200 closure nodes/resources/local graph nodes) never truncate compatibility checking. --max-nodes 0 shows everything; --summary returns counts. Classification comes from manually inspected [case records](trigger-cases.json).

SQLite triggers.sqlite follows project/reference runtime paths; --db overrides. Freshness checks input additions/deletions, size and mtime; --verify-input-hashes adds hashes. Inputs include declarations, registration, GUI libraries, TriggerStrings, GameStrings and generated MapScript. Rebuild stale indexes from their original external roots; stale definitions cannot prove current compatibility. Trigger index version remains 2.

## Loading evidence

ComponentList.SC2Components locates the info declaration. Raw extracted official components may use an actually present DocumentInfo if no list exists, never to hide corrupt existing metadata. LibraryList.xml registers library files; registration ordinal is not the Library ID. Standard Id in .SC2Lib/.TriggerLib and Library Id in Triggers establish ownership. Resolve cross-library references by Library/Type/Id; map-local references retain document scope.

The 2026-10-07 SC2GameData snapshot retained declarations for challenges/frontiers/voidprologue/alliedcommanders; core/liberty/swarm/void.sc2mod had registrations/definitions but lacked component lists and DocumentInfo/DocumentHeader. Checked StandardInfo files had no Dependencies. This does not prove the original game lacks dependencies.

Current resolution uses actual declarations, verified official built-in chains and SC2's Core base rule. Ntve must come from Core's real registered NativeLib. Fake local same-name libraries, unmapped network refs, broken registration and ambiguous definitions fail. Pure-data official packages require verified complete CASC enumeration to prove no GUI libraries; an ordinary missing directory is insufficient.

Use [CASC rules](official-casc-cache.en.md). Applicable builds with verified source enter active scope; verified loading-uncertain sources remain research-only for find/show/libraries/examples. Target compatibility stays unconfirmed and strict check fails. A corrupt complete cache never falls back to partial.

## GUI structure and migration

Definition parameter order describes the signature; call Params bind through ParameterDef, so sibling order may differ. The official sc2tutorial Terran MakeBarracks CreateObjective case confirms this. Check ownership, coverage and duplicates, not just ordering.

Defaults are definition facts; calls still supply explicit required parameters. SubFunctionType belongs to the parent definition. Checks follow function bodies, variable initializers, parameter defaults and indirect GUI references. Default templates validate references without implying execution; Label grouping is not executable dependency. Variable arguments follow ParamFlagMultiple and difficulty literals use official ValueId.

Remap local declaration/reference IDs before import, synchronizing TriggerStrings/GameStrings. tools/sc2_triggers.py remap_local_ids(raw, strings, occupied) returns XML/strings for map-local fragments; occupied includes all existing elements/anchor IDs. Mod Library import additionally requires explicit ownership.

Global Variable declarations need Root/reachable Category Item registration. Local/structure fields need Variable declarations under their owner. Reads are not declarations. Allocate separate initializer Param and mutable FunctionCall/Param instances; FunctionDef/ParamDef/Preset and variable reads can be shared. See [retrospective S1](../../docs/agents/retrospective.en.md).

Target check adds these structural checks independently of missing external libraries, without exempting dependencies or deleting/copying nodes automatically. Rootless reference fragments do not imply global registration; ParamDef defaults are not owned execution instances. Inspect orphan calls/parameters before cleanup.

## Validation scope

Resolve actual loaded root definitions and their indirect active references. Matching IDs with different fingerprints do not confirm compatibility. Identical component copies can match only if loaded. Curated migration can use inspected source-map local_graph nodes; other local/external references must resolve in the target. Recheck target inputs before compatibility output.

Unified mod/all preflight includes primary-target GUI checks without a reference index. --mods-dir/--campaigns-dir select actual roots; Catalog --primary-only/--exclude-mod never trim trigger dependencies. Proven absence of checkable GUI produces not_applicable; incomplete registration/metadata still fails. Check maps via explicit --target. Tools/docs scopes need no active project.

References remain reference_only; library closure does not migrate map objects, Catalog links, initialization or IDs, nor compile Custom Script. [GUI fragments (Chinese original)](trigger-templates/README.md) (original reference) are not runnable maps. check --templates checks indexed native structure; with a target it also checks target compatibility. No map resource/runtime acceptance is implied. [Performance record (Chinese original)](trigger-query-performance.md) retains original technical measurements; single samples are not stable performance claims.

Static tools justify only static validation passed. Editor reload/save and game scenario evidence are required for Editor accepted and packaged runtime passed.

## Editor behavior evidence boundary

Earlier claims that only GUI calls preserve mod libraries or event declarations must be adjacent lacked versioned minimal before/after evidence. Treat these as conservative handoff practices rather than universal linker/generator facts. GUI structures and references come from official Triggers/NativeLib.

For future isolated comparisons of GUI versus equivalent Custom Script and near versus distant event registration, record Editor version/dependencies/input fingerprints, saved Triggers, generated calls/events and runtime observations in [template acceptance (Chinese original)](trigger-templates/acceptance.md) (original evidence record). Until then these claims remain unproven.
