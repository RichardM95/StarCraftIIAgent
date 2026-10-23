# Official CASC dependency cache

[中文](official-casc-cache.md)
<!-- translation-source: wiki/reference/official-casc-cache.md; sha256: 862e9645d415d54b0f728c9398586464c5cb39c3770968be1a0d89277e281c6b -->

[sc2-official-cache.py](../../tools/sc2-official-cache.py) opens CASC only for explicit probe/sync. Dependencies, GUI, Catalog and preflight consume published caches without loading CascLib, extracting or networking. Local MPQ components use StormLib; see [archives](../../tools/README.en.md#packed-components-and-conversion). No command implicitly rewrites project configuration, game or mod.

## Probe and synchronization

Installation defaults to config; explicitly supply the DLL. Other installations need --sc2-install-dir and target-appropriate --mods-dir.

```text
python tools/sc2-official-cache.py --ui-language en probe --casc-dll "<CascLib.dll>"
python tools/sc2-official-cache.py --ui-language en sync --target "<Components>" --casc-dll "<CascLib.dll>"
python tools/sc2-official-cache.py --ui-language en sync --target "<Components>" --casc-dll "<CascLib.dll>" --apply
```

probe returns diagnostic JSON for layout, unique active build, DLL architecture/hash/exports/charset and parsed XML samples. read_verified requires storage opening and complete metadata/definition reads/parsing, not complete dependencies. Native calls run in isolated children (60-second default, --timeout override); crash/timeout become diagnostics and child handles are released/reclaimed. Error code 2 alone does not prove game corruption.

sync previews in memory without creating caches. It resolves metadata/publication prerequisites first; known Core/bootstrap blockers stop before large GameData/localization payloads. extraction_phase reports metadata/payload and counts only successful reads. Not-attempted languages are neither declared available nor missing. Required missing files return partial; default --apply refuses partial publication. Optional unreadable language files are recorded in unavailable_files, never fabricated. applied indicates actual publication.

--allow-partial explicitly continues known payload extraction; --apply publishes research data, normally to a sibling <build>-partial directory. Exit 1 still denotes incomplete loading evidence even if applied is true. file_states distinguish readable/unavailable/not_attempted. Missing references remain assessment.problems; they are not falsely counted as unreadable existing files. Component closure and batch loading_status are separate facts.

Default cache: sibling StarCraftIIAgent-data/reference/casc/<installation-id>/<build-key>/. --official-cache overrides. Preserve lower-case Mods/Campaigns logical paths and original bytes. Manifests record actual CASC paths, installation/build, DLL fingerprints, hashes, language availability and registration evidence. Extract only component/dependency metadata, GUI registration/libraries, Galaxy definitions, GameData XML and available zhCN/enUS text. Exclude whole maps, models, textures, audio and cinematics.

Verify paths/build/hashes/XML/registration/GameData closure before staged publication. Failure preserves the previous cache. Existing destinations must match installation/build and completeness class; never place caches inside suite/game or their ancestors, or mix builds/installations.

## Loading evidence and limits

Use ComponentList's actual info entry, or an actually present DocumentInfo when no list exists. Never synthesize official metadata. Local sources take precedence; corrupt existing local components fail instead of falling back to cache. Only absent official references with exact evidence use cache. Custom missing dependencies, similar names and unmapped network refs are not guessed.

Core is the implicit SC2 base, recorded before components by sc2_core_base. Its scope is the engine already verified by this implementation, based on the user-confirmed SC2 base contract and [Core Always First research](https://github.com/sc2-arcade-watcher/sc2-file-format-docs/blob/main/archive-system.md#core-always-first). Matching installation/build and real Core/LibraryList/NativeLib remain required. It does not synthesize DocumentInfo or disassembly; binary bootstrap profiles are separate optional evidence.

The 21-entry chain originally found in locale research also participates in [mod-path validation](https://github.com/sc2-arcade-watcher/sc2-file-format-docs/blob/main/archive-system.md#modpath-validation-algorithm), recursive dependencies, Base.SC2Data validation and registration. Verified built-in single-player chains use engine_dependency_chain; locale names alone do not demote them. Multiplayer stacking extras, custom refs and unmapped network refs stay outside that rule.

Cache manifest v3/component assessment v3 keep availability, relationships, Catalog scope and base state separate. Old assessments/caches are revalidated in memory, never rewritten. Old complete is not an exemption; unknown assessment versions fail. External JSON never installs trusted engine rules. CascLib uses verified basic local storage/enumeration/read APIs, not unverified extended structs, online flags or zero-fill encrypted-content options.

## Declarations, recursion and order

Declared info dependencies retain raw order and edge ordinal/raw/evidence/relation, distinguishing declared, built-in, locale and bootstrap relations. A confirmed Heros→Void campaign declaration remains true even if an upstream edge is unknown.

traversal_order is deduplicated dependency-first postorder; cycles fail. With complete applicable evidence, loading_order records Core first, dependencies before dependents and the current component last. file_merge_order separately remains unconfirmed for XML field merges; same-level conflicts stay ambiguous. Catalog uses recorded traversal, not filename sorting. Includes resolve relative to the containing file, recursively in declaration order; deduplicate repeats and fail on cycles/missing/escaping paths.

All cached files are hash-checked. Target official_problems includes only relevant components and necessary Core evidence; unrelated loading uncertainty stays in cache assessment. Unknown installations never borrow another installation's Core. Corruption/unreadable required payload remains a hard error.

## Shared queries and research

init-project, inspect-mod-dependencies, validate-agent-config, sc2-trigger-query, build-sc2-catalog-graph, sc2-catalog-query and test-suite support --official-cache. Without it, read-only discovery matches the target Mods installation/build; missing caches remain dependency gaps, invalid explicit caches fail.

```text
python tools/inspect-mod-dependencies.py --ui-language en --official-cache "<缓存根>"
python tools/sc2-trigger-query.py --ui-language en --official-cache "<缓存根>" libraries
python tools/sc2-trigger-query.py --ui-language en --official-cache "<缓存根>" check
python tools/build-sc2-catalog-graph.py --ui-language en --official-cache "<缓存根>" --locale zhCN --sqlite-only
python tools/sc2-catalog-query.py --ui-language en --official-cache "<同一缓存根>" stats
python tools/test-suite.py --ui-language en --scope mod --official-cache "<缓存根>"
```

## Official research queries

Exact matching prefers complete cache, then corresponding partial; a corrupt complete cache stops instead of hiding behind partial. Default-project Catalog refresh passes --official-research; GUI find/show/libraries/examples can use verified research sources. Only uncertain official loading is opened this way. Corruption, missing custom/network mappings and disabled recursion retain their errors/permission boundaries. Ordinary queries never extract/network or grant general partial permission.

Matching verified Core becomes an implicit base edge; Ntve follows real registration. Unconfirmed/nonapplicable sources remain research-only with unconfirmed target compatibility. Catalog uses reference_export plus CASC/loading evidence for these sources; strict config/deploy/trigger check still requires completeness. Historical partial indexes retain explicit permission; default projects rebuild from current sources.

Catalog categories remain local_mod, active_component_dependency and reference_export, with local precedence and provider evidence. --locale enUS|zhCN (default enUS) selects text without cross-language filling. Default query refresh reuses recorded locale or explicit override; --db/--graph/--no-auto-rebuild/--allow-stale remain read-only as described in [tools](../../tools/README.en.md#indexes-and-publication).

Cache validation and Catalog share standard-table/additional-entry/Includes closure logic. GameData.xml registers additional spaces, not all standard tables; see [data spaces](https://s2editor-guides.readthedocs.io/New_Tutorials/04_Data_Editor/data-spaces/). Research inventory is parseable XML with unconfirmed loading. Candidate filenames do not establish activity. Applicable standard-source rules combine standards with explicit additional closure. Missing additional refs/escapes fail. Unknown roots remain unclassified; nonempty unregistered XML stays uncertain. With verified standard rules, empty unregistered Catalog placeholders need not block scope. Only explicit no-GameData registration plus no inventory confirms no Catalog. Hand-written mod scanning and TXT reference status are unchanged. Reuse XML parsing/manifest collection per operation while fully checking hashes; no cross-command trust cache.

External targets use actual dependency checks rather than current-project config acceptance. Pass the same Mods/Campaigns/cache to all related checks. They default to recursive dependencies but primary-only authoring lint, without inheriting another project's exclusions/disabled recursion. Config overrides are one-off, read-only.

Catalog inventory remains v8, including original archive/member identity, research/rules/evidence fingerprints, cache inventory, build/locale and actual roots. Old default indexes rebuild on demand. XML parse failures abort publication; partial permission cannot skip corrupt files. Text retains all providers; peers differing in text are ambiguous. Official caches receive hash/XML/registration checks, not handwritten encoding/style lint.

## Local evidence scope

Verified SC2 5.0.17.98370, build bb10ee62e9cf3678dfa74233d5657757; engine SHA-256 c68202849f8e64ed20d15bea0fb89f2c5b94028d075d9848e124a8264d130222. The original toolbox x64 CascLib works with ANSI local reads.

[Engine evidence reader](../../tools/sc2_engine_dependencies.py) checks built-in chains, registration and standard-source collection. The GameData table at raw 0x3b99740 has 110 entries/24-byte stride; initialization handles 109 XML files then Assets.txt. Rules bind full engine/table/loop/call-range hashes. Combined with the [original component workflow](https://sc2mapster.github.io/mkdocs/setup/#41-basesc2datagamedata), this confirms static standard-source scope without inferring XML field merge order from table order.

It covers Cursor, DSP, Light, SoundMixSnapshot, Soundtrack and VoiceOver omitted by the toolbox's 54 candidates. Original files remain unchanged; custom spaces follow actual Includes. Broken refs, nonempty unknown XML, bad libraries/builds fail. Pure-data no-GUI confirmation needs retained complete CASC enumeration, no registrations and confirmed component relation together; ordinary local directories cannot borrow that exemption. These static facts are not Editor/game acceptance.
