# Project initialization

[中文](project-initialization.md)
<!-- translation-source: wiki/guides/project-initialization.md; sha256: ee77a753eecceb802d9e654c02de17e2d0a300b0f63e44e78cfa73d2f6cf8e22 -->

Provide the primary Components .SC2Mod folder when requesting selection. The agent directly runs `python tools/init-project.py "<primary-mod-components-path>"`; users need not edit JSON or list dependencies. The tool derives SC2/Mods/Maps from standard layout, recursively validates dependencies and atomically writes config only after checks pass. --dry-run is read-only. For nonstandard layouts supply --mods-dir, --sc2-install-dir and/or --campaign-maps-dir only as needed.

Bank, Library ID, hand-written script block and prefixes cannot be inferred from a folder name. Verify actual component/Triggers identity after selection; never carry an old project's assumptions forward. [Workspace rules](../../AGENTS.en.md) remain authoritative.

## Copyable conversation examples

| Example | Request | Expected action |
|---|---|---|
| 1 Standard layout | “My primary Components mod is `D:\SC2\Mods\MyCampaign.SC2Mod`. Initialize it and check dependencies and identity.” | Run initialization and config validation, no manual JSON request. |
| 2 Preview only | “Preview `<primary-mod-components-path>` with --dry-run; wait for confirmation before writing config.” | Report inferred paths/dependency gaps, no config writes. |
| 3 Switch project | “Select `D:\StarCraft II\Mods\AnotherCampaign.SC2Mod`; verify identity rather than reuse the old campaign.” | Reinitialize, check Library/Bank/source evidence. |
| 4 Nonstandard layout | “Primary: `D:\Projects\MyCampaign.SC2Mod`; Mods: `D:\SC2Data\Mods`; install: `C:\Games\StarCraft II`; maps: `D:\SC2Data\Maps\Campaign`. Initialize only after validation.” | Use explicit directory flags. |
| 5 Validate current config | “Check current paths, source_mode and dependencies read-only.” | Run tools/validate-agent-config.py, do not select another project. |
| 6 Temporary other mod | “Inspect `<other.SC2Mod>` with --mod-dir; do not change the default project.” | Pass actual target and dependency roots to relevant checks. |
| 7 Missing dependency | “Initialization reports `<dependency-reference>`; diagnose the declaration and missing metadata. Do not hide it with --allow-incomplete.” | Locate exact gap, preserve old config on failure. |
| 8 No Components yet | “I only have a mod in the Editor; explain saving Components. Do not invent configuration.” | Give Editor steps, wait for the actual directory. |

## Installation and selection

Keep suite separate from game/mod/project data. Open this workspace in a compatible assistant with local file/Python access; Windows, Python and an installed SC2 Editor are needed for the corresponding operations. Host metadata is in agents/trae.yaml; rules/tools remain local regardless of host.

In the Editor create/open the mod, select intended dependencies, and File → Save As → Components. Provide the directory containing ComponentList.SC2Components and its declared info file. Packaged MPQ sources are readable for queries; initialization/editing still require Components. Explicit tools/sc2-archive.py conversion is a separate operation.

Configuration includes paths.workspace_dir, sc2_install_dir, mods_dir, campaign_maps_dir and project.primary_mod/source_mode. Relative values resolve against the suite; cross-drive absolute paths receive portability warnings. in_place edits the configured primary source. workspace_copy requires explicit project.source_mod; missing copies stop writes. Never use publish/ as source.

Dependency resolution reads the info entry in ComponentList, follows declarations recursively with sharing/cycle checks and local priority, and consults a matching verified official cache only for absent official sources. Existing corrupt metadata is an error. Do not infer dependencies by listing Mods. Traversal order and proven loading rules remain separate from unresolved XML field merges.

Use tools/project-paths.py to inspect data ownership; default project docs/runtime live beside the primary mod as <name>.agent, outside Components and suite. --project-data-dir overrides; same-project initialization preserves an explicit choice. No empty data tree is created just by initialization.

## Verification and completion

```powershell
python tools/validate-agent-config.py --ui-language en
python tools/inspect-mod-dependencies.py --ui-language en --json
python tools/test-suite.py --ui-language en --scope tools
python tools/test-suite.py --ui-language en --scope docs
python tools/test-suite.py --ui-language en --scope mod --primary-only
python tools/build-sc2-catalog-graph.py --ui-language en --sqlite-only
```

Choose only relevant scopes; report actual target and dependency scan policy. --mods-dir/--campaigns-dir/--official-cache are explicit one-off overrides, not config changes. External targets do not inherit another project's exclusions or recursion-disabled setting.

Missing primary source stops; never find an old same-name copy. Packed files are readable but require explicit unpacking for edits. A nonexistent optional maps directory or machine-specific absolute path can be a warning; corrupt metadata and incomplete active dependencies remain errors. --allow-incomplete is explicit investigation permission, not proof of target completeness.

Completion requires valid paths, correct identity/source ownership and dependency evidence. Build/query Catalog defaults follow project data. Default SQLite queries refresh only when needed; explicit indexes and --no-auto-rebuild remain read-only. --allow-stale authorizes history, independently of partial-dependency permission. Editor/runtime gates require their own evidence; see [handoff](editor-handoff.en.md).
