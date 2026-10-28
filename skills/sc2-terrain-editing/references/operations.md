# Operation contract

Public entry: `python tools/sc2-terrain.py --ui-language zh-CN --help` (or `en`). Output JSON fields, IDs and lifecycle labels remain stable.

`plan <map> --operations <operations.json> --output <plan.json>` calculates changes without editing the map. `apply <plan.json> --output <workspace-copy.SC2Map>` previews; `--apply` publishes. New output parents must exist. Continue editing only by making a new plan against that tool-owned copy and applying to the same copy. Existing unrelated outputs are refused.

The plan binds the source's full content hash and each computed change. `.SC2Map.terrain-work` beside an output contains changed-component snapshots and the revision cursor. `undo <copy> --apply` and `redo <copy> --apply` verify the complete map fingerprint. An Editor save invalidates that history: retain the saved map and begin a new output copy. Previous full maps retained by publication are recovery artifacts, never unconditionally deleted.

## Operations JSON

The file is a JSON array. Coordinates are world XY; brush rectangles are half-open `[left,bottom,right,top]`. Object positions use XYZ. Rotation transforms use radians; camera `Yaw` values use degrees. Names and attribute values are serialized as ASCII XML with character references when needed.

```json
[
  {"op":"height","mode":"raise","rect":[40,40,44,44],"value":0.125},
  {"op":"texture","mode":"set","rect":[40,40,42,42],"slot":1},
  {"op":"objects","mode":"duplicate","selector":{"kind":"point","ids":[113]},"offset":[2,0,0]},
  {"op":"regions","mode":"add","name":"TerrainProbe","shapes":[{"type":"rect","rect":[40,40,44,44]}]}
]
```

IDs, slots and rectangles above are illustrative. Inspect/select the actual map first. A missing or unsupported operation fails the entire plan; there is no partial map publication.

| `op` | Inputs and supported behavior |
|---|---|
| `height` | `mode`: raise/lower/smooth/noise/uniform; `rect`, optional `shape` rect/circle/diamond, `falloff` 0..1, `strength` 0..1, `value`, `iterations` 1..100, `seed`. Uniform requires a vertex-aligned world `sample` XY and the same cliff level throughout the brush. `channel` 0/1 (default 1); +1.0 raises in both channels have scoped Editor evidence, not proof of all native brush semantics. Updates only that channel and render/sync deltas. Absolute world-height set remains unsupported. |
| `texture` | add/remove/set/uniform/blur; same brush options except iterations/seed; `slot` is a global existing texture slot in the affected block's current texture set. Uniform accepts eight `weights` in 0..15. Cross-set allocation is unsupported. |
| `water` | add/update/remove rectangles. Add/update: existing `type`, `rect`; update/remove: `index`. Height/state belongs to configuration, not these rectangles. |
| `water-config` | Existing map-local `WaterData.xml` only. `mode` update/clone/clone-state; `id`, existing `state` (default 0), `values` for supported explicitly present state fields. Clone requires a local `template` ID; clone-state requires a unique uint32 `new_state`. Height, supported numeric appearance properties, Color, UvRate and editor-only Name may be changed; inherited-only fields and unproved assets are refused. A cloned local type can then be assigned to a rectangle with `water`. State cloning does not implement runtime state selection. |
| `objects` | `mode`: add/update/duplicate/delete/transform/align/distribute/group/ungroup. `selector` filters kind/ids/name/type/player/rect; `{"all":true}` is explicit selection of all. Add requires `kind`, a same-kind `template` selector, and `position`. Spatial operations take `offset`, `pivot`, `angle`, positive `scale`, optional `mirror` x/y. Alignment/distribution take `axis` and `spacing`. Group takes `name`. |
| `objects` properties | Query `object-schema --kind unit\|doodad\|point\|camera` for attributes, child fields and enum values from the installed Objects.xsd. `children` inserts/updates indexed Flag, CameraValue, AIActive, AIRebuild, AIFlag or Resources, or typed SoundHeight: `{"tag":"CameraValue","index":"Distance","value":30}`; `{"tag":"Flag","index":"PointHidden","remove":true}` removes an override. Texture, GroupObject and PatrolPoint are excluded. Template-based normal points, units, doodads and cameras are supported; new start locations are not. |
| `objects` grounding | Absolute-height doodads (`Flag HeightAbsolute=1`) default to preserving terrain-relative height when moving/copying or aligning/distributing XY. The terrain-height difference is added to the computed Z, retaining intentional vertical offsets. An explicit XYZ `position` or alignment on Z keeps the supplied Z by default. `grounding` may explicitly select `preserve-offset`, `snap` (replace Z with sampled ground), or `keep-z`. Snap supports placement or correcting a buried object without moving XY. Sampling uses the current HMAP on unit-scale, zero-offset terrain; mixed cliff samples are refused. Relative-height objects, native platforms/bridge surfaces and other collision geometry are not decoded. |
| `regions` | add/update/move/delete/merge. Add: `name`, nonempty `shapes`. Shapes: rect with `rect`; circle with `center`,`radius`; diamond with `center`,`width`,`height`. Move: selector, 2D `offset`. Merge copies source shapes into the first selected region while preserving source IDs. |
| `foliage` | remove instances within `rect`, or seeded scatter using an existing `template_flag`, `density` instances per square world unit, `seed`. New records precede existing ones: order affected visible results in the accepted Zerus diagnostic. `prioritize` stably moves a rectangle's existing instances to the front, preserving every record. Use a visibly confirmed flag/texture profile; an arbitrary observed flag does not guarantee grass. This is separate from native allow/disallow/regenerate brushes. |
| `creep` | `mode` paint/remove; integer-aligned world `rect`, optional `shape` rect/circle/diamond selects whole cells by their centers. Unit XY scale and zero XY offset required. Writes/creates `CellAttribute_Cpl`, filling each selected world-cell byte with 255 or clearing it to 0; preserves outside bytes, including finer native samples. Legacy PaintedCreepLayer migration is refused. This edits preplaced creep, separately from permission masks and runtime creep sources. |
| `visibility` | `mode` paint/remove; same whole-cell bounds/shape restrictions as `creep`. Writes/creates `CellAttribute_Vbl` to paint or clear vision blockers, with scoped Editor acceptance. Global fog settings, unexplored-area masks and unit line-of-sight behavior are separate. |
| `pathing` | `mode` paint/remove; integer `rect` and optional rect/circle/diamond `shape`. Writes/creates `CellAttribute_Pnp` using whole-cell 255/0, preserving outside bits. Removes supplemental paint, without forcing native terrain/footprint blockers walkable. Legacy PaintedPathingLayer migration, finer subcell layout, air/building masks and runtime pathfinding remain separate. Cannot manually paint while owned doodad contributions are active; reconcile those first. |
| `doodad-blockers` | `selector` for doodads, `profiles` mapping Type to an explicit static occupancy or native profile, optional `keep_clear` world rectangles and `allow_empty`. Transforms local rectangles with final placement, rotation and XY scale; conservative whole-cell intersection raster. Keeps original Pnp bytes and overlapping contributions. Tool history stores the ownership/recipe, so subsequent `objects` edits automatically synchronize the selected scenery in the same transaction, including deletion. Unknown profiles, stale Pnp and route conflicts are refused. |
| `lighting` | `mode` add/remove; `rect`, optional `shape`, `falloff`, `strength` 0..1, Editor `region` 1/2 (default 2). Requires an existing Editor-authored LightingMap.tga at four pixels per world unit, unit XY scale and zero XY offset. Region 1 uses R, region 2 uses G; removing restores region 1. Patches with other channels are refused. Retains image header/footer and untouched pixels. New light definitions and additional regions are separate. |
| `roads` | move/duplicate/remove an existing `group`; move/duplicate use XYZ `offset`. `mode` add reuses a native straight two-point template `group` and accepts two new XY `points`, grounding endpoints from HMAP on gentle single-level terrain. Retains native width/material/opaque profile fields and constructs matching direction vectors. General curves and width/type changes remain unsupported. |
| `bounds` | Integer `rect` within current MapInfo dimensions; update playable bounds and integrity hash together. Does not resize terrain or change camera bounds. |
| `cliff-stamp` | `template` Components map, `source_center` and destination `center` (even integer XY), even `radius` 2..16. Requires v115, identical terrain/cliff palettes, unit scale, zero offset, a flat matching-level border around an isolated one-level donor island, a flat destination with clear cell flags, and no intersecting ramp descriptor. Transfers render/sync heights, levels, cell flags and cliff XML cells together. Preserves destination fine-height channel; native color defaults/pathing require acceptance. Does not implement arbitrary cliff brushes. |

Property replacement requires an existing same-kind placed instance for the destination type. The tool retains unknown XML, attributes, children and unknown binary channels. Deleting referenced objects/regions is refused; group membership is removed for unreferenced object deletions. Generated scripts are never rewritten to mask broken references.

## Placement and pathing

`objects` add/duplicate/update/transform accepts `face_towards: [targetX,targetY]` for units and doodads. It computes absolute `Rotation` using `atan2` from each object's final position, without moving the object to turn it. A coincident target, camera/point target, or simultaneous explicit `attributes.Rotation` is refused. Absolute `Rotation` is radians: 0 = +X, pi/2 = +Y in the placement coordinate system; verify the rendered model's own forward axis. Existing `angle` is a spatial rotation around `pivot`, not a rotation-in-place shortcut.

```json
{"op":"objects","mode":"update","selector":{"kind":"unit","name":"Guard"},"face_towards":[60,84]}
```

Match facing to approach directions, formation axes and scenery alignment; retain authored facing where the layout gives no reason to change it. Cosmetic rocks may be symmetric, so inspect numeric rotation as well as appearance.

Check HeightAbsolute before choosing Z. For terrain contact, an absolute-height template can use `grounding:"snap"` with its new position; subsequent offset moves preserve its terrain-relative height automatically. A generic spatial move that retains an absolute Z can bury the object on higher terrain, as confirmed by the RockSmall diagnostic. `keep-z` retains deliberately authored bridge/platform/elevated placements; the ground sampler reconstructs terrain only. The accepted correction and automatic replay are scoped to the MarSara case, not every model's pivot or native geometry.

For automatic scenery blocking, establish the actual target's Catalog footprint or a user/Editor-verified local shape, transform it with placement/rotation/scale, and preserve deliberate openings. Visual model bounds do not establish a footprint. Native footprint blockers and painted masks are separate; adding permanent paint under movable/destructible objects can leave invisible barriers after removal. Preserve native behavior for those objects. Ground, air, building placement and vision are independent constraints.

Reference-only evidence: `Actor:RockSmall` exists as a CActorDoodad, not a Doodad catalog entry. The bundled Liberty actor export has no explicit Footprint on that entry; absence does not resolve its inherited/default behavior. `Actor:Aiur_City_Light` explicitly names `FootprintDoodad1x1`; that footprint's exported Layers are Check/Place plus a Shape. A footprint name or placement shape alone therefore does not establish a ground-walkability mask. These snapshot examples are lookup guidance, not effective-value evidence for an active map.

The manual no-ground-path probe changed four Pnp world-cell bytes near `(52,68)` from 0 to partial masks. The experimental whole-cell writer fills all eight bits or clears them, without inventing individual sample positions. Clearing A and painting a 2x2 B patch passed the MarSara PathingWrite save/reopen check; runtime traversal and footprint-derived placement validation remain separate.

For explicit scenery occupancy, supply profiles such as the following. The rectangle is a caller-verified local footprint before placed Scale and Rotation, not a default for every rock. `mode: native` with `evidence` preserves native behavior without painting a permanent obstacle; use that for movable/destructible blocking. A string in `evidence` records provenance but does not itself verify the claim; the agent must query the actual map or obtain a measured native example.

```json
{"op":"doodad-blockers","selector":{"kind":"doodad","name":"StaticWall"},"profiles":{"ExistingWallType":{"mode":"static","rect":[-2,-0.5,2,0.5],"evidence":"Replace with actual map-specific footprint evidence"}},"keep_clear":[[40,50,44,60]]}
```

The raster includes each world cell intersecting the transformed rectangle, so an oblique edge can expand blockage by less than one cell on each side. Native finer samples, arbitrary Catalog footprint decoding and automatic inference from models are not implemented. A `keep_clear` conflict fails planning rather than silently narrowing a route.

The plan and adjacent `.SC2Map.terrain-work` revision record retain original per-cell bytes and the recipe. Keep that history beside its map: copying the map alone loses contribution ownership. Later object transforms/deletions automatically restore the old contribution and recompute the union for surviving selected doodads; unrelated and overlapping original paint is retained. Undo/redo and new tool-created copies retain this state, including undo to a copy's initial revision. Editor saves still invalidate same-output history: create a new copy from the saved map; ownership can be reused only while Pnp exactly matches the stored hash, otherwise synchronization refuses and requires reconciliation. Manual `pathing` paint with active owned cells is refused to protect their baseline; establish manual paint before initial scenery ownership, or first sync an explicit empty selection (`allow_empty:true`) to restore the original layer.

Each explicit `doodad-blockers` call replaces the entire managed selection, rather than adding another independent owner group. Combine all intended managed IDs and Type profiles in one call. The saved recipe freezes selected IDs, so renaming or moving an object out of the initial selection rectangle still updates its blocker. After adding new managed scenery, explicitly sync a selection including both existing and new IDs. Empty ownership is discarded once every managed contribution is restored.

Query active dependencies before relying on footprint inheritance; reference exports alone do not establish target effective values.

## Controlled experiments

`experiment <source-map> --feature <capability-id> --rect <l> <b> <r> <t> --output <new-directory>` produces `before/Probe.SC2Map`, `after/Probe.SC2Map` and exact steps.

1. The user opens only `after/Probe.SC2Map`, saves without editing, then closes the map.
2. Run `experiment-baseline <directory>` to capture `normalized/Probe.SC2Map`. Preserve original and normalized baselines separately.
3. The user performs exactly one action, records brush size/type/parameters and location, saves, closes/reopens, and reports the result.
4. Run `experiment-compare <directory> --output <report.json>`. Inspect changed XML elements, binary ranges, versions and companion files. Byte offsets after variable-length XML are not field identities; parse the XML to compare semantics.
5. Derive the smallest rule, test it on a new copy and another applicable sample, then ask for Editor/runtime validation. Preserve evidence scope; one pair cannot validate all slope directions or terrain sets.
