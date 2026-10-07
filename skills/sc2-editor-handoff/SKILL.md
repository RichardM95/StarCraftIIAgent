---
name: sc2-editor-handoff
description: StarCraft II Editor handoff workflow and issue lifecycle for the AeonOfIhanrii campaign. Use after code/XML changes to verify Editor acceptance, save as Components, run playtests, and track defects through the 6-stage lifecycle. Covers what the agent can and cannot do in the SC2 Editor.
---

# SC2 Editor Handoff & Issue Lifecycle

## When to Use

Load this skill after making source changes (XML, Galaxy, triggers) to verify SC2 Editor acceptance, coordinate the user's Editor save, and track issues through the required lifecycle.

## 6-Stage Issue Lifecycle (mandatory)

Every reported bug or defect must follow:

```text
reported → root cause confirmed → source fixed → static validation passed → Editor accepted → packaged runtime passed
```

1. **`reported`**: Recorded in `wiki/implementation/bug-reports/latest.md` with: map/mission, player/faction config, observed vs expected behavior, exact Editor warning or in-game error (from `bugreport.txt`).
2. **`root cause confirmed`**: Root catalog ID, parent inheritance flaw, or Galaxy logic error identified.
3. **`source fixed`**: Working-tree source files updated.
4. **`static validation passed`**: `python tools/test-suite.py` runs with zero errors.
5. **`Editor accepted`**: SC2 Editor opens modified mod/map cleanly — no XML schema warnings, missing dependency errors, or trigger compile failures.
6. **`packaged runtime passed`**: Change tested and verified in-game.

> A clean static test suite does NOT advance an issue past the Editor gate.

## What the Agent CANNOT Do (requires SC2 Editor GUI)

- Opening and saving Blizzard maps (requires SC2 account login)
- Terrain, regions, doodads, pathing
- Cutscenes and cinematics
- Saving mod/map as Components (user action)

These steps must be performed by the user. The agent prepares everything and provides a precise handoff checklist.

## Editor Handoff Checklists

### After Galaxy Script Changes

1. In `workspace_copy` mode, preview and copy the component mod with `python tools/deploy-mod.py --dry-run` followed by deployment; in `in_place` mode, skip deployment.
2. User opens `<ModName>.SC2Mod` in SC2 Editor and verifies the intended custom script block/include in the Trigger Editor.
3. Compile triggers → **File → Save** mod as **Components**; only the Editor regenerates `Lib*.galaxy`.

### After Mod XML / Trigger GUI Changes

1. User opens `<ModName>.SC2Mod` in SC2 Editor.
2. Review XML warnings in the editor output panel; resolve catalog type/ID issues before saving.
3. **File → Save** mod as **Components**.
4. If map `Triggers` XML was edited directly in repo, reopen affected `.SC2Map` in Editor and save as Components so `MapScript.galaxy` regenerates cleanly.
5. After save: run `python tools/audit-gamestrings-anchors.py --fill`.

### After Map Component Changes

1. User opens the map under configured `paths.campaign_maps_dir/<Category>/<MapName>.SC2Map/` in SC2 Editor.
2. Confirm **Modules → Dependencies** includes `<ModName>.SC2Mod`.
3. **NEVER** open Blizzard maps with the project mod active as an external override (loads modded version instead of vanilla).
4. **File → Save** map as **Components**.

### After Playtesting

1. Run `python tools/extract-playtest-bugreport.py` to extract runtime alerts/errors.
2. Triage per the issue lifecycle.
3. Log defects in `wiki/implementation/bug-reports/latest.md`.

## Issue Intake Rules

- **Statistic changes:** Before editing XML statistics, record local catalog entry, parent, inherited value, and intended override.
- **UI & text fixes:** Identify the exact UI surface (world hover, selection panel, command card button, tooltip, or editor text) and its effective localization anchor before modifying `GameStrings.txt` or `ObjectStrings.txt`.
- **Runtime logs:** Run `python tools/extract-playtest-bugreport.py` after playtest to extract `Alerts.txt` and `ScriptError.txt` into `bugreport.txt`.

## Ledger Maintenance

- Active ledger: `wiki/implementation/bug-reports/latest.md`
- Keep the active ledger concise.
- Move durable system facts to canonical topic pages rather than retaining long historical discussions.

## Editor Safety Rules

- **NEVER open maps with the project mod active as an external override** — loads modded version instead of vanilla.
- **Adding dependency:** Map → Modules → Dependencies → `<ModName>.SC2Mod`.
- After Editor save, run localization audits to restore pruned string anchors.

## Reference

- `wiki/guides/editor-handoff.md` — Editor handoff checklist
- `wiki/implementation/testing-feedback-workflow.md` — issue lifecycle & triage
- `wiki/implementation/bug-reports/latest.md` — active issue ledger
- `wiki/reference/editor-guide.md` — SC2 Editor workflow notes
- `wiki/guides/simulated-bank-playtests.md` — simulated bank playtest setup
