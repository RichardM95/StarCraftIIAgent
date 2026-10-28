---
name: sc2-editor-handoff
description: StarCraft II Editor handoff workflow and issue lifecycle for the selected project. Use after code/XML changes to verify Editor acceptance, save as Components, run playtests, and track defects through the 6-stage lifecycle. Covers what the agent can and cannot do in the SC2 Editor.
---

# SC2 Editor Handoff

Use after source changes to coordinate Editor regeneration and runtime verification. Follow the relevant sections of the [handoff checklist](../../wiki/guides/editor-handoff.md); provide only steps affected by this change.

## Evidence and status

The [feedback workflow](../../wiki/implementation/testing-feedback-workflow.md) owns lifecycle gates and evidence fields. Static checks cannot establish Editor or runtime acceptance. Keep unresolved symptoms separate from candidate-patch validation; record durable defects in the selected project's ledger using the [issue rules](../../docs/agents/issue-tracker.md).

## Source protection

- Edit the configured source and respect `in_place` versus `workspace_copy`. Only deploy a copy after checking the dry-run destination.
- Close affected Editor documents before external edits and retain a backup. Reuse the user's closure confirmation while it remains valid.
- Reload, compile and save Components in the Editor using authorized, verifiably available GUI control, or hand off necessary unavailable steps to the user; only the Editor regenerates `Lib*.galaxy` and `MapScript.galaxy`. Those files are read-only evidence.
- Before interpreting a retest, follow [source-to-runtime verification](../../wiki/guides/editor-handoff.md#源码到运行时的核对): verify the generated actions, variable declarations, event registration and initialization order.
- Never open Blizzard maps with the project mod active as an external override. Verify the map's actual dependencies.
- After an Editor save, audit string anchors for the explicit target/locale; use `--fill` only for the intended restoration and review its diff.

For terrain, map expansion, scene composition and bridge/tunnel connections, [sc2-terrain-editing](../sc2-terrain-editing/SKILL.md) owns the explicit map target, supported operations, controlled experiments and scoped Editor/runtime evidence. Follow its evidence procedure before restoring anchors; folder persistence or compilation does not establish appearance, passage or mission acceptance. Cinematics require an actual Editor workflow.
