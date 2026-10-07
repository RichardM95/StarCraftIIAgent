---
name: sc2-localization
description: StarCraft II localization files (GameStrings.txt, ObjectStrings.txt, TriggerStrings.txt) for the AeonOfIhanrii campaign. Use when adding or fixing player-facing text, Data Editor display names, trigger display names, or string anchors. Covers file formats, key conventions, XML anchor rules, and automated restoration via audit-gamestrings-anchors.py.
---

# SC2 Localization & String Anchors

## When to Use

Load this skill when the task touches any of the three localization files inside `<ModName>.SC2Mod/enUS.SC2Data/LocalizedData/`:

- `GameStrings.txt` — in-game visible text
- `ObjectStrings.txt` — Data Editor display text
- `TriggerStrings.txt` — Trigger Editor display names

Also load when the Data Editor shows blank names, wrong prefixes, or missing descriptions, or when fixing a reported UI text issue.

## Localization Files Overview

| File | Purpose | Key Format |
|---|---|---|
| `GameStrings.txt` | In-game visible text: button names, tooltips, upgrade names shown to the player | `Button/Name/ID=Text`<br>`Button/Tooltip/ID=Text`<br>`Unit/Tooltip/ID=Text`<br>`Upgrade/Name/ID=Text` |
| `ObjectStrings.txt` | Data Editor display text: editor names, prefixes, descriptions for all data objects | `Type/Name/ID=Name`<br>`Type/EditorPrefix/ID=Prefix`<br>`Type/EditorDescription/ID=Desc` |
| `TriggerStrings.txt` | Trigger Editor display names for Galaxy functions and triggers | `FunctionDef/Name/ID=Name`<br>`Trigger/Name/ID=Name` |

## ObjectStrings.txt Types Covered

`Abil`, `Actor`, `Behavior`, `Button`, `Effect`, `Model`, `Mover`, `Requirement`, `RequirementNode`, `Sound`, `Turret`, `Unit`, `Upgrade`, `Validator`, `Weapon`.

## Rule for New XML Entries

Whenever you create or override an XML catalog object that should be readable in the SC2 Data Editor, update `ObjectStrings.txt` in the same change. Add both `Type/EditorPrefix/ID=...` and `Type/Name/ID=...` for every new `id` in catalogs such as `AbilData.xml`, `UnitData.xml`, `ButtonData.xml`, `UpgradeData.xml`, `RequirementData.xml`, and `RequirementNodeData.xml`.

For player-visible text in `GameData.xml`, always add an explicit XML anchor:

```xml
<!-- UnitData.xml -->
<CUnit id="MyUnit">
    <Description value="Unit/Tooltip/MyUnit"/>
</CUnit>
```

```text
# GameStrings.txt
Unit/Tooltip/MyUnit=Player-facing unit description here.
```

Without an explicit XML anchor, the SC2 Editor may prune or fail to preserve player-facing localized text during save passes.

## Issue Intake Rule

Before changing UI text, identify the exact UI surface and its effective localization anchor:

- **World hover** — text shown when hovering an object in the game world
- **Selection panel** — text in the unit/structure selection panel
- **Command-card button** — `Button/Name/ID` and `Button/Tooltip/ID`
- **Tooltip** — `Unit/Tooltip/ID`, `Upgrade/Name/ID`, etc.
- **Editor text** — `Type/Name/ID` and `Type/EditorDescription/ID` in `ObjectStrings.txt`

Record the effective anchor before editing `GameStrings.txt` or `ObjectStrings.txt`.

## Automated String Restoration

When the SC2 Editor saves, it may normalize entries and migrate editor-facing text into `ObjectStrings.txt`. To ensure all referenced player-facing strings remain anchored in `GameStrings.txt`, run:

```powershell
python tools/audit-gamestrings-anchors.py --fill
```

This scans all `GameData/*.xml` files, checks against `GameStrings.txt`, and automatically populates missing keys from `ObjectStrings.txt`. Run it after every Editor save that touches catalog XML.

## Hard Rules

- **Edit localization files, not raw data XML, when the Data Editor shows blank/wrong text.** Player-facing text belongs in `GameStrings.txt`; editor display text belongs in `ObjectStrings.txt`.
- **Every new catalog `id` must get `ObjectStrings.txt` entries** in the same change — both `Type/Name/ID` and `Type/EditorPrefix/ID`. Otherwise the object shows blank in the Data Editor.
- **Player-facing text requires an explicit XML anchor** (`<Description value="Unit/Tooltip/..."/>`, `<Name value="Button/Name/..."/>`, etc.). Missing anchors cause the Editor to prune localized text on save.
- **Run `audit-gamestrings-anchors.py --fill` after every Editor save** that touches catalog XML, to restore pruned anchors.

## Reference

- `wiki/implementation/localization.md` — full localization file reference
- `tools/audit-gamestrings-anchors.py` — automated anchor restoration tool
- `wiki/implementation/xml-patterns.md` — XML authoring patterns that produce the anchor references
- `sc2-catalog-xml` skill — XML authoring rules that emit the anchors consumed here

## Chinese Task Knowledge (Merged)

Distilled from `references/localization.md`. Duplicates with sections above omitted.

### Locale Discipline
- Before writing text, inspect the target mod's existing locales (`enUS`, `zhCN`, etc.) and follow the project's convention. Do not assume `enUS` only, and do not migrate language based on the user speaking Chinese — confirm the runtime locale with the user first.

### Anchor Coverage Caveats
- The source example uses `enUS.SC2Data/LocalizedData/`; the actual task may target `zhCN` or another locale. Mirror the project's locale folders.
- `audit-gamestrings-anchors.py` currently hard-codes the `enUS` path and only scans direct `GameData/*.xml` anchors. `zhCN` and other languages plus indirect anchors need a separate manual check — a zero-error report does not prove all languages are complete.
- Editor may move editor-facing text into `ObjectStrings.txt`; that migration does NOT satisfy runtime references still pointing at `GameStrings.txt`. After save, run the anchor audit with explicit `--mod-dir`, restore with `--fill`, and manually review the actual copy.

### ObjectStrings Coverage Scope
- When adding a readable catalog object, sync `ObjectStrings.txt` name and project prefix for every relevant type — Actor, Model, Sound, Turret, Validator, and supporting Weapon, in addition to the obvious Unit/Ability/Button/Effect.

### Anchor Consumption Caveat
- `Name`, `Tooltip`, and `Description` field consumption varies by object — confirm against the field and current dependency before assuming which `GameStrings` key a catalog field reads.

## GameHotkeys and KSP CLI

These cover localization concerns not handled by `audit-gamestrings-anchors.py`.

### GameHotkeys.txt

Fourth localization file, alongside `GameStrings.txt` / `ObjectStrings.txt` / `TriggerStrings.txt`. Stores localized hotkey bindings and labels. Same `Key=Value` line format, UTF-8. Preserve hotkey intent and avoid locale changes that break expected shortcuts.

### Localization Editor SC2 KSP CLI

External tool for manual localization work and diagnostics. GitHub: <https://github.com/VoVanRusLvSC2/Localization-Editor-SC2-KSP>. CLI install path documented in [PR #1](https://github.com/VoVanRusLvSC2/Localization-Editor-SC2-KSP/pull/1/files).

If the user does not already have the tool installed, recommend installing it before bulk translation work. The desktop application is useful even without the CLI.

#### CLI Diagnostics

```powershell
sc2loc check-missing "C:\Maps\MyMap\enUS.SC2Data\LocalizedData\GameStrings.txt"
sc2loc check-missing "C:\Maps\MyMap\enUS.SC2Data\LocalizedData\GameStrings.txt" --json
```

Reports the following issue categories:
- missing locale files (sibling `xxXX.SC2Data` folders)
- missing keys compared across languages
- blank or `null`-like values
- malformed lines without `=`
- duplicate keys in one file
- read errors

Exit codes: `0` clean, `1` warnings/errors, `2` usage/input error, `3` unexpected runtime failure.

#### Localization Error Check/Fix Loop

When editing localization files, run this loop until clean:

1. Run `sc2loc check-missing <file>` (when CLI available).
2. Review by category — missing file, missing key, blank value, malformed line, duplicate key.
3. Fix the root cause in the text file, not the symptom.
4. Re-run the CLI and repeat until resolved.
5. If the CLI is unavailable, inspect sibling locale files manually and preserve key parity across languages.

If the user asks to fix localization errors, perform this workflow end-to-end rather than only describing it.

#### Common Text Fixes

- **Add a missing key:** `Unit/Name/MyUnit=My Unit`
- **Fix a blank value:** `DocInfo/PatchNote003=Fixed an issue where the unit icon was missing.`
- **Fix a malformed line:** ensure exactly one `=` per entry — `Unit/Name/MyUnit My Unit` → `Unit/Name/MyUnit=My Unit`
- **Remove duplicate keys:** keep one canonical entry per key, delete duplicates.

### Writing Guidance

- If the task is a translation of existing text, preserve source meaning, placeholders, markup, and tone.
- If the task requires brand-new localization text (not translating an existing string), ask the user for templates or reference examples first — tone and phrasing are project-specific.
- Good templates: existing keys from the same map/mod, a preferred faction voice, UI wording examples, tooltip patterns, or a comparable `GameStrings.txt` sample.
- If no template is available, state the text is a best-effort draft and keep wording neutral, concise, and SC2-style.

### Terminology Consistency

Prefer terminology consistency across `GameStrings.txt`, `ObjectStrings.txt`, and UI-facing strings. Use the localization tool for bulk translation but review machine-generated SC2 terminology manually.
