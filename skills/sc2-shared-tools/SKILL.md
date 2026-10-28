---
name: sc2-shared-tools
description: Route SC2 tasks between existing workspace tools and the shared CLI/MCP for official assets, editor warnings, map shells, candidate transactions and bounded DeepSeek work.
---

# Shared SC2 tools

Load [project entry](../sc2-project-entry/SKILL.md). Read the [integration guide](../../wiki/guides/shared-tools.md) or its English link for setup, exact commands, JSON arguments and state ownership.

Existing Catalog effective-value queries, GUI triggers, localization anchors, terrain and migration tools remain the default. Use the imported shared implementation for supplementary resources, source-context/asset audits, shell/region diagnostics, warnings and transactional candidates. Query its current `tools` schema instead of inventing parameters.

For supplementary operations, use connected `sc2-editor` MCP tools; if unavailable, run `python tools/sc2-local.py --ui-language <language> call <operation> --arguments-file <file>`. Both use the same dispatcher, validation and project state. Keep one transaction entry for the task. Business errors need diagnosis; do not change transport to bypass a guard. On an uncertain submission, inspect existing task/change IDs before repeating it.

Open an explicit target with `writable=false` for investigation; the returned project_id identifies that target. Authorized edits use its actual configured editing source and `writable=true`. The global entry never silently selects LoyalWOL for another workspace. Generated Galaxy and publish source edits are blocked even through batches and candidate application.

- Terrain, map expansion and scene composition: load [sc2-terrain-editing](../sc2-terrain-editing/SKILL.md) and use its current local tool contract for the explicit map. Mission-object wiring and GUI organization also load [sc2-map-triggers](../sc2-map-triggers/SKILL.md).
- Official resources: load [sc2-official-assets](../sc2-official-assets/SKILL.md).
- DeepSeek sub-tasks: load [sc2-deepseek-tasks](../sc2-deepseek-tasks/SKILL.md).
- Review candidates and source hashes before applying; use the existing domain validators on the actual output. Report the exact applicable lifecycle status; a connected tool, completed worker, static pass, Editor acceptance and packaged runtime result are separate evidence.
