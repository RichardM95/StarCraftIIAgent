# Terrain Module drawing conversations

[中文](terrain-conversations.md)

These examples focus on SC2 Terrain Module drawing. See [skill conversations](skill-conversations.en.md) for general integration/model requests and the [terrain guide](sc2-terrain-editing.en.md) for commands/transactions. The entry is [sc2-terrain-editing](../../skills/sc2-terrain-editing/SKILL.md). Requests describe desired outcomes, without promising an automatic writer for every feature. Query current `capabilities` and scoped evidence instead of treating historical cases as acceptance of the current map.

## Start a map

Send this first, followed by a specific drawing request below. Replace every `<...>`; use coordinates and units verified for the actual map:

```text
Read AGENTS.md, skills/sc2-project-entry/SKILL.md and
skills/sc2-terrain-editing/SKILL.md first.
Source: <latest-saved-Components-map>.
Output: <new-independent-workspace.SC2Map-copy>.
Goal: <combat-spaces-routes-theme-and-edit-extent>.
Preserve: <story-objects-roads-regions-cameras-dependencies-and-protected-terrain>.
Query current capabilities and verify dimensions, coordinates and actual dependencies.
Plan/review supported edits and execute the authorized scope on the copy.
Identify unsupported parts and prepare controlled, single-operation Editor experiments.
Keep the original, publish and generated Galaxy read-only.
Report static, Editor and game evidence separately.
```

If the input is a packed `.SC2Map`, identify its format first and use the explicit conversion workflow in the [archive tool guide](../../tools/README.en.md) when Components are needed. Without a valid reference or Components base, identify missing input rather than presenting an empty directory as a complete map. A new design can begin with a layout draft; actual drawing still requires a valid base or supported creation tool.

## Drawing requests

| Number | Terrain Module task | Copyable request | Boundary and acceptance |
|---|---|---|---|
| 01 | Read-only map inspection | “Inspect `<map>` read-only: total dimensions, playable bounds, terrain theme, existing roads/water/objects/regions and dependencies. Provide coordinate-based diagnostics and evidence gaps.” | The map argument selects the target; diagnostics are not game rendering. |
| 02 | Choose a reference base | “Scan `<reference-map-directory>` and shortlist `<town/wilderness/Zerg-theme>` candidates. Compare dimensions, terrain and dependencies without importing project mechanics or calling modified community maps pristine official sources.” | Distinguish Components/archives and asset availability; select a base before copying. |
| 03 | Routes and spaces first | “Plan entrances, main route, combat spaces, branches and exits in `<copy>` within `<extent>`. Preserve `<existing-route>`, reserve `<largest-traveler>` clearance and building access; show unimplemented connections.” | Width is map-specific input, not a universal pathfinding threshold; static connectivity needs travel tests. |
| 04 | Height brushes | “Apply `<raise/lower/uniform/smooth/noise>` in `<area>`, protecting roads and levels. Verify supported modes/channels/strength and show a bounded candidate diff first.” | Fine height is distinct from cliff levels; unsupported/absolute-height modes require experiments and preserved simulation companions. |
| 05 | Texture blending | “Give `<area>` a `<road/courtyard/rocky-edge>` surface using actual existing texture slots and neighboring materials, with transitions and unchanged surroundings. Avoid isolated rectangular color patches.” | Query slot mappings; palette creation is separate from painting existing slots. Check companions. |
| 06 | Cliffs and platforms | “Create `<levels-and-boundary>` at `<position>`. Check writers first; without a general cliff brush, preserve topology and prepare one level-change experiment instead of substituting a height bump.” | Raise/lower, type and same-level operations need their own evidence; parseability does not establish topology. |
| 07 | Ramps and direction | “Connect `<lower-approach>` to `<upper-approach>` using `<ramp-width-and-direction>`. Check add/remove/turn support; if missing, experiment with one direction on a copy and preserve old ramps.” | One direction/terrain set does not prove arbitrary ramps. Save/reopen, then test infantry and vehicles. |
| 08 | Reuse a supported cliff sample | “Check whether the isolated one-level island in `<reference>` fits `<destination>`. Verify version, terrain/cliff palettes, flat border, extent and ramp intersections before planning a bounded stamp.” | Follow the current `cliff-stamp` contract; it is not a general mountain/ramp/multi-level transplant. |
| 09 | Water extent and height | “Change `<existing-water>`'s `<rectangle/local-height/local-state>` using actual local water states. Preserve other water and identify shoreline/terrain checks.” | Query state/type; one height/color case cannot validate every water behavior. |
| 10 | Roads | “Lay a straight road between `<two-endpoints>` using `<existing-native-straight-road-group>` material/width. Preserve old roads and ground continuity; list Editor steps for unsupported curves or width changes.” | Template straight roads and group transforms do not imply arbitrary curves; appearance does not establish travel. |
| 11 | Foliage | “Thin/add foliage in `<area>` using a visibly confirmed template and `<seed/density>`. Clear small road/entrance areas while preserving other instances.” | Existing-instance scatter/removal differs from native allow/disallow/density/regenerate brushes. Unknown flags need evidence. |
| 12 | Lighting regions | “Paint/remove `<existing-lighting-region>` in `<area>` using the actual LightingMap and supported channels. Preserve other regions and provide game-view checks.” | Painting an existing region is distinct from arbitrary light creation; appearance needs Editor/render observations. |
| 13 | Preplaced creep | “Paint/clear preplaced creep within `<extent>`, preserving outside data. Verify whole-cell, scale and offset constraints; validate runtime creep sources separately.” | Preplaced creep, permission masks and runtime spread are distinct mechanisms. |
| 14 | Vision blocking | “Paint/remove vision blocking in `<whole-cell-extent>`, preserving passages and other areas. Explain its distinction from ground blocking, fog of war and unit sight.” | Vision paint cannot replace pathing/global fog settings; actual sight needs scenario tests. |
| 15 | Units and formations | “Place confirmed `<unit-type/template>` in `<area>` with `<formation-and-spacing>`. Guards face `<approach>`; avoid existing units/intersections and preserve mission scripts.” | Verify active dependencies/templates; placement does not implement AI, rescue or objectives. |
| 16 | Doodads and grounding | “Arrange `<buildings/rocks/equipment>` along `<street-or-cliff>`, orient/scale them and ground ordinary objects. Preserve elevated/deck Z; inspect model facing and height modes to avoid burial.” | Facing in place differs from orbiting positions; terrain sampling cannot identify arbitrary platforms/decks. |
| 17 | Points and regions | “Add/adjust `<points-or-rectangular/circular-regions>` in `<copy>`, preserving existing IDs and typed references. Check trigger references before deletion; route mission events to the GUI skill.” | Referenced deletion is blocked; start locations/arbitrary reference remapping need dedicated support. |
| 18 | Cameras and composition checks | “Inspect layout from `<existing-camera>` and `<intended-game-view>` for occlusion, street edges and entrances. Check implementation before requesting new cameras/property writes; arrange Editor work when needed.” | Camera/object diagnostics do not imply camera editing or native rendering. |
| 19 | Ground-pathing paint | “Paint/clear supplemental ground blocking within `<whole-cell-extent>`. Check original Pnp and owned doodad contributions; preserve unrelated native/finer data.” | Clearing paint does not force cliffs/native footprints walkable. Air, building placement and actual travel are separate checks. |
| 20 | Static scenery blocking | “Block `<static-building/rock-selection>` from actual footprints or measured shapes, preserving `<passage-rectangles>`. Synchronize owned contributions after moves/deletions; retain native behavior for movable/destructible objects.” | No footprint inference from model size. Include the entire managed selection; preserve original/overlapping paint and stop on route conflicts. |
| 21 | Playable bounds | “Set playable bounds to `<rectangle>` within current dimensions. Check existing objects/regions/cameras, preserve outside components and identify separate camera-bound work.” | Playable MapInfo bounds are not map resizing or automatic camera bounds. |
| 22 | Resize and origin | “The current canvas cannot fit the route; expand `<direction>` to `<dimensions>`. Verify total size, origin, existing routes and references; without a general writer, prepare an isolated Editor experiment.” | Do not change only headers or reuse fixed project cell-transfer scripts. Save/reopen and affected channels need evidence. |
| 23 | Bridge/tunnel terrain | “Connect `<bridge-or-tunnel>` with `<road-approaches>`, checking native model, facing, footprint, ground levels and vehicle clearance. Preserve deck height and mountain constraints instead of adding an unintended bypass.” | An intact model does not prove crossing. Test infantry/required vehicles; teleportation is not terrain repair. |
| 24 | Scene refinement | “`<scene>` looks empty. Inspect silhouettes, street edges and courtyard enclosure at the game camera. Add substantial buildings/rocks/equipment before small clutter; retain combat/vehicle space.” | Prop counts/top-down dots do not establish art quality; check large-model occupancy and occlusion. |
| 25 | Plan, undo and recovery | “Preview this edit set on `<owned-working-copy>`, inspect component differences, then apply the authorized scope. Before undo/redo, verify map/history fingerprints; preserve later manual edits.” | Retain the copy and adjacent history together. Changed sources/history invalidate old plans; preserve failed-publication journals/backups. |
| 26 | Editor save and continuation | “Save/close/reopen `<this-copy-and-operation>` and inspect it. Perform authorized, available GUI steps; hand off necessary unavailable ones. Capture raw save differences before explicit map/locale string audits.” | Normalization invalidates old history. Create the next copy from the latest save; record acceptance per operation. |

## Multi-turn drawing conversations

### From graybox to testable terrain

**User:** “Use `<reference-Components-map>` for a small suburban battlefield, output `<new-copy>`. Entrance south, exit north, courtyard between; retain ramps/roads and do not wire missions yet.”

**Agent:** Query capabilities, size, coordinates and dependencies; establish route/spaces. Work from existing templates on the copy, distinguish terrain from placement and mission triggers, and provide plan, actual differences, audit and open checks.

**User:** “Add a one-level platform north with a south-facing ramp. The courtyard surface is too rectangular; blend paving into rocky dirt.”

**Agent:** Separate texture blending from cliff/ramp topology. Prepare a candidate with supported existing slots; when a general level/direction writer is absent, preserve topology and prepare one controlled experiment. A smoothed hill does not replace the requested platform.

**User:** “Textures survived save/reopen. I made the platform manually; the ramp is untested.”

**Agent:** Capture raw saved differences first. Record `Editor accepted` only for the tested textures; the manual platform is an experiment, not acceptance of an automatic writer. Leave the ramp open, continue from the latest save and test required travelers.

### Scenery, blocking and road clearance

**User:** “Place buildings and rocks beside the street in `<current-copy>`, keeping `<vehicle-type>` access. Face units toward the entrance and avoid burying them.”

**Agent:** Check existing objects, dependencies, facing and height modes; arrange substantial forms first. Derive static blocking from real footprints/measured shapes, preserve roads/device approaches and retain native destructible-object behavior.

**User:** “Move three east buildings outward to widen the entrance, and delete the vehicle destroyed by the mission.”

**Agent:** Check references; block direct deletion of a referenced vehicle and route that change to GUI work. Synchronize building-owned blocking contributions with the moves, retaining other paint; audit within the same copy transaction so old positions do not remain permanently blocked.

**User:** “Save/reopen produced no errors. What should we test next?”

**Agent:** Verify the actual saved artifact and inspected scope, then separately check ground contact/occlusion at the game camera, infantry/vehicle travel along the complete route and blocking after mission destruction. Compilation alone proves none of those scenarios.

## Delivery and reference selection

Provide explicit input/output, edit extent, actual component differences and open work. Use `static validation passed`, `Editor accepted` and `packaged runtime passed` only with matching evidence. Running a tool, parsing components or completing one manual action cannot establish a fully implemented Terrain Module.

Load operation JSON, format, case and experiment details through the [terrain skill](../../skills/sc2-terrain-editing/SKILL.md). This page supplies conversations rather than a duplicate parameter contract. Recheck current help, source and capabilities when the tools change.

<!-- translation-source: wiki/guides/terrain-conversations.md; sha256: aafe8953a4c246ac67656bf51832cc878fb26daa150edefc36eae80bea714acd -->
