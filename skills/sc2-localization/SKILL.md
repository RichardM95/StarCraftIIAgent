---
name: sc2-localization
description: StarCraft II localization files (GameStrings.txt, ObjectStrings.txt, TriggerStrings.txt) for the selected project. Use when adding or fixing player-facing text, Data Editor display names, trigger display names, or string anchors. Covers file formats, key conventions, XML anchor rules, and automated restoration via audit-gamestrings-anchors.py.
---

# SC2 Localization & String Anchors

Load for localization-file changes, reported UI text issues, or blank names, wrong prefixes and missing descriptions in the Data Editor. This skill covers development-time keys, anchors and file-format diagnostics; whole-project translation is outside this workspace.

## Files and Reference

Localization files live in `<ModName>.SC2Mod/<locale>.SC2Data/LocalizedData/`.

| File | Purpose and key examples |
|---|---|
| `GameStrings.txt` | Player-visible text: `Button/Name/ID`, `Button/Tooltip/ID`, `Unit/Tooltip/ID`, `Upgrade/Name/ID` |
| `ObjectStrings.txt` | Data Editor text: `Type/Name/ID`, `Type/EditorPrefix/ID`, `Type/EditorDescription/ID` |
| `TriggerStrings.txt` | Trigger Editor names: `FunctionDef/Name/ID`, `Trigger/Name/ID` |
| `GameHotkeys.txt` | Localized hotkey bindings and labels; UTF-8 `Key=Value` lines. Preserve intended shortcuts across locales. |

Use [localization.md](../../wiki/implementation/localization.md) for the authoritative file reference and surface-to-anchor mapping. XML authoring belongs to [xml-patterns.md](../../wiki/implementation/xml-patterns.md) and the `sc2-catalog-xml` skill.

## Intake and Restoration Workflow

1. Identify the exact surface before editing: world hover, selection panel, command-card button, tooltip or editor display. Record its effective localization anchor. Confirm field consumption against the object and current dependency: `Name`, `Tooltip` and `Description` do not consume keys uniformly. An imported diagnostic does not replace this investigation.
2. Inspect the target mod's existing locale folders and project convention. Use the requested runtime locale; if it is unresolved, confirm it with the user before writing. Neither an `enUS` example nor the user's language selects the locale or authorizes migration.
3. Fix localized values in the appropriate text file when Data Editor text is blank or wrong: player-facing values belong in `GameStrings.txt`, editor display values in `ObjectStrings.txt`. Do not substitute a raw XML text edit for a localization fix.
4. After every Editor save touching catalog XML, inspect the audit tool's current `--help`, then run restoration against the actual target and locale:

   ```powershell
   python tools/audit-gamestrings-anchors.py --mod-dir "<target>" --locale <actual-locale> --fill
   ```

   The tool scans `GameData/*.xml`, checks referenced keys in `GameStrings.txt`, and fills missing values from `ObjectStrings.txt`. Editor migration into `ObjectStrings.txt` does not satisfy runtime references still reading `GameStrings.txt`.
5. Reopen and review the actual target copy after restoration; a successful write alone does not verify its contents. Review indirect runtime references separately. A zero-error static report does not prove packaged runtime coverage; retain the evidence-stage distinctions required by `AGENTS.md`.

## Catalog Changes and Anchors

For each new or overridden catalog object intended to be readable in the Data Editor, keep `Type/Name/ID` and the project's `Type/EditorPrefix/ID` synchronized in `ObjectStrings.txt` in the same change. Coverage includes `Abil`, `Actor`, `Behavior`, `Button`, `Effect`, `Model`, `Mover`, `Requirement`, `RequirementNode`, `Sound`, `Turret`, `Unit`, `Upgrade`, `Validator` and `Weapon`, including supporting objects.

Player-visible text requires an explicit XML anchor, for example:

```xml
<CUnit id="MyUnit">
    <Description value="Unit/Tooltip/MyUnit"/>
</CUnit>
```

```text
Unit/Tooltip/MyUnit=Player-facing unit description here.
```

Without an explicit anchor, Editor save passes may prune or fail to preserve localized player text. Follow the XML references above when authoring anchors; run restoration after the save as described in the workflow.

## Optional KSP Diagnostics

[Localization Editor SC2 KSP](https://github.com/VoVanRusLvSC2/Localization-Editor-SC2-KSP) is an optional existing desktop diagnostic, not a replacement for anchor restoration. CLI installation is documented in [PR #1](https://github.com/VoVanRusLvSC2/Localization-Editor-SC2-KSP/pull/1/files).

When the CLI is available:

```powershell
sc2loc check-missing "<target>/<locale>.SC2Data/LocalizedData/GameStrings.txt" --json
```

`--json` is optional. Diagnostics cover missing sibling locale files, cross-language missing keys, blank or `null`-like values, malformed lines without `=`, duplicate keys and read errors. Exit codes: `0` clean; `1` warnings/errors; `2` usage/input error; `3` unexpected runtime failure.

For localization-error fixes, perform the workflow end-to-end: inspect categories, correct their causes in the text files, and rerun after corrections until resolved. If the CLI is unavailable, manually inspect sibling locale files and preserve key parity across languages.

When fixing lines, split at the first `=` and preserve subsequent `=` characters in the value. Keep one canonical entry per key when removing duplicates.

## Text Preservation and Writing

- Preserve source meaning, placeholders, markup and tone when translating existing text. Keep terminology consistent across localization files and UI-facing strings.
- Before creating new text, ask for project templates or reference examples: nearby keys, faction voice, UI wording, tooltip patterns or comparable strings. If none are available, identify the text as a best-effort draft and use neutral, concise SC2-style wording.
