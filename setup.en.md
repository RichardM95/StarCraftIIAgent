# Installation and setup — custom campaign agent starter

[中文](setup.md)
<!-- translation-source: setup.md; sha256: 5434091efb7e13d0bdf0849eadab482480a0b31433b0c9625b5a7c558c4cda45 -->

**Author: 扯蛋虾米.** See [AUTHORS](AUTHORS.en.md). Local agent-config.json determines whether a project is selected. Open this independent StarCraftIIAgent workspace; verify current configuration/source rather than assume a historical campaign.

## Quick-start checklist

A fresh Git clone contains generic skills, source and references, without the maintainer's `projects/`, local `agent-config.json`, environments, credentials, indexes or model-task records. Run tools/docs checks first and initialize your own project. Do not copy another machine's selected-project configuration to compensate for these absent local files.

See [skill conversations](wiki/guides/skill-conversations.en.md) for new capabilities and expected evidence. Rebuild shared CLI/MCP environments and register local entries using [shared-tool setup](wiki/guides/shared-tools.en.md); delegation additionally needs your local Harness/provider configuration. Optional [Harness2 setup](wiki/guides/harness2.en.md) rebuilds Linux/WSL dependencies. Registration, actual model connectivity, execution, static checks, Editor acceptance and runtime acceptance are separate results.

1. Make Python and the installed SC2 Editor available for their respective operations; use a host with local workspace/tool access. Read AGENTS.md, wiki/index.md and skills/sc2-project-entry/SKILL.md.
2. Choose [UI language](wiki/guides/agent-language.en.md). `python tools/agent-language.py --set en` saves English; --set zh-CN fixes Chinese; --set auto restores automatic selection. UI language never changes SC2 --locale.
3. Create/open the mod in the Editor, select intended dependencies and save as Components. Provide the real primary folder for initialization.
4. Have the agent run tools/init-project.py, verify actual identity/source/dependencies, and run relevant checks.
5. Save project design facts to project docs/design/ and provenance to docs/sources.md, located using tools/project-paths.py. Suite wiki/ keeps reusable rules only.
6. Build only the required Catalog SQLite; implement a small verified change, check it, then follow Editor/game handoff.

## Copyable conversations

Replace placeholders with actual paths/inputs. Expected behavior is guidance, not completed acceptance evidence.

| Request | Expected action/boundary |
|---|---|
| “My primary Components mod is `E:\Program Files (x86)\StarCraft II\Mods\MyCampaign.SC2Mod`. Run tools/init-project.py, recursively check dependencies, update agent-config.json and verify identity/config. Do not ask for manual JSON editing or infer dependencies by listing Mods.” | Initialize directly; ask for extra paths only when standard inference fails. |
| “Preview `D:\SC2\Mods\MyCampaign.SC2Mod` with --dry-run. Show paths, primary and missing dependencies without config writes.” | Read-only preview; preserve old config. |
| “Switch to `D:\StarCraft II\Mods\AnotherCampaign.SC2Mod`; validate dependencies and check Campaign, Library ID, Compiled Galaxy, Script Block, Bank and prefixes from evidence.” | Reinitialize; report inconsistent identity rather than reuse it. |
| “Temporarily inspect `D:\StarCraft II\Mods\Experimental.SC2Mod` using test-suite.py --mod-dir; do not change config. Report actual target and dependency scan scope.” | Keep external checks separate from selected project. |
| “Nonstandard layout: primary `D:\Projects\MyCampaign.SC2Mod`, Mods `D:\SC2Data\Mods`, install `C:\Games\StarCraft II`, maps `D:\SC2Data\Maps\Campaign`. Initialize with explicit directory flags only after validation.” | Validate recursive dependencies before writing. |
| “I only have a mod in the Editor. Explain saving Components and which path to provide; do not guess config.” | Give user Editor steps, wait for source. |
| “Read AGENTS.md and wiki/index.md, locate local skills/tools and check whether a project is selected. Read-only.” | Separate suite installation from project state; never choose an arbitrary mod. |
| “Check Python/rules/skills/wiki/tools and applicable tools/docs scopes. Don't initialize a project or install software.” | Suite checks work without a project; Editor saves remain operator actions. |
| “Show primary mod, actual editing source, source_mode, Mods, maps and project data paths read-only; distinguish source/copy/deployment.” | Resolve config; report absence without changing it. |
| “I have no mod yet. Plan Editor creation, dependencies and Components save based on `<Wings of Liberty / Heart of the Swarm / Legacy of the Void / specific dependency>`. Wait for a real folder before initialization.” | Presence of libraries on disk does not prove loading. |
| “Initialization reports `<dependency-reference>`; here is `<output>`. Diagnose declarations, manifest and paths. Don't hide it with --allow-incomplete or add dependencies.” | Identify exact missing evidence; failure preserves config. |
| “Primary moved to `<new-Components-path>` from `<old-path>`. Reinitialize/verify then update config; preserve old contents/uncommitted work.” | Re-resolve; never delete old source or infer new availability from old indexes. |
| “Workspace is on `<workspace-directory-on-drive-A>`, primary mod on `<standard-Mods-path-on-drive-B>`. Initialize and check relative/cross-drive paths; identify machine-specific settings.” | Do not require moving both to one drive or hard-code machine paths into skills/source. |
| “Initialize `<Components-path>` with --project-data-dir `<project-data-directory>`. Explain docs/runtime without creating empty data trees.” | Keep project facts outside suite wiki/ and Components. |
| “Primary deployment is `<deployment-directory-under-Mods>`; edit `<development-copy-directory>`. Check both, set workspace_copy/source_mod and verify direction. Preserve both; no deployment. Missing copy must not fall back.” | Use current config contract; do not invent unsupported CLI flags or ask users to guess fields. |
| “Edit `<primary-mod-components-path>` in place without a copy. Confirm source_mode/identity and validate config.” | Verify in_place before editing; never confuse publish/deployed copies with source or copy unnecessarily. |
| “Read-only inspect `<map.SC2Map>`, Mods `<directory>`, Campaigns `<directory>`. List actual libraries/paths/gaps without changing default project.” | A map-local function does not become a mod definition. |
| “Build an external reference trigger index from `<SC2GameData-Mods-root>` and `<Campaigns-root>`. Explain definitions/cases/metadata gaps. No project selection, official source edits or full-library copying.” | Registration alone is not loading evidence. |
| “Project is initialized; verify dependencies and build only SQLite Catalog queries. Report actual input/gaps, preserve old index on failure.” | No unnecessary full reports or fabricated completeness. |
| “Ingest `<content-or-attachment>` into selected project docs/design/, with sources in docs/sources.md. Mark undecided choices; don't overwrite suite DesignDocument.md.” | Confirm material design choices separately. |
| “Plan the smallest verifiable `<specific-small-mechanism>` after reading existing source, with inputs and Editor/game scenarios. No edits or unrelated refactors yet.” | Ask for concrete missing objects/resources, not all material again. |
| “Implement the agreed `<mechanism>` in actual source, preserve uncommitted work, check references/parameters/strings/static rules; no deployment. Give Editor/game steps.” | Complete authorized source work; highest static gate is static validation passed. |
| “Static source checks passed. List exact Editor components and reload/save checks for GUI/objects/generated calls and string anchors. Don't record Editor accepted yet.” | Avoid wrong deployed copy or original map under override. |
| “In Editor `<version>`, I reloaded/saved `<actual-target>` with `<observed-behavior>`. Before/after files `<path>`, compile evidence `<path>`. Check whether Editor accepted is justified.” | Compare structure/generated calls; Editor success does not prove packaged runtime. |
| “Package `<source-version-and-packaging-method>`; steps `<actions-performed>`; result `<observed-behavior>`; logs/video `<path>`. Coverage `<details>`. Update actual issue state and untested cases.” | Only supported packaged scenarios reach packaged runtime passed; absence of visible errors does not certify everything. |

### Multi-turn: investigate, then execute

**User:** “Here is the primary Components mod `<path>`. Preview initialization only.”

**Agent:** Runs --dry-run and reports inferred paths and real dependency gaps.

**User:** “I've supplied the missing inputs. Initialize, then query `<unit-id>` without editing it.”

**Agent:** Revalidates, writes configuration, then queries effective values/providers. Initialization permission does not authorize unit edits.

**User:** “Set base health to 120 based on that evidence and run static checks; don't deploy.”

**Agent:** Edits actual source, validates and reports precise acceptance steps.

### Multi-turn: runtime failure after static success

**User:** “Editor reload/save worked; here are before/after files.”

**Agent:** Checks structure/generated calls before recording Editor accepted.

**User:** “In the package, the button appears but clicking doesn't enter the branch. Logs: `<path>`.”

**Agent:** Investigates actual package, event player, saved control handles and branch state; preserves failure evidence and repairs editable source.

**User:** “Here is video of normal/repeated clicks after repackaging the same version.”

**Agent:** Updates only supported coverage; timeout/multiplayer remain untested if absent.

## Workspace and Editor steps

For everyday requests, see [36 development scenarios](wiki/guides/development-conversations.en.md). See [README structure](README.en.md#repository-and-routing) and [initialization](wiki/guides/project-initialization.en.md). The suite contains local rules/skills/tools/wiki/exports; project source lives under configured Mods or explicit editing copy, project docs/runtime beside the project, publish/ only for packaging.

1. Existing Components: run `python tools/init-project.py "<primary.SC2Mod>"`; verify identity from Triggers/config. New mods: create in the Editor, select correct dependencies, save Components and provide path. Do not invent IDs/Bank names.
2. Save mods as Components, preserving hand-written versus generated source. Map → Modules → Dependencies adds the intended mod. Never open Blizzard maps with project mod external override active.
3. Save campaign maps as Components under the configured maps path. Terrain/regions/doodads/pathing/cinematics need Editor work. Packaged archives are directly readable; explicit tools/sc2-archive.py converts them separately, without automatic conversion by queries.
4. Build `python tools/build-sc2-catalog-graph.py --ui-language en --sqlite-only` for query use; omit --sqlite-only only when full reports are needed. Project default query indexes refresh on demand; explicit indexes/--no-auto-rebuild remain read-only. --locale is data language; missing dependencies are not silently waived.
5. Use tools/test-suite.py --scope tools and --scope docs for suite maintenance, --scope mod for relevant actual component validation. Actual dependency/source scans follow config/explicit overrides; report scope and blockers. A passing subset cannot certify a blocked full check.
6. Follow [Editor handoff](wiki/guides/editor-handoff.en.md) and [feedback](wiki/implementation/testing-feedback-workflow.en.md). Close affected documents before external edits, compile/save dependencies before dependents, inspect generated calls read-only and separate fresh starts/old saves/transition tests. Static validation is at most static validation passed.

For support, include actual target/config scope, tool command/output, Editor version and reproducible evidence; do not substitute historical example IDs for project identity. CCM community use follows the attribution/licensing files supplied with the suite.
