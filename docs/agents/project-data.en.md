# Project documentation and runtime data

[中文](project-data.md)
<!-- translation-source: docs/agents/project-data.md; sha256: ff3b644e8570f52c7544005edd16f3121185198dc2a8caa2d4d9eb055731eac9 -->

The suite owns reusable rules, tools, skills and references. Project facts follow the project data directory; generated files belong under runtime/.

## Location and initialization

`python tools/project-paths.py` returns documentation, ledger, index, report and temporary paths without creating them. Without a project, project paths are null and reference indexes use the sibling `<suite-name>-data/reference/`.

`python tools/init-project.py "<primary.SC2Mod>"` records a sibling `<mod-name>.agent` by default. Override with --project-data-dir. Relative project.data_dir resolves against the suite; prefer relative paths on the same drive. Initialization writes local configuration without creating empty project data directories.

Reinitializing the same project preserves an explicit data directory; switching project derives a new one. Editing copies retain the selected project's ownership. Data must be outside the suite and SC2Mod/SC2Map Components. Invalid config/write errors stop; do not fall back to suite wiki/.

| Content | Location | Create when |
|---|---|---|
| Project design | docs/design/ | Durable design facts exist |
| Mechanism contracts | docs/implementation/ | Project-specific contracts exist |
| Sources | docs/sources.md | Design material is ingested |
| Cross-session issues | docs/issues.md | Continued tracking is needed |
| Indexes | runtime/catalog/ | An actual build occurs |
| Playtest reports | runtime/reports/bugreport.txt | Extraction is requested |
| Temporary research | runtime/tmp/ | Staging is needed |

Use the [issue template (Chinese original)](../../wiki/implementation/bug-reports/latest.md) (English original). Small edits do not require new ledgers/logs. Topics describe current agreements; Git/chat preserve history. Version project docs, not runtime/.

On first actual creation, tools exclusively create a .gitignore containing runtime/; preserve existing files. Agents saving project docs follow the same convention. If an existing ignore file lacks runtime/, report or supplement it within authorization; do not replace its rules.

Catalog build/query share defaults; --out/--db/--graph remain explicit overrides. Other target indexes belong beside that component; query them explicitly. Legacy suite indexes remain untouched and can be inspected as history; rebuild the new default when needed.

--ledger explicitly checks an existing ledger; --target selects a component's ledger and is mutually exclusive. Missing default ledgers are skipped; missing explicit ledgers fail. Editing copies retain project data ownership. Pure docs scope checks suite docs/skills; mod/all includes the actual target ledger. Do not automatically move/delete historical backups, reports, indexes or unowned material.
