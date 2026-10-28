---
name: sc2-terrain-editing
description: Create and adapt StarCraft II Components maps with sc2-terrain tools, including terrain, objects, pathing and scene composition. Use for drawing, expansion or visual refinement; check scoped write, Editor and runtime evidence for each operation.
---

# SC2 Terrain Editing

Use the workspace's [SC2 entry](../sc2-project-entry/SKILL.md), then the [usage guide](../../wiki/guides/sc2-terrain-editing.md) or its English link. Explain technical material in the user's language. The map argument, not the currently selected mod, identifies the actual editing target.

Use this skill for practical basic map drawing from a reference copy. It includes placing/removing/moving units, doodads and regions, plus creep, roads, foliage, lighting and visibility painting. Full Editor parity and exhaustive menu/property reproduction are optional extensions. Preserve existing ramps/pathing when a requested new operation lacks a writer; disclose that limitation instead of substituting preview output for an edit.

For campaign expansion, scene polishing, bridges or tunnel connections, read [map adaptation and composition](references/map-adaptation.md) before changing the layout. It covers choosing the latest saved baseline, reserving circulation, arranging substantial scenery and separating visual from traversal evidence. For mission objects or GUI organization, continue with [sc2-map-triggers](../sc2-map-triggers/SKILL.md); terrain placement alone does not implement the mission behavior.

## Choose the next action

1. Run `python tools/sc2-terrain.py --ui-language <language> capabilities`. `active_requirement` identifies basic drawing requirements; the remaining full-module inventory is an optional backlog. `experimental` requires checking the separate scoped Editor evidence; `editor_issue_reported` requires diagnosis before normal use; `diagnostic` does not imply native rendering or runtime pathfinding.
2. For a supplied reference root, `scan --audit --output <report.json>` distinguishes Components directories from archives and checks supported binary roundtrips. Modified campaign maps are reference evidence, not pristine Blizzard originals or proof of active dependencies. Inspect a bounded shortlist and query each chosen map's actual dependencies.
3. Use `inspect`, `select`, `measure` and `render` to relate layout to real world coordinates. Read [format evidence](references/formats.md) when interpreting binary fields; read [case observations](references/cases.md) when selecting learning samples. Preview height and paint overlays are diagnostic reconstructions.
4. For supported edits, write an explicit operations JSON using the [operation contract](references/operations.md). Generate a hash-bound `plan`, inspect changed components and warnings, preview `apply`, then apply to a separate workspace `.SC2Map`. These steps are implementation work, not a reason to ask for redundant authorization.
5. Run `audit` and `diff` on the actual output. Test `undo`/`redo` when changing history behavior. Preserve map/script identities and typed references. Referenced object/region deletion is refused; start-location creation and arbitrary reference remapping need dedicated support.
6. For unsupported semantics, use `experiment` to produce baseline/working copies for one named capability. The Editor operator saves without editing and closes the map; `experiment-baseline` captures normalization. Then perform one operation, record parameters, save/close/reopen; `experiment-compare` identifies the coordinated change. The agent may operate the Editor when authorized and UI control is verifiably working; ask the user only for unavailable actions. Implement and test the learned rule before marking it writable. A raw byte patch or a tutorial is not full feature implementation.

Before extending an accepted operation or diagnosing an Editor difference, read the [scoped Editor evidence](references/editor-evidence.md). It distinguishes tool-generated acceptance from manual experiments and records migration confounders.

When placing or moving units/doodads, choose facing from the layout: guards face approaches, formations share a direction, and walls/pipes follow their intended axis. Use absolute `Rotation` or `face_towards` for rotation in place; `angle` rotates positions around a pivot too. Verify model-specific forward direction and symmetric assets in the Editor. For static blocking scenery, use `doodad-blockers` with actual occupancy evidence and reserved routes; its owned contributions automatically follow subsequent object edits. Native movable/destructible blockers keep their native behavior. Read the [placement and pathing rules](references/operations.md#placement-and-pathing) before adding paint; arbitrary model footprint inference is unsupported.

Check doodad height mode as well as XY. Absolute-height doodads preserve their terrain-relative offset on offset moves/copies and XY alignment. Use `grounding:"snap"` for terrain contact or correcting burial; explicit XYZ placements retain their supplied Z by default. Keep authored bridge/elevated placements with `grounding:"keep-z"`; terrain sampling does not decode platform surfaces or mixed cliff geometry.

## Source and completion boundaries

- External campaign sources and `publish/` remain read-only. New outputs live in the workspace; continued edits require a tool-owned working copy. The tool refuses changed input hashes, links/junctions, unowned outputs and stale history. Preserve surviving stage/journal/backup directories if recovery fails.
- Keep an affected map closed during external writes. Reuse actual operator save/reopen evidence until that map changes. When UI input is ineffective (including a suspected elevation mismatch), do not report a successful click as an accepted edit; request only the necessary manual step. Never hand-edit generated `MapScript.galaxy`, library output or the component manifest to make an experiment load.
- Height, texture and topology have companion simulation data. Preserve unknown fields and unchanged channels. Successful parsing alone cannot prove that a cliff, ramp or pathing edit works.
- After Editor save, follow the selected map's localization/anchor workflow with explicit target and locale. Do not restore anchors before capturing an experiment's raw Editor-save differences; keep that restoration separately identified.
- Report the applicable exact lifecycle label. Static tooling can reach `static validation passed`; user open/save/reopen evidence establishes `Editor accepted` only for the tested artifact/action. `packaged runtime passed` requires the packaged map's scenario and result. Judge basic drawing against active requirements; optional full-module gaps do not expand a user's request.
