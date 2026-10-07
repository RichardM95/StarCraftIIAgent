# Localization Files

## Localization Files Overview

| File | Purpose | Key Format |
|---|---|---|
| `GameStrings.txt` | In-game visible text: button names, tooltips, upgrade names shown to the player | `Button/Name/ID=Text`<br>`Button/Tooltip/ID=Text`<br>`Unit/Tooltip/ID=Text`<br>`Upgrade/Name/ID=Text` |
| `ObjectStrings.txt` | Data Editor display text: editor names, prefixes, descriptions for all data objects | `Type/Name/ID=Name`<br>`Type/EditorPrefix/ID=Prefix`<br>`Type/EditorDescription/ID=Desc` |
| `TriggerStrings.txt` | Trigger Editor display names for Galaxy functions and triggers | `FunctionDef/Name/ID=Name`<br>`Trigger/Name/ID=Name` |

---

## ObjectStrings.txt Types Covered

`Abil`, `Actor`, `Behavior`, `Button`, `Effect`, `Model`, `Mover`, `Requirement`, `RequirementNode`, `Sound`, `Turret`, `Unit`, `Upgrade`, `Validator`, `Weapon`

---

## Rule for New XML Entries

Whenever you create or override an XML catalog object that should be readable in the SC2 Data Editor, update `ObjectStrings.txt` in the same change. Add both `Type/EditorPrefix/ID=...` and `Type/Name/ID=...` for every new `id` in catalogs such as `AbilData.xml`, `UnitData.xml`, `ButtonData.xml`, `UpgradeData.xml`, `RequirementData.xml`, and `RequirementNodeData.xml`.

For player-visible text in `GameData.xml`, always add explicit XML text anchors:

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

---

## Automated String Restoration

`audit-gamestrings-anchors.py` accepts `--locale` (default `enUS`). Niadra has `zhCN` localization; use `python tools/audit-gamestrings-anchors.py --mod-dir "../StarCraft II/Mods/Niadra.SC2Mod" --locale zhCN`, and add `--fill` after Editor save. Do not create an English directory merely to satisfy the default audit. Niadra's current migration status and pre-existing anchor omissions are recorded in the naming contract.

When the SC2 Editor saves, it may normalize entries and migrate editor-facing text into `ObjectStrings.txt`. To ensure all referenced player-facing strings remain anchored in `GameStrings.txt`, run:

```powershell
python tools/audit-gamestrings-anchors.py --fill
```

This scans all `GameData/*.xml` files, checks against `GameStrings.txt`, and automatically populates missing keys from `ObjectStrings.txt`.
