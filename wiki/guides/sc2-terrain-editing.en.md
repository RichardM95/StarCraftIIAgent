# Terrain Module tools and controlled Editor experiments

[中文](sc2-terrain-editing.md)

For copyable drawing requests, use [26 Terrain Module scenarios and two multi-turn conversations](terrain-conversations.en.md). They distinguish layer-specific goals, current implementation gaps and evidence without requiring users to construct tool arguments themselves.
<!-- translation-source: wiki/guides/sc2-terrain-editing.md; sha256: a68f798640ff4da61a0239f8006ee0628b9f48952824a6ac6d429f15b491269a -->

Entry skill: [sc2-terrain-editing](../../skills/sc2-terrain-editing/SKILL.md). Attribution follows [AUTHORS](../../AUTHORS.en.md). The current target is basic drawing on reference-map copies: heights, textures, cliffs/ramps, water, unit/doodad/region placement, deletion and movement, plus creep, roads, foliage, lighting and visibility painting. Exhaustive advanced menus and property parity are optional extensions. `capabilities` is the single coverage ledger, separating implemented tools, diagnostic previews, Editor acceptance and runtime acceptance.

## Adaptation and scene composition

For expansion, empty-looking scenes or bridge/tunnel connections, read [map adaptation and composition](../../skills/sc2-terrain-editing/references/map-adaptation.md) on demand. Continue from the latest user save, establish routes and functional spaces, place substantial buildings and rocks, then add facilities, vegetation and surface detail. Unit placement normally retains local materials; roads serve continuous routes. Many small props do not replace spatial framing. For mission objects, official voice and trigger folders, use [GUI adaptation](../../skills/sc2-map-triggers/references/map-adaptation.md). Case values are not fixed templates for another map; GUI compilation does not establish terrain or gameplay acceptance.

## Inspect and learn

```powershell
python tools/sc2-terrain.py --ui-language en capabilities
python tools/sc2-terrain.py --ui-language en capabilities --basic-only --pending-only
python tools/sc2-terrain.py --ui-language en scan "<reference-Maps-directory>" --audit --output temp/terrain-corpus.json
python tools/sc2-terrain.py --ui-language en inspect "<map.SC2Map>"
python tools/sc2-terrain.py --ui-language en dependencies "<map.SC2Map>" --mods-dir "<actual-Mods-directory>"
python tools/sc2-terrain.py --ui-language en render "<map.SC2Map>" --layers height,cliffs,water,point,regions,grid --output temp/terrain-preview.svg
```

The supplied modified campaign distribution contains 99 Components maps, 90 with terrain. Custom dependencies and modifications mean these are not asserted to be pristine Blizzard originals. Pass a reference root explicitly; scanning does not switch the selected project. Resolve availability from each map's actual dependency graph. Partial dependency research does not establish runnable completeness.

`audit` checks no-edit roundtrips of supported formats. It does not establish new brush functionality. SVG previews diagnose height and layers; they do not reproduce native materials, camera effects or runtime pathfinding.

## Edit isolated copies

Inspect coordinates, IDs, slots and water configuration first; prepare JSON using the skill's [operation contract](../../skills/sc2-terrain-editing/references/operations.md). Create the explicit workspace output parent, preview and apply:

```powershell
python tools/sc2-terrain.py --ui-language en plan "<source.SC2Map>" --operations "<operations.json>" --output temp/terrain-plan.json
python tools/sc2-terrain.py --ui-language en apply temp/terrain-plan.json --output temp/TerrainWork.SC2Map
python tools/sc2-terrain.py --ui-language en apply temp/terrain-plan.json --output temp/TerrainWork.SC2Map --apply
python tools/sc2-terrain.py --ui-language en audit temp/TerrainWork.SC2Map
python tools/sc2-terrain.py --ui-language en undo temp/TerrainWork.SC2Map --apply
python tools/sc2-terrain.py --ui-language en redo temp/TerrainWork.SC2Map --apply
```

Plans bind the complete source content hash and expected changes. Replan after source changes. For continued edits, plan against a tool-owned working copy and apply back to that same copy. Unowned existing maps cannot be overwritten. Adjacent `.terrain-work` directories retain component history; transactional publication also retains replaced full-map backups.

An Editor save changes multiple components and invalidates prior history. Preserve that saved map and start another output copy. Stop overwriting on map/history inconsistencies and inspect surviving journals/backups. Original campaign maps, current project configuration and `publish/` are not experiment write targets.

## Complete basic operations and extend on demand

`active_requirement` identifies current basic drawing requirements; the former full-module inventory remains an optional backlog. Use `--basic-only --pending-only` to locate basic operations still missing a writer. Map resizing, exhaustive property parity and advanced pathing are outside the current completion gate. Disclose missing writers and use controlled experiments to establish their rules; tutorials or previews do not count as actual edits.

Unit and doodad addition currently reuses a same-kind template in the map. Movement and deletion use explicit selectors; referenced object deletion is refused. Regions support circles, rectangles, diamonds, movement, union copies and deletion. Query schema fields with `object-schema --kind unit` and other kinds. Roads support whole-group duplication, movement, removal and new straight segments using native two-endpoint profiles. Foliage supports existing-flag scattering and removal; new instances are prioritized first, and the Zerus comparison confirmed visible results. Other flag/texture combinations require visibly confirmed examples. Creep, vision blockers and region-1/2 lighting have scoped Editor evidence. Consult the ledger and evidence page for exact boundaries.

Basic unit/doodad and rectangular-region additions, moves and removals passed the Editor save/reopen check. Choose facing from approaches, formations and scenery axes when placing/moving objects: `face_towards` points at a target, and `attributes.Rotation` specifies radians; both can turn objects in place. Preview marks the facing axis; the actual model forward direction still needs Editor checking.

`pathing` paints/clears whole-cell no-ground-path masks; the MarSara comparison passed Editor save/reopen checking. `doodad-blockers` supplements blocking from explicit verified static occupancy rectangles, automatically following selected doodads' subsequent movement, rotation, scaling and deletion while retaining original/overlapping blockers. `keep_clear` protects reserved routes. Ownership is stored in adjacent tool history; keep it with the map. Unknown occupancy is refused without guessing model bounds. The manually assigned diagnostic rectangle passed the C/D Editor comparison for movement, rotation and old-area restoration; this does not identify actual model occupancy. The conservative whole-cell raster rounds outward; finer pathing and arbitrary Catalog footprint decoding remain unsupported. Movable/destructible objects retain native blocking; ground/air movement, building placement and vision remain separate. See [placement and pathing](../../skills/sc2-terrain-editing/references/operations.md#placement-and-pathing).

Absolute-height doodad moves, copies and XY alignment preserve terrain-relative height by default, preventing burial after moving onto higher ground. Explicit XYZ retains the supplied Z by default; choose `grounding: snap` for terrain contact or `keep-z` for fixed height. The corrected MarSara stone passed save/reopen verification, and the current default move sequence reproduces the accepted object/pathing bytes. Sampling requires unit terrain scale and zero offset, does not decode bridges or model surfaces, and refuses mixed cliff samples.

```powershell
python tools/sc2-terrain.py --ui-language en experiment "<reference.SC2Map>" --feature cliff.raise --rect 40 40 44 44 --output temp/cliff-probe
python tools/sc2-terrain.py --ui-language en experiment-baseline temp/cliff-probe
python tools/sc2-terrain.py --ui-language en experiment-compare temp/cliff-probe --output temp/cliff-diff.json
```

Follow generated `steps.txt`: first save without editing and close the map; capture the normalized baseline. Perform exactly one action, record parameters, save, close/reopen to check, then close for file reading. The agent may operate when authorized and UI input verifiably works; otherwise ask the user only for unavailable steps. Run an in-game test where behavior requires it.

Record unreadable files and errors explicitly. `experiment-compare --allow-unreadable` allows read-only partial comparison and lists every inaccessible component; it cannot establish full coordinated-change evidence. Separate format upgrades, global requantization and Editor normalization from the local functional change.

## Validation and maintenance

Run `python -m unittest discover -s tools/tests -p test_sc2_terrain.py` for focused regression. Tool/rule integration also requires `python tools/test-suite.py --scope tools` and `--scope docs`. Validate the skill using skill-creator's `quick_validate.py`.

Follow the [feedback workflow](../implementation/testing-feedback-workflow.md): static checks establish at most `static validation passed`; actual open/save/reopen evidence establishes `Editor accepted` for that artifact; packaged scenario steps/results establish `packaged runtime passed`. Keep manual experiment acceptance separate from tool-generated acceptance. Judge basic drawing against current requirements; optional full-editor parity does not block that delivery. See [Editor evidence](../../skills/sc2-terrain-editing/references/editor-evidence.md) for accepted height, texture, isolated-cliff-stamp and independent-water-height scopes.
