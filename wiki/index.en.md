# Wiki task router

[中文](index.md)
Read [workspace rules](../AGENTS.en.md). The local agent-config.json identifies the selected project. Initialize only on request with a primary Components path and tools/init-project.py.

- [Language and personal preferences](guides/agent-language.en.md).
- [Unified skill entry (English original)](../skills/sc2-project-entry/SKILL.md): one English technical skill tree, explained in the chosen language.
- Everyday development: [36 scenarios](guides/development-conversations.en.md), grouped by units, presentation, triggers, dialogue, persistence and validation.
- [18 skill scenarios and two multi-turn conversations](guides/skill-conversations.en.md): terrain, migration, official resources, MCP, model delegation and Harness2.
- [26 Terrain Module drawing scenarios and two multi-turn conversations](guides/terrain-conversations.en.md): reference selection, terrain painting, placement, pathing and continuation after Editor saves.
- [Tools](../tools/README.en.md); without a project run tools/test-suite.py --scope tools and --scope docs.
- Basic terrain drawing: [terrain tools and experiments](guides/sc2-terrain-editing.en.md), [terrain skill](../skills/sc2-terrain-editing/SKILL.md), [map adaptation and composition](../skills/sc2-terrain-editing/references/map-adaptation.md). Route mission objects and organization to [GUI adaptation](../skills/sc2-map-triggers/references/map-adaptation.md). Query the coverage ledger; unfinished operations remain visible.
- [Official CASC cache](reference/official-casc-cache.en.md).
- XML: [patterns (English original)](implementation/xml-patterns.md), [Catalog rules (English original)](implementation/xml-patterns/catalog-rules.md) (English technical references).
- Galaxy: [pitfalls (English original)](implementation/galaxy-gotchas.md), [language (English original)](reference/galaxy-language.md) (English).
- [Localization (English original)](implementation/localization.md) (English technical reference).
- Triggers: [queries](reference/trigger-knowledge.en.md), [in-game dialogue](reference/trigger-dialogue-examples.en.md), [user conversations](reference/trigger-agent-dialogue-examples.en.md), [GUI templates (Chinese original)](reference/trigger-templates/README.md) (original reference), [XML overview (English original)](reference/triggers-overview.md), [map wiring (Chinese original)](implementation/per-map-setup.md) (English).
- Bank: [contracts (Chinese original)](implementation/bank-system.md), [API (Chinese original)](reference/galaxy-bank.md) (English).
- [Initialization](guides/project-initialization.en.md), [feedback](implementation/testing-feedback-workflow.en.md), [Editor handoff](guides/editor-handoff.en.md).
- [Runtime diagnosis](implementation/runtime-diagnostics.en.md), [retrospective](../docs/agents/retrospective.en.md).
- [Project design location (Chinese original)](design/README.md) (Chinese original); [capability sources (Chinese original)](../DesignDocument.md) (original source).
- [Project data](../docs/agents/project-data.en.md), [issue template (Chinese original)](implementation/bug-reports/latest.md) (English).
- [Full inventory](catalog.en.md). Query DataEditorXML/ and triggers-native/ by specific ID rather than reading whole libraries.

- Unit migration: [chain analysis, source selection and safe import](guides/unit-migration.en.md).

- Shared tools and MCP: [setup, ownership and DeepSeek](guides/shared-tools.en.md), [routing skill](../skills/sc2-shared-tools/SKILL.md).
- Harness2: [project-local installation and recursion demo](guides/harness2.en.md).

<!-- translation-source: wiki/index.md; sha256: c75039108e71c432210397d1fe7b10b8159e21dc944953e044f1e61d4714b4a1 -->
