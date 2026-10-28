# Unit data-chain migration

[中文](unit-migration.md)
<!-- translation-source: wiki/guides/unit-migration.md; sha256: 928cb5be1e43c213b24f5edd6b9bcdd6bf0a2ed4dc52e09c7911088c3330e196 -->

Use `tools/sc2-migrate.py` and the [migration skill](../../skills/sc2-unit-migration/SKILL.md). Roots are new unit IDs compared against each source's actual official dependencies, including Core. The target dependency list stays fixed. Official-ID overrides are excluded as roots but may be required inside a selected chain.

## Analysis and selection

```powershell
python tools/sc2-migrate.py plan --source "<Source.SC2Mod>" --source "<OtherSource.SC2Mod>" --target "<Target.SC2Mod>" --prefix MyImported_ --output reports/migration --ui-language en
```

The output contains `migration-plan.json`, `report.md` and `selection-template.json`. JSON retains effective fields, source definitions, reverse Actor links, resources, texts, mapping proposals and blocking diagnostics. `analyze` and `plan` use the same analyzer. Both read components without switching the selected project. Keep report output outside every source and target component. A successful analysis exit means the report was generated; use each candidate’s `issues` and `executable` to assess export eligibility. Shared field evidence is stored once in `object_evidence[source-path][family:id]`.

A partial baseline can exclude known official IDs but cannot certify absent IDs as custom. Use the [official snapshot workflow](../reference/official-casc-cache.en.md) to obtain evidence. Bind individual snapshots using `--source-cache "Source.SC2Mod=<source-cache-directory>"`; the default cache still applies to other contexts. Reference availability never proves target loading.

Selection JSON:

```json
{"units": {"CustomUnit": "Source.SC2Mod"}, "exclude": ["UnwantedUnit"]}
```

`units` overrides the source choice for an ID; values may be component names, stable source keys from the report, or absolute source paths. Unique playable candidates are selected automatically. Auxiliary and uncertain records require explicit selection. `exclude` removes roots, not dependencies required by other roots. Conflicting roots need a source choice before export. Replace template `null` values with a source or remove the entry.

```powershell
python tools/sc2-migrate.py plan --source "<Source.SC2Mod>" --target "<Target.SC2Mod>" --prefix MyImported_ --selection reports/migration/selection.json --output reports/migration --ui-language en
python tools/sc2-migrate.py export --input reports/migration/migration-plan.json --output "<new-package-directory>" --ui-language en
```

## Resources and boundaries

Ordinary analysis reads Components, MPQ and verified official metadata snapshots. Add `--read-casc-assets --casc-dll "<CascLib.dll>" --sc2-install-dir "<SC2-installation>"` explicitly to read required official assets, retaining their paths and hashes. A target asset at the same path cannot establish equality when the source asset is unreadable. Text, hotkeys and localized assets remain separate for each language, without fallback or translation.

Copied records receive the target prefix and a stable source namespace. Proven equivalent target records retain their IDs. Export materializes inherited fields and retains parent/source definitions as evidence. Array operations, tokens, Actor events and embedded text data links use typed positions. Dynamic links, uncertain ordering, script and custom UI mechanisms block executable output until reviewed. Race/global configuration bindings are target context seams, not ownership of an entire faction; incompatible contexts are reported separately. Unit identity predicates may use an existing target ID without importing that unit. Upgrade mutations outside the migrated gameplay chain require explicit review. The default per-unit budget is 2000 objects; reaching it blocks export, and `--max-objects` can raise the budget for a new analysis. Different resource contents at one virtual path also block export; references are never removed to hide missing data.

Common blockers: `asset_unverified` needs source resource evidence; `external_mechanism_reference` needs script/UI review; `unclassified_actor_reference` needs message semantics; `ambiguous_default_order` means ordering may change default values; `object_budget_exceeded` means traversal is incomplete; `unit_source_choice_required` needs a source choice.

## Import and recovery

```powershell
python tools/sc2-migrate.py preview --package "<package-directory>" --ui-language en
python tools/sc2-migrate.py apply --package "<package-directory>" --ui-language en
python tools/sc2-migrate.py apply --package "<package-directory>" --apply --ui-language en
```

The package binds its analyzed target, inputs, inventory, selection and mappings. Only the final command writes. Reanalyze for another target. Changed inputs, modified packages and different existing objects/text/resources block writing. A staged component passes Catalog XSD validation before shared publication safeguards install it. Failure rolls back; success retains the complete original and ownership record. Preview and restore that backup with `tools/sc2-archive.py restore`. Reimport checks its receipt and current target instead of duplicating records.

Report tooling tests separately from real component acceptance. After an actual migration run component, command-card and string checks, then obtain `Editor accepted` and `packaged runtime passed` evidence. Transaction success does not establish either state.

Selected merge/link/M3 algorithms were adapted from SC2EditorTool under its [MIT license](../../tools/vendor/sc2editortool/LICENSE); see the [notice](../../tools/vendor/sc2editortool/NOTICE).

## Merge only authored local layers

Use `tools/sc2-merge-mod-layers.py plan` when the user explicitly includes local overrides of official IDs. A source-local file does not establish custom ownership; nonofficial-only transfers first compare source-specific official baselines and extract unit chains. Sources are ordered from low to high priority. A collision selects the highest-priority complete original entry, without field composition, official inheritance materialization or dependency additions. IDs, parents, tokens and array operations are preserved.

```powershell
python tools/sc2-merge-mod-layers.py plan --source "<LowPriority.SC2Mod>" --source "<HighPriority.SC2Mod>" --target "<Target.SC2Mod>" --output reports/layer-merge --ui-language en
python tools/sc2-merge-mod-layers.py apply --input reports/layer-merge/layer-plan.json --ui-language en
python tools/sc2-merge-mod-layers.py apply --input reports/layer-merge/layer-plan.json --apply --ui-language en
```

The work directory must be new and disjoint from every component. Preparation writes only a private copy. Apply rechecks source, target and stage fingerprints before publication and keeps a complete backup. Resource files and same-locale text keys follow source priority. Images under `Assets/UI/` remain resources. Trigger data, Galaxy, UI layouts/styles and library registration are listed for separate wiring; existing target files remain intact.

Establish whether unresolved official references are accepted under the target’s existing dependencies. If accepted, retain and report them without copying official layers or deleting references. Delivery status is `source fixed`, with Catalog XML checks recorded separately. Full component preflight, Editor and game acceptance are independent.

## Pruning official overrides after a merge

Use `prune` with the published original plan and a complete official cache for each source to prepare a cleanup of the current target. All custom entries remain; official-ID overrides remain only with ownership evidence from custom-unit roots. Preexisting target entries are protected. Follow abilities, weapons, effects, behaviors, inheritance and necessary actors. Record producer backlinks, ordinary train/build products, upgrade mutation targets and unit identity predicates separately rather than expanding official units. Missile magazines, morph forms and spawned units remain ownership links. Shared Actor event sources locate presentation dependencies; an Actor does not own every other gameplay event that can create it. Effective links after array deletions determine ownership; walking a parent's fields again must not resurrect deleted dependencies. This step preserves resource, localization, script and dependency files.

```powershell
python tools/sc2-merge-mod-layers.py prune --input reports/layer-merge/layer-plan.json --source-cache "<absolute-source-path>=<official-cache>" --output reports/layer-pruned --ui-language en
python tools/sc2-merge-mod-layers.py apply --input reports/layer-pruned/layer-plan.json --ui-language en
python tools/sc2-merge-mod-layers.py apply --input reports/layer-pruned/layer-plan.json --apply --ui-language en
```

Repeat `--source-cache` for every source. Review `removed`, `retained_official` and field evidence. An incomplete baseline blocks cleanup. Apply reuses fingerprint checks, transactional publication and complete backups. Dynamic links and uncertain merge semantics remain diagnostic; successful cleanup is not evidence of complete runtime migration.
