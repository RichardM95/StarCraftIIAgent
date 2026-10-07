# Agent Context Efficiency

Use this page when a task risks loading too much repo context. The goal is to keep implementation passes bounded, reproducible, and focused on the smallest evidence needed.

## Context Bloat Sources

1. **Raw catalog dumps and component samples.** `DataEditorXML/*.txt` and `DataEditorXML/SC2GameDataComponents/` overlap in places and can produce repeated large results when searched together.
2. **Generated graph artifacts.** `sc2-catalog-graph-out/graph.json` and object summaries are generated and can be much larger than a task needs.
3. **Historical logs.** Old correction history is useful for patterns, but reading full archive/log pages before checking topic pages repeats stale implementation details.
4. **Unbounded search results.** Repeated `rg` over all XML and wiki files produces duplicate hits across dependencies, local mod rows, and generated outputs.

## Default Navigation Order

1. Read `AGENTS.md`, then route directly from `wiki/index.md`. Use `wiki/catalog.md` only when the task router does not name the needed page.
2. For SC2 catalog questions, run deterministic catalog queries first:

```powershell
python tools/sc2-catalog-query.py find <text> --source-class local_mod --limit 20
python tools/sc2-catalog-query.py show <Family:Id> --limit 30 --depth 2
python tools/sc2-catalog-query.py providers <Family:Id>
python tools/sc2-catalog-query.py unresolved --contains <text> --limit 40
python tools/sc2-catalog-query.py path <Family:Id> <Family:Id> --max-depth 4
python tools/sc2-catalog-query.py unit-chain <Unit:Id> --source-class local_mod
python tools/sc2-catalog-query.py production-chain <Unit-or-Abil:Id> --source-class local_mod
```

3. When a catalog implementation needs a concrete official/partner precedent or English/Chinese string, run one bounded query against the component snapshot. Specify the catalog family and a likely component whenever known:

```powershell
python tools/sc2-reference-query.py components --source CM
python tools/sc2-reference-query.py find 'id="Marine"' --area gamedata --family Unit --component liberty --limit 20
python tools/sc2-reference-query.py find 'Unit/Name/Marine' --area zhcn --component liberty --limit 10
python tools/sc2-reference-query.py object Unit:Marine --component liberty --max-chars 6000
```

Open only the returned file fragment. Record its component and line, then reuse it for the same task. The snapshot is a source of examples, not evidence of an active dependency or effective value. A refreshed snapshot does not require rebuilding the catalog graph.
If the catalog query reports a stale index, run `python tools/build-sc2-catalog-graph.py --sqlite-only` once before using current project results. Only `--allow-stale` permits intentional inspection of old data.

4. For historical implementation context, inspect Git history for the relevant path:

```powershell
git log --oneline --all -- <path>
```

Read the current canonical page first; history is for prior states, not the working contract.

5. Use `rg` after the durable wiki or a scoped query identifies a catalog family, ID, file, or wiki page. Scope it to one selected dump or component folder.

## Common XML Failure Classes

1. **Incomplete extraction graph** — unit/ability/effect/behavior/actor rows copied, but models, sounds, turrets, validators, helper weapons, requirement nodes, buttons, or localization missing.
2. **Editor canonicalization mismatch** — duplicate `(catalog type, id)` across `GameData.xml` and typed side catalogs after an Editor save.
3. **Localization ownership mismatch** — player-facing text not anchored in `GameStrings.txt`; editor labels missing from `ObjectStrings.txt`.
4. **Actor and command-card inheritance traps** — parented actors keep ancestor events; inherited command cards leak buttons from vanilla parents.

Local XML parsing does not catch Editor schema warnings, missing active rows, wrong command-card layer, actor scope collisions, or pruned text. See [xml-patterns.md](xml-patterns.md#editor-round-trip-checklist).

## Practical Rules

- Never edit auto-generated editor files (`MapScript.galaxy`, `Lib*.galaxy`, `ComponentList.xml`). New triggers are GUI-first; if the user explicitly requests a standalone Galaxy implementation or an existing script needs maintenance, keep hand-written code in `*_ScriptBlock.galaxy` or `Base.SC2Data/Scripts/`.
- Never paste or load whole raw XML dumps into the model context.
- Validate XML and Galaxy syntax against engine rules before editor handoff: `python tools/test-suite.py`.
- Avoid reading `sc2-catalog-graph-out/graph.json` or `catalog.sqlite` directly; use `tools/sc2-catalog-query.py`.
- Query the component snapshot with `tools/sc2-reference-query.py`; do not run repeated whole-tree `rg` searches for each field.
- When grepping generated/catalog folders, constrain the search with `--glob` and `--max-count` where possible.
- Treat `wiki/log.md` as a short decision record, not as the current source of truth.

## Catalog Graph Tooling

Refresh the query database with `python tools/build-sc2-catalog-graph.py --sqlite-only`. Omit that flag only when the complete JSON, GraphML, and object reports are needed. Query through `tools/sc2-catalog-query.py`.

## Tool Failure Recovery

If a patch helper reports errors or fails to apply a replacement, restart the session or use exact string replacement while preserving UTF-8 line endings. Run `python tools/test-suite.py` to verify formatting and syntax. Never edit files in `publish/`.
