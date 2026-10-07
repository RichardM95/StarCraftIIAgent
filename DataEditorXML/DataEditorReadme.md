# DataEditorXML — Field Name Reference

> **This file is a pointer.** Full content is at `wiki/reference/data-editor-xml.md`.

This folder contains XML dumps extracted from the SC2 Data Editor. Grep these `.txt` files before writing any XML — field names are case-sensitive.

**Rule:** Grep these files before writing any XML. Do not guess field names.

This folder does not contain every SC2 data source. It includes selected dumps from **Wings of Liberty**, **Heart of the Swarm**, and **Legacy of the Void** campaign/mod layers, with the current file index maintained in `wiki/reference/data-editor-xml.md`.

`SC2GameDataComponents/` contains a path-preserving reference snapshot from 26 official and partner `.SC2Mod` / `.SC2Campaign` component folders. It includes each component's available `Base.SC2Data/GameData/`, `enUS.SC2Data/`, and `zhCN.SC2Data/` content. Some top-level `.txt` dumps duplicate these raw XML files. Query the catalog graph first; use `python tools/sc2-reference-query.py find <term> --family <Family> --limit 20` only when a component-level implementation example or localization is needed. See `SC2GameDataComponents/README.md` for scope and usage boundaries.

Inactive StarCoop, NovaStory/Nova, and Mengsk exports live in `XMLFromDependenciesWeDontUse/`, including model and sound catalogs for selective unit extraction. See `XMLFromDependenciesWeDontUse/README.md` and `wiki/reference/unit-extraction-from-inactive-xml.md`.
