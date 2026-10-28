# Custom campaign tools

[中文](README.md)
Maintenance helpers, static checks, bounded Catalog/GUI queries and test entry points. Paths come from agent-config.json and resolve relative to the workspace. Explicit targets win; SC2_MODS_PATH is a fallback only without a configured primary. Missing configured sources never fall back to same-name copies. workspace_copy requires source_mod. Dependency source-lint scope follows validation.include_dependencies/exclude_mods or explicit overrides; loading resolution is separate.

Terrain Module tools: `python tools/sc2-terrain.py --ui-language en capabilities` shows basic drawing requirements, optional extensions and current coverage. See the [terrain guide](../wiki/guides/sc2-terrain-editing.en.md) for scan, inspect, render, plan, apply, diff, undo, redo and controlled Editor experiments. Implemented operations edit isolated Components copies; Editor and game acceptance are reported separately.

## Interface language

All public Python CLIs accept --ui-language auto|zh-CN|en. See [selection and preferences](../wiki/guides/agent-language.en.md). Explicit flags override environment, preference and automatic locale. Ordinary tools never save preferences; only tools/agent-language.py --set does. Pass the chosen language to agent-invoked tools. JSON/XML, canonical diagnostics, identifiers/statuses and exit codes are stable. UTF-8 is used for CLI/child output. Raw platform diagnostics retain original text with localized human context. SC2 --locale selects data, independent of UI language/preferences; changing UI alone neither changes config nor rebuilds an index.

## Quick decisions

| Task | Command | Boundary |
|---|---|---|
| Show/save language | `python tools/agent-language.py` / `--set en` | Only --set writes personal preference |
| Initialize/select | `python tools/init-project.py "<primary.SC2Mod>"` | Derive paths, check recursively, then safely write local config |
| Preflight | `python tools/test-suite.py --scope tools` / `--scope docs` / `--scope mod` | Report actual scope; all is comprehensive |
| Ledger | `python tools/audit-issue-lifecycle.py` | --target and --ledger are mutually exclusive; explicit missing fails |
| Source validation | `python tools/validate-mod.py` | Formal Catalog XSD plus layout/Galaxy static patterns |
| Dependencies | `python tools/inspect-mod-dependencies.py --json` | Actual component declarations/rules, recursive by default |
| CASC | `python tools/sc2-official-cache.py probe --casc-dll "<DLL>"` | Explicit probe/sync only; sync preview unless --apply |
| Unit data-chain migration | `python tools/sc2-migrate.py plan --source "<Source.SC2Mod>" --target "<Target.SC2Mod>"` | [Analysis, selection, packages and transactional import](../wiki/guides/unit-migration.en.md); explicit --apply writes |
| Catalog | `python tools/sc2-catalog-query.py <cmd>` | Bounded objects/references/chains |
| Raw example | `python tools/sc2-reference-query.py object Unit:Marine --component liberty` | --max-chars bounds XML |
| Sample search | `python tools/sc2-reference-query.py find <term> --family <Family> --component <name> --limit 20` | Reference only, not active loading |
| Refresh samples | `python tools/refresh-sc2-reference.py --mods <directory> --campaigns <directory> --cm <directory>` | Verify only; --apply replaces verified snapshot with backup |
| SQLite refresh | `python tools/build-sc2-catalog-graph.py --sqlite-only` | Omit flag for JSON/GraphML/reports |
| Deployment preview | `python tools/deploy-mod.py --dry-run` | Copy only after authorization/direction verification |
| String anchors | `python tools/audit-gamestrings-anchors.py` | Read-only audit |
| Restore string anchors | `python tools/audit-gamestrings-anchors.py --fill` | Separate write after Editor save, using actual data locale |
| Command card | `python tools/audit-actor-and-card-integrity.py` | High-confidence errors fail; --strict also fails candidates |
| Project paths | `python tools/project-paths.py` | JSON only; creates nothing |
| Playtest report | `python tools/extract-playtest-bugreport.py` | Authorized log extraction into project runtime/reports |
| Documentation | `python tools/check-doc-links.py` | Local links/anchors/tool references, no network |
| Translations | `python tools/audit-doc-translations.py` | Required pairs/source fingerprints/scenario counts |

Add --ui-language en or zh-CN to examples as desired. Tool --help/source owns exact interfaces; do not invent flags for historical scripts.

## Validation

Initialization is Components-only, with --dry-run preview and atomic config write after checks. Config validation confirms schema/required paths/readable source and recursive active dependencies; cross-drive paths/optional missing maps may warn. Missing/corrupt source stops.

Unified tools scope runs unit tests; docs scope checks skill frontmatter, local links and translation freshness. mod/all includes actual-target configuration/dependency checks, source validation, GUI dependency/structure, command card, strings and ledger. Current configured source (including editing copy) gets config validation; other explicit targets get their own dependency check, roots and recursion policy. --primary-only/--include-dependencies/--exclude-mod control source scanning, not trigger loading. No selected project is needed for tools/docs.

validate-mod uses lxml or xmllint for formal Catalog/GameData XSD; neither available means failure. SC2Layout.xsd remains an IDE/reference aid; runtime-compatible layout root/children/ASCII checks are separate. XML comments/attributes use ASCII and Catalog cannot be comment-only. Galaxy checks are static patterns (locals/include/operator/ASCII), not an AST compiler. Generated Galaxy remains read-only.

The command-card auditor's historical filename does not imply complete Actor binding validation. Intentional shared slots may depend on Requirements, so candidates summarize unless --show-warnings/--strict is requested. String audits check explicit target Name/Tooltip/Description anchors, target default templates and explicit parent inheritance against active same-locale GameStrings. They expand `##id##`, never create a literal placeholder key, and do not expand scope to all implicit dependency editor names. Missing dependency or locale evidence reports unconfirmed and fails. The auditor accepts --mods-dir/--campaigns-dir/--official-cache; preflight forwards these and --locale (still enUS by default). --fill restores truly missing keys from target ObjectStrings without copying strings already supplied by dependencies.

Frontmatter checks one SKILL.md per skill: matching name, nonempty single-line description/body. Translation pages do not duplicate skills. Documentation checks skip generated/cache/backup/temp/publish directories, ignore fenced Markdown example links but still validate tool references, and support Chinese/duplicate headings, HTML anchors and complex local paths. Translation checks detect missing/stale pairs; they do not prove semantic equivalence.

## Catalog and GUI queries

GUI uses tools/sc2-trigger-query.py build/libraries/find/show/examples/check. Build from explicit original Mods/Campaigns roots; use --reference without a target. See [trigger workflow](../wiki/reference/trigger-knowledge.en.md). Trigger JSON includes provenance/compatibility and searches identifier/zhCN/enUS names. Index v2 rebuilds from original roots; templates are fragments, not accepted maps.

Catalog examples:

```text
python tools/sc2-catalog-query.py --ui-language en find <term> --source-class local_mod
python tools/sc2-catalog-query.py --ui-language en unit-chain <Unit:Id>
python tools/sc2-catalog-query.py --ui-language en production-chain <Unit:Id>
python tools/sc2-catalog-query.py --ui-language en actor-chain <Actor:Id>
python tools/sc2-catalog-query.py --ui-language en show <Family:Id> --limit 30 --depth 2
python tools/sc2-catalog-query.py --ui-language en unresolved --contains <term>
```

Defaults: project runtime/catalog/catalog.sqlite (or explicit graph). Inputs track additions/deletions, size/mtime; --verify-input-hashes detects restored timestamps. Original MPQ hash always participates, even unchanged size/mtime. Default selected-project SQLite queries refresh missing/stale/upgradable indexes once then retry. Valid indexes do not rebuild. Explicit --db/--graph, no-project reference indexes, --no-auto-rebuild and --allow-stale stay read-only. --allow-stale marks history and never grants independent partial-dependency/cache permission.

Identity conflict, malformed manifest, missing source or invalid config stops with specific recovery/build command; no automatic overwrite. --locale enUS|zhCN overrides data language; otherwise reuse the same project's recorded locale or enUS initially. Rebuilds reuse only matching same-project Campaigns/cache scope, with explicit overrides first. Never borrow another project's installation/cache.

Builders retain local_mod, active_component_dependency and reference_export. TXT/non-active examples never prove loaded values. --official-research opens verified loading-uncertain official sources only; it does not waive corrupt XML, custom missing deps or disabled recursion. Other partial investigations require --allow-incomplete-dependencies on both build and query; --allow-partial-official-cache has independent requirements. Index inventory remains v8: info files, relationship/order/rule evidence, dependencies, roots, selected data locale and archive/member provenance. UI preferences are excluded. See [CASC](../wiki/reference/official-casc-cache.en.md).

Declaration postorder is distinct from proven component loading order and unproven XML field merging. Local sources win; peer differences stay ambiguous. Localization nodes retain all text/providers/CASC/MPQ provenance. show `loc:<string-key>` and providers `loc:<string-key>` show candidates; reference_only cannot become a current value. Recursive false is explicitly partial investigation, not complete loading.

## Packed components and conversion

Dependency/GUI/Catalog/static read-only tools accept Components directories and MPQ .SC2Mod/.SC2Map/.SC2Campaign in mixed chains. Read members directly, preserving original absolute archive path/hash, member path/locale/hash; no permanent Components copies. Corrupt local archives cannot be hidden by cache. Initialization, editing, deployment and string --fill require Components and give an explicit unpack command.

```powershell
python tools/sc2-archive.py --ui-language en probe "<packed.SC2Mod>"
python tools/sc2-archive.py --ui-language en unpack "<packed.SC2Mod>" --output "<new Components.SC2Mod>"
python tools/sc2-archive.py --ui-language en unpack "<packed.SC2Mod>" --output "<new Components.SC2Mod>" --apply
python tools/sc2-archive.py --ui-language en pack "<Components.SC2Mod>" --output "<new packed.SC2Mod>" --apply
python tools/sc2-archive.py --ui-language en unpack "<packed.SC2Mod>" --in-place --apply
python tools/sc2-archive.py --ui-language en restore "<backup path from result>"
python tools/sc2-archive.py --ui-language en restore "<backup path from result>" --apply
```

Default conversion is preview; --apply writes. Output must not exist, must be separate, and retain component extension. --in-place explicitly swaps file/directory with a sibling tool-owned .sc2-backup-<id>. Restore verifies ownership/original target and backs up the current version, never deleting unknown contents.

Stage, compare member sets/sizes/hashes, recheck source and publish. Recheck backup after moving an in-place source; failure rolls back. Preserve/report evidence paths if recovery fails. Reject publish/, links/junctions, collisions, incomplete enumeration and ambiguous locales. A single nonneutral locale can be queried but cannot be losslessly represented in Components, so conversion refuses it.

Keep all ordinary binary/assets; exclude root MPQ indexes/attributes/signature and .git/.hg/.svn/.sc2editortool. Preview lists exclusions. Rebuild MPQ indexes/attributes; no promise of byte identity, signature or empty directories, Editor save equivalence or deprotection.

Fixed DLL/license/provenance: [vendor/stormlib](vendor/stormlib/). No PATH search. Native ABI/calls isolated in children: 60-second read default, 1800-second conversion, --timeout override. Limits: 200,000 members, 2 GiB/file, 16 GiB total reads; exceedance fails. CASC remains separate explicit CascLib extraction. Content equivalence is static evidence only.

## Indexes and publication

SQLite/JSON each embed build_id bound to their own manifest. Every index checks recorded workspace/primary/roots/recursion; explicit targets need not be selected projects. Missing/mismatched current build identity cannot be bypassed with --allow-stale. Old histories keep independent partial permissions.

Full outputs stage beside the destination, recheck unchanged inputs then switch. --sqlite-only preserves old JSON/reports; full builds preserve unrelated files. Parse/publication failure keeps previous database+manifest paired.

Automatic refresh closes readers, locks the same target and rechecks after acquiring the lock. Others wait up to 30 seconds; unknown locks are not deleted. The 300-second build child writes only staging; parent validates and publishes. On failure/timeout retain old index and report diagnostics, executable rebuild command and leftover paths; never silently return old data. Progress goes to stderr, query format stays on stdout. At most one rebuild per query; no CASC/network/automatic partial permissions.

Deployment verifies direction/containment even in dry-run. Equal in-place source/target is a safe no-op. Ordinary deployment copies current target then overlays source; --clean stages only source. Recheck unchanged source, verify copied files and switch. Retain one owned prior version; rotate only verified ownership, reject links/manual collisions. Roll back on switch failure; keep/report recovery paths if rollback fails. Lock cleanup cannot mask the primary error. Do not hand-edit copied generated libraries; compile/save in the Editor.

Extract playtest logs only when authorized, using project reports or explicit --output without a project. Raw logs stay read-only. Static tools justify only static validation passed, never Editor accepted or packaged runtime passed without their respective evidence.

## Shared local tools and MCP

See [setup, calls, DeepSeek and recovery](../wiki/guides/shared-tools.en.md). `sc2-local.py` and `deepseek-task.py` use isolated environments; MCP and CLI share business code and project state. Use `sc2-integration.py` for installation, diagnosis and global registration.

## Harness2

`python tools/harness2.py --ui-language en demo --k 2` runs the official local demo through WSL. See the [Harness2 guide](../wiki/guides/harness2.en.md) for the environment, model configuration and scope.

`sc2-optimize --skill <ID>` or `sc2-optimize --batch <JSON-manifest>` validates professional Skills through real Codex calls; no selection options retain the localization flow. The [24-Skill registry](harness2-skills.json) defines group order and acceptance profiles. Candidates use restricted on-demand reference reads, with all selection and solving input tokens included in the benefit measure. After independent cases and primary-agent diff review, use `sc2-apply` to merge a group and `sc2-restore` with its experiment directory for guarded recovery.

<!-- translation-source: tools/README.md; sha256: db2eccea7723c06ab2d726a0235d4704f89c65c8f991ca42f69732415a6df9a5 -->
