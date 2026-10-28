# Adapting and composing an existing map

Use for campaign expansion, an empty-looking scene, material integration, or a bridge/tunnel connection. The [operation contract](operations.md) owns supported JSON operations; [Editor evidence](editor-evidence.md) owns acceptance. This page guides layout decisions rather than introducing new writers.

## Establish the working baseline

Start from the user's latest saved working map. Record its component hashes, active dependencies, dimensions, origin, camera/playable bounds and referenced object/region IDs. Preserve the original reference and protect the current saved map from an old build manifest. An Editor save may normalize XML, requantize heights, regenerate companions and replace scripts; resume from that saved result, not an earlier cached terrain recipe.

Distinguish total map dimensions from playable and camera bounds. Prefer fitting the route and functional spaces in the existing canvas; expand the needed edges when there is a spatial reason. Preserve the requested coordinate origin and verify that old units, regions and cinematic cameras still refer to the same locations. Symmetric expansion is a design choice, not a requirement.

**Ready to edit:** identify the actual saved input and output, protected story references, route connections, terrain palette and supported operations. A modified community map is a reference with its own dependencies, not a pristine official source.

## Shape the route before dressing it

Describe entrances, combat spaces, side courtyards, equipment access and exits in world coordinates. Make optional objectives reachable before any main-objective cutoff that would end them. Treat a requested mountain wall or tunnel entrance as a layout constraint; a convenient extra corridor can otherwise invalidate the intended space.

Build or preserve the continuous floor and required slope/bridge connections first. Reserve road width, turning room, deployment surfaces and device approaches. Express clearance as space outside the object footprint, not distance between object centers. Use the intended largest traveler as well as infantry when reviewing a route. A project's approximate 8–10-cell main route and 4–6-cell branch are local design targets, not universal SC2 pathing thresholds.

If a supported topology operation cannot express a connection, follow the controlled experiment procedure in the entry skill. Keep the unfinished connection explicit rather than substituting a smooth height bump, a teleport or a pathing overlay for the requested terrain.

**Layout check:** trace every required route, identify each level change, and keep task access and optional branches clear of placed footprints. Static tracing is an intermediate result; native travel remains a separate check.

## Fix emptiness with substantial scenery

Review the space at the intended game camera. Ask which silhouettes bound the street, what terminates a view and where a courtyard begins. Place the large anchors first: buildings, workshop sheds, utility towers, substantial rock formations or ruins. Then organize fences, equipment and vegetation around those anchors, followed by small ground clutter.

Use connected functional groups: a detention yard, maintenance frontage, loading area or refuge. Give them usable entrances and uneven but coherent boundaries. Keep gaps for combat deployment and navigation; a visually continuous street edge need not be an uninterrupted blocking wall. Large background formations can frame a route while foreground buildings establish its scale.

Measure coverage by type and position, not total prop count. In the local Uprising case, a pass with 91 new props still looked empty to the user: 53 were rubble/ground items and only three were substantial buildings. The following candidate added eight buildings, two towers and five large rock groups. Those counts document the response to the feedback; its final appearance has not been accepted and the ratios are not a reusable density formula.

**Composition check:** inspect street edges, courtyard perimeters and views between landmarks. Confirm useful large forms in those views before adding more small objects. A top-down dot plot cannot establish 3D density or beauty.

## Integrate the surface

Query the actual terrain set and texture slots. Sample the neighborhood's blended materials and carry that palette into the new space. Use connected surface roles—road, working yard, worn shoulder, rocky edge—with soft transitions and local variation. A uniform material can be intentional, but isolated rectangular patches tend to expose the editing operation.

Place ordinary units and equipment on the existing ground by default. Add or change roads because a continuous route needs them, not because a unit was placed. A short decorative road segment does not establish connectivity. When adapting an inherited town, preserve its authored roads unless their change is part of the requested layout.

Temporary high-contrast textures are useful writer diagnostics; replace them with the intended blended treatment in the final scene. Update supported texture companions with the masks and check that the changed region is bounded.

## Grounding, occupancy and passages

Use the [placement and pathing rules](operations.md#placement-and-pathing) for facing, height modes and supplemental blocker ownership. Layout reservation circles are authoring aids; they are not measured native collision or proof that an actor is passable. Include existing objects when checking occupancy: the Uprising warehouse contained a new storage target at the exact position of an original siege tank.

For a bridge, inspect the active Actor/Unit, model, native footprint, orientation, scale and both approaches. In the local case `MarSaraBridgeDestroyed` lacked the intact doodad's `MarSaraBridge` footprint, whose Place layer uses `BoostCliff`. Replacing the broken visual with the intact native actor is a candidate repair, not evidence of actual crossing. Retain the authored deck height when appropriate; terrain snapping does not sample a bridge deck. Test infantry and the required vehicle across both ends.

For a tunnel, keep a continuous walkable route through and beyond the arch, preserve the bordering mountain, and check the native object's footprint and height mode. A tunnel model can exist over blocked terrain. Inspect passage clearance under the arch and at its exits rather than inferring it from the entrance image.

## Resume after Editor normalization

Capture the raw saved components before any localization restoration or further edit. Compare semantic terrain changes separately from requantization, derived pathing, colors, minimap and metadata. Keep unknown fields and unrelated channels. Local diagnostic height reconstruction does not establish every engine channel's meaning.

Project-specific native-cell transfer code may illustrate a bounded experiment, but its terrain version, case palette, dimensions and coordinate assumptions must be checked before reuse. The Uprising helpers are not general cliff, ramp or resize APIs. The manual 208×208 resize and two-level lowering are separately scoped evidence, not proof of arbitrary procedural topology.

## Deliver the right evidence

| Check | What it can establish |
|---|---|
| Component/GUI audit and before/after hashes | Supported serialization, bounded changes, retained references; `static validation passed`. |
| Editor save, close and reopen | Only the observed artifact and behavior. Record whether the operator checked compilation, layers, appearance or all of those. |
| Rendered scene review | Ground contact, clipping, palette and spatial composition at the game camera; record the actual review result. |
| Packaged playtest | Actual unit travel, bridge/tunnel crossing, blocking, object interaction and mission behavior for the recorded scenarios. |

The user-confirmed `Editor accepted` result for Uprising GUI folders covers directory persistence and compilation. It does not validate the same artifact's bridge, tunnel, scenery quality, rescue movement, audio or campaign balance. Keep those open until their own observations exist.

Evidence sources: [local cases](cases.md), [scoped Editor record](editor-evidence.md), and the optional local project records `projects/liberation-day-expanded/reports/uprising-improved.json`, `uprising-current-handoff.md`, and `uprising-gui-organization.json`. These generated artifacts are provenance, not skill installation dependencies. Project coordinates, mission rewards, characters and asset bindings remain in project documentation.
