# Local campaign observations and learning tasks

Initial source: user-supplied `Maps/campaign` under the modified x2 campaign v1.17y distribution. Later adaptation observations also use the community Uprising Liberation Day map and its user-saved working copies. Neither source is asserted to be unchanged Blizzard content. Resolve the reference root supplied by the user rather than embedding its machine path into a reusable skill.

The observed corpus contains 99 Components maps: 90 with `t3Terrain.xml` and nine without. Terrain XML versions: 113 (30), 114 (56), 115 (4). Terrain-bearing groups: WoL root (29), Swarm (27), Void (22), Void prologue (3), Nova (9). Story/hub maps without terrain are not treated as damaged terrain samples.

| Sample relative path | Observed evidence | Useful next comparison |
|---|---|---|
| `traynor01.SC2Map` | MarSara; dimensions 137×161 vertices; two ramp descriptors; no water rectangles. Adds `Mods/18.SC2Mod` alongside campaign dependencies. | Read relative heights, cliff levels, ramps and roads together. It is the first controlled cliff-edit experiment, not a universal cliff generator. |
| `swarm/zchar01.SC2Map` | CharDunes; 145×177 vertices; two ramps; 23 water/configuration rectangles. Includes `Mods/z1.SC2Mod`. | Distinguish water coverage rectangles from material/state/height configuration, and verify whether the rendered fluid is water or another terrain fluid. |
| `void/paiur01.SC2Map` | AiurCity; 185×201 vertices; three ramps; seven AiurCreep water rectangles. Includes `Mods/p1.SC2Mod`. | Compare multiple cliff sets, ramp directions and named fluid regions. Keep placement/terrain/simulation coordinates aligned. |
| `thanson01.SC2Map` | Agria; 153×201 vertices; five ramps; nonempty water and HRDT groups. | Compare road/hard-tile layout and shore boundaries; identify each HRDT group's actual visible role before treating it as a road. |
| `swarm/zzerus01.SC2Map` | Zerus; 193×161 vertices; nine ramps; water present. | Compare connected plateaus, alternative routes and vegetation against real unit-scale playtests. |

## What to extract from a case

For a requested layout, select cases by terrain set, object availability, ramp direction, water configuration and the role of the space. Keep source observations, design choices and tested gameplay separate.

- Sample the height and cliff grids at intended entrances and routes. Use the actual ramp descriptors and placed blockers; height alone does not establish connectivity.
- Locate bases, objectives and reference points from placed objects/regions, checking whether their roles are actually confirmed by trigger evidence. Do not assign gameplay roles from a filename or a minimap alone.
- Measure routes and minimum gaps in world coordinates, then test the intended unit and formation. A straight-line distance is not path travel time or group clearance.
- Compare texture/foliage/doodad density near routes versus background using the decoded layers. A seeded scatter must preserve readability and be tested after loading actual assets.
- For any recommendation about composition or route hierarchy, attach the specific map/location and the result of the comparison. Do not invent measured thresholds, aesthetic scores or similarities.

Reusable learning consists of evidence-backed choices and working tools. A stored map index does not by itself teach reliable design, and copying a campaign terrain does not by itself implement a new brush.

Absolute-height doodads need a terrain-relative movement rule. In the MarSara blocker probe, moving RockSmall from `(68,76)` to `(72,76)` crossed a two-unit terrain rise; retaining Z buried the object while its supplemental pathing remained visible. Correcting Z to the destination terrain restored visibility, and the default move now preserves the source's relative offset. Use explicit snap for terrain contact and keep-z for intentionally elevated authored placements; actual bridge/platform surfaces require separate evidence.

## Decisions supported by the local cases

| Drawing decision | Sample evidence and condition |
|---|---|
| Establish visible scale before fine sculpting. | On MarSara, the initial +0.125 height and 2×2 texture patch looked unchanged; the later +1.0 height and 8×8 dirt patches were clearly visible and retained. Use a temporary obvious probe when checking a new writer, then choose the final artistic strength separately. This is not a universal height recommendation. |
| Locate water checks over the bed. | Agria's marker `(68,144)` lay on ground near height 8 and confused the first water check. At `(68,152)` the low bed stayed fixed while water rose 2.2→4.2. Check bank/bed height before placing water labels and use a temporary high-contrast surface when diagnosing depth. |
| Borrow a road profile from the same terrain. | The accepted MarSara road preserves the native width-1 profile and material while changing endpoints. Keep basic new segments on gentle terrain within one cliff level; validate a new curve or slope rather than extrapolating the straight-road case. |
| Measure vegetation density locally. | In modified `swarm/zzerus01.SC2Map`, `[24,144,30,150]` contains 82 foliage instances (2.28/world²); `[32,144,38,150]` contains 94 (2.61/world²). The accepted corrected probe clears the first and rebuilds the second with 108 instances (3/world²), preserving ordinary doodads. These are local comparison values, not recommended density thresholds. |
| Account for foliage record priority. | The initial Zerus additions at the end of a large array remained invisible. Moving identical records to its front made diagnostic flags 2..4 visible; corrected default scatter also showed flag 4 on the original blended terrain. Prioritize new instances and preserve old relative order. The precise engine display budget is unmeasured. |
| Keep geometry and gameplay evidence distinct. | MarSara's native cliff pair changed masks, cliff cells and sync data together. A smooth raised patch, a stamped island and an existing ramp have different component evidence. Preserve the reference's ramps and blockers until a requested replacement has a validated writer; test unit traversal in game. |
| Resume from the latest Editor save. | The Uprising Polished copy was requantized and its derived components regenerated. A later build preserved that saved baseline rather than replacing the full terrain with an older cache. Its local conversion remains a scoped experiment, not a general topology writer. |
| Expand for the route, not a fixed canvas. | The user replaced the proposed 240×224 canvas with a native 208×208 resize, preserving old coordinates. Additional R5 space was fitted inside that canvas. Manual resize acceptance does not establish arbitrary tool resizing. |
| Frame empty areas with substantial forms. | The user still found the first 91-prop pass empty; 53 props were small ground items and only three were substantial buildings. The next candidate prioritizes buildings, towers and large rock groups. Its composition and native travel remain unaccepted; see the [adaptation workflow](map-adaptation.md). |
| Preserve inherited ground unless the layout needs a surface change. | The user rejected an isolated short road and an obvious material patch under a rescue device. Later candidates preserve road groups and use connected, locally blended surfaces. This is an adaptation preference, not a ban on intentional new roads. |
| Separate a visible crossing from a functioning one. | The Uprising broken bridge lacked the intact native doodad's footprint. Replacing it and opening the tunnel floor are candidate repairs; neither a model change nor a connected height grid establishes unit/vehicle crossing. |
