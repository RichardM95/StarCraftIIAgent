# Editor evidence and remaining limits

Editor executable: 5.0.15.98370. Operator: the user. Initial sources are modified campaign maps from the supplied v1.17y distribution; the Uprising section uses a separately supplied community map. This page records scoped observations, not whole-feature completion.

## Generated height and texture probe — Editor accepted

`ChannelProbe.SC2Map` derives from the supplied `traynor01.SC2Map` (MarSara). Tools applied:

- Rectangle `[48,56,56,64]`: relative height +1.0 in HMAP channel 0.
- Rectangle `[64,56,72,64]`: relative height +1.0 in HMAP channel 1.
- Both rectangles: texture slot 0, MarSaraDirt, set to full weight, with sync companion updates.
- Two normal point and region labels, `A_Channel0` and `B_Channel1`, locate the patches.

The user first reported both rectangles visibly raised, then explicitly confirmed that both were dirt and that elevation and dirt remained after saving Components, closing and reopening. The user closed the map for file inspection. This establishes `Editor accepted` for these exact tool-generated raise/set operations. Runtime terrain sampling, pathfinding, building placement and other terrain sets remain untested.

An earlier +0.125, 4×4 height and 2×2 texture example looked unchanged to the user. Binary comparison showed its modified height/mask/sync bytes still matched the generated revision. The larger probe establishes visible write capability; it does not prove the precise perceptual cause of the earlier report, nor every brush's semantics.

Generated component hashes, operations, before/after snapshots and the user's result are retained in the local lab's `diagnostic-channels/editor-validation.json`. Lab artifacts are ignored generated outputs, not portable installation requirements.

## Manual cliff probe — Editor accepted, writer not implemented

The user opened an unedited copy, saved Components and closed it; the tool captured that baseline. The user then applied one Raise Cliff near `(42,42)`, saved, closed/reopened and reported a normal result. Brush size and cliff type were not supplied.

The first terrain edit upgraded terrain XML 113→115, expanded the texture-set representation, changed quantization, replaced old PaintedPathingLayer with CellAttribute_Pnp, and updated other derived data. The local cliff-level change also involved HMAP, SMAP, CLIF, cell flags, cliff-cell XML and vertex-color data. Thus the first pair mixes migration with local generation; it is insufficient to implement a general cliff writer.

The Editor-generated `CellAttribute_Pnp` was inaccessible to the agent even after the Editor closed. The user copied it to a readable lab file. Its payload is a 32-bit bit count followed by the bitset; that structural observation does not establish all named pathing rules. The original unreadable member remains listed in the partial comparison report.

Next clean topology experiment must start from an already upgraded, readable map, take a fresh no-op baseline and isolate one operation. Keep the full component set readable before claiming coordinated pathing validation. A manual accepted cliff edit is not acceptance of a tool-generated cliff edit.

## Second v115 manual cliff pair

The user-confirmed copy of the inaccessible member was combined with the remaining readable files to materialize a new research source; its substitution provenance is retained in the lab. Its already saved v115 state was reused as the baseline, avoiding another format upgrade.

The user raised near `(66,58)`, saved/reopened normally and closed the map. The full pair is readable. The center's cross-shaped five HMAP mask values increased, four CLIF cells increased by 64, a surrounding 4×4 LFCT area changed, and four cliff XML entries changed. HMAP quantization changed slightly, SMAP also changed outside the local patch, and VTCL was regenerated. These global numeric changes must not be treated as a universal localized byte patch.

`cliff-stamp` uses this kind of Editor-authored isolated island as a donor, subject to explicit compatible-flat-area checks. It is separate from general cliff generation. The user inspected the generated stamp at `(70,58)` in `CliffStamp.SC2Map`, reported correct high ground and normal surrounding cliffs, then confirmed save/reopen and closure. This establishes `Editor accepted` for that compatible MarSara v115 isolated-island stamp. Procedural pathing, unit traversal, other terrain sets and arbitrary outlines remain untested. The local lab retains `cliff-stamp/editor-validation.json` and the generated edit history.

## Independent water level — Editor accepted

Source: modified `thanson01.SC2Map`, Agria. The source explicitly defines local `CWater id="Template 2" parent="Agria"`, `State[0].Height=2.2`. The tool clones this local configuration, sets Height=4.2, and reassigns the existing coverage rectangle `[64,128,72,160]` to the clone. It does not infer an inherited height or alter ground grids.

An initial transparent-water test looked as if its bed rose too. The chosen point `(68,144)` was on high ground, and the original water's Color fourth component was 0.055, so that visual report was not sufficient evidence of actual bed movement. Ground/sync/cliff/cell/descriptor files remained byte-identical to the source.

The diagnostic clone uses Color `0.05,0.25,0.8,1` and RefractionDistortion=0, observed over the low bed at `(68,152)`. The user explicitly confirmed that only the blue water surface rose, that hiding water left the bed in place, and that saving/reopening retained the result. This establishes `Editor accepted` for the explicit local configuration clone, those state properties, height change and reassignment of that existing rectangle. It does not prove runtime water-state selection, inherited-only configurations, all water types or gameplay water rules.

Keep coverage rectangles, per-state water appearance/height and the actual terrain separate. For a visual complaint, compare ground-file hashes, observe over a genuinely submerged location, and toggle water visibility before treating refraction/transparent appearance as terrain movement. The diagnostic's color changes are a test aid, not a default override for future maps.

## Preplaced creep painting and clearing — Editor accepted

The user painted Add Creep with brush size 1.5 near `(52,68)` on an already saved v115 MarSara source. The new `CellAttribute_Cpl` contains a uint32 bit count of 174080 followed by 136×160 bytes. Only four bytes became 255: world cells x=51..52, y=67..68. The user copied this otherwise unreadable Editor-created file into a readable evidence file; its substitution provenance is retained in the lab. The pair also contains Editor requantization and derived-file changes, which are not creep encoding rules.

The tool-generated `CreepWrite.SC2Map` clears those four bytes and paints four new whole cells x=59..60, y=67..68, with point labels A and B. In response to the requested save/close/reopen check, the user reported the original creep at A `(52,68)` disappeared and new creep appeared at B `(60,68)`. This establishes scoped `Editor accepted` for whole-cell preplaced creep painting and clearing. Finer brush samples, permission masks, legacy PaintedCreepLayer migration and runtime propagation from units remain separate.

Optional layer creation is part of the editing transaction: undo removes a newly introduced file, and redo restores its exact bytes. The automated regression checks full map fingerprints for both transitions. This does not replace packaged runtime testing.

## Vision blocker painting and clearing — Editor accepted

The user applied the native “阻碍视野” operation with brush size 1.5 near `(52,68)`. It created `CellAttribute_Vbl`; the user supplied a readable copy. Its bit count, dimensions and four full-cell values match the Cpl probe's storage geometry, but it is an independent layer. The original Pnp pathing layer was unchanged.

The tool-generated `VisibilityWrite.SC2Map` clears the original four cells and paints a new 2×2 block near `(60,68)`. In response to the requested save/close/reopen check, the user confirmed A's original blocker disappeared and B's new blocker appeared. This establishes scoped `Editor accepted` for whole-cell vision-blocker data. The lab retains member provenance and generated/current raster hashes. Runtime line of sight, unexplored-area masks and global fog options remain untested.

## Local lighting painting and restoration — Editor accepted

The user applied Add Lighting, region 2, brush size 1.5 near `(52,68)` on the MarSara probe. The sole new functional component was LightingMap.tga, 544×640 uncompressed 32-bit BGRA with top-origin storage. Its native patch occupies image coordinates x=206..210, y=270..274 after normalizing to a lower-left origin. Default pixels are `(B,G,R,A)=(0,0,255,0)`; painted pixels transfer weight from R to G, confirming region 2 against default region 1 at four pixels per world unit. The user supplied a readable copy of the otherwise inaccessible file. No local LightData.xml was introduced.

The tool-generated `LightingWrite.SC2Map` restores the original patch to region 1 and paints region 2 in `[59,67,61,69]`. In response to the requested save/close/reopen check, the user confirmed A `(52,68)` restored region 1 and B `(60,68)` showed region 2. This establishes scoped `Editor accepted` for those raster weights. New light definitions, other channels, global lighting and packaged appearance remain untested.

## Local menu inventory scope

The user exposed the installed Layer menu; the observed layers are Terrain, Units, Doodads, Points, Regions, Cameras and Pathing. The inventory is partial. Full menu parity became an optional extension when the user narrowed the task to basic drawing, including objects, creep, roads, foliage, lighting and visibility.

## Ground no-path paint — Editor accepted for whole cells

The user reported adding the requested no-ground-path brush near `(52,68)`. All saved files are readable. The Pnp layer retains its 174080-bit count and 136x160-byte geometry; only cells `(51,67)`, `(52,67)`, `(51,68)`, `(52,68)` changed, from 0 to 142, 43, 212, 113 respectively. The Editor also requantized HMAP/SMAP, changed vertex colors/minimap and updated document metadata. These companion differences are retained as evidence, not copied into the Pnp writer.

The baseline is the previously user-saved v115 source, not a fresh no-operation save of this copy; provenance is explicit in `experiments/pathing-ground/experiment.json`. Therefore the standard experiment-compare guard correctly refused to call it a newly normalized pair. A direct comparison is recorded separately. The user's short report does not independently confirm save/reopen acceptance or runtime behavior.

`pathing` now writes/clears complete world cells with 255/0. The generated PathingWrite comparison clears A `(52,68)` and paints a 2x2 whole-cell patch at B `(60,68)`. In response to the requested save/close/reopen check, the user reported correct results. Saved Pnp bytes exactly match the generated hash. This establishes scoped `Editor accepted` for Pnp whole-cell painting and clearing on this MarSara case; packaged traversal and other masks remain unconfirmed.

The DoodadBlockers diagnostic uses a deliberately assigned synthetic local rectangle (not measured RockSmall collision), moves the probe from `(68,76)` to `(72,76)` and rotates 90 degrees; owned Pnp follows automatically while the old area restores to its exact baseline. In response to the requested save/reopen check, the user confirmed C/D were correct, but the stone was not visible. Pnp exactly retained its generated hash. This establishes scoped `Editor accepted` for the supplemental-mask transform/restoration; stone visibility and actual model footprint size are separate.

## Absolute-height doodad burial — fixed and Editor accepted

The saved probe still contained RockSmall Id 2725 at `(72,76,9.923085451)`, with `HeightAbsolute=1`, normal scale and no hidden flag. The source position `(68,76)` had reconstructed ground 9.9230854512, while the new location had ground 11.9235381432. The move retained absolute Z while crossing terrain two units higher. A regression reproducing this move and a duplicate both failed with Z=10 instead of expected 12 before the source fix.

The shared object operation now preserves terrain-relative height on absolute-height doodad moves/copies and XY alignment/distribution. Explicit XYZ and Z alignment retain Z by default; `snap` and `keep-z` are explicit alternatives. Sampling uses current HMAP with unit terrain scale/zero offset and refuses interpolation across mixed cliff samples. Regression also covers fractional interpolation, explicit fixed Z, vertical offsets, snap without XY movement, alignment and automatic blocker synchronization.

`GroundedBlocker.SC2Map` changes only the stone's absolute Z to 11.923538143. The user confirmed it was correct in response to the requested visibility/contact and save/reopen check. Objects retained its generated hash, and Pnp remained unchanged. Replaying the original add/move/marker operations through the current default grounding logic produces byte-identical Objects, Pnp and Regions to that accepted corrected map. This establishes scoped `Editor accepted` for this grounded pose and equivalent automatic move result. Other model pivots, bridges/platforms, mixed cliff geometry and packaged traversal remain separate.

## Basic object and region placement — Editor accepted

`BasicObjects.SC2Map` adds Marine units at `(52,84)` and `(56,84)`, moves the latter to `(60,84)`, and creates then deletes a third unreferenced probe. The same operations use existing RockSmall templates at y=88. Rectangular regions are added at `[50,92,52,94]` and `[54,92,56,94]`, with the latter moved to `[60,92,62,94]`; a third region is created then removed. Surviving probes are named `SC2Probe_*_Added` or `SC2Probe_*_Moved`; deleted probes have no surviving records.

In response to the requested save/close/reopen check, the user reported normal results. Both generated Objects and Regions hashes are unchanged after that check. This establishes scoped `Editor accepted` for these same-kind template additions, moves and unreferenced deletions, including the tested rectangular region shapes. It does not establish all asset types, all properties, rotation, footprints or runtime movement. The user subsequently requested intentional facing and supplemental blocking from scenery; facing now has a target-point writer with static regression, while automatic footprint-derived paint still requires native encoding and footprint evidence.

## New straight road — Editor accepted

The user drew a native Mar Sara Road with width 1 near `(52,68)` to `(60,68)`. The new HRDT group uses type MarSaraTile and two 58-byte endpoint records. Position fields and opposite unit direction vectors match the measured 3D chord. The profile's other fields, endpoint flags and opaque group suffix are retained when making a new straight road.

The generated `RoadWrite.SC2Map` contains the new segment `(52,64)` to `(60,64)`, with endpoint heights reconstructed from the local HMAP on gentle single-level ground. In response to the requested save/close/reopen check, the user reported a width-1 Mar Sara Road at those endpoints. This establishes scoped `Editor accepted` for straight-profile addition. The original segment's visual deletion was not separately reported and is not included in that acceptance. General curves, width/material modification, steeper terrain and runtime appearance remain separate.

## Foliage scatter ordering — Editor accepted

The Zerus probe clears `[24,144,30,150]` (82 original records) and replaces `[32,144,38,150]` (94 original records) with 108 seeded entries using observed flag 4. The user reported no automatic foliage in A and no clear newly scattered foliage in B, while ordinary doodads remained. Other map areas show automatic foliage, so global display suppression is not the current explanation.

After the requested save/reopen, all generated DLFT bytes remained identical and B still contained all 108 records. Both original and generated B positions occupy LFCT cells with value 2; both centers have reconstructed ground height about 11.96 and no covering water rectangle. Eight existing texture/flag combinations also showed no new foliage while their generated records were appended at the end of a 47,044-record array.

An order-only diagnostic moved those same records to the front, preserving their exact byte multiset, positions and textures. The user then saw foliage in strips 2..4. This confirms that record order affected visibility in this case; a precise engine budget or selection algorithm has not been established. Default scatter now prepends new entries while preserving existing record contents and relative order.

`FoliageFixed.SC2Map` repeats the original B patch with the identical 108 flag-4 entries, seed, density and blended terrain; only the record order differs. In response to the requested save/reopen check, the user confirmed A remained clear and B now displayed automatic foliage. This establishes scoped `Editor accepted` for clearing and corrected seeded scatter on that Zerus profile. Other profiles and packaged runtime remain separate. Reference format notes describe the record flag without establishing its asset semantics ([primary format research](https://github.com/sc2-arcade-watcher/sc2-file-format-docs/blob/main/t3fluffdoodad.md)).

## Uprising adaptation — distinct manual, GUI and gameplay scopes

The later source is the user's community Uprising Liberation Day Components map, adapted to the explicitly selected LoyalWOL/Kit dependency chain. Its project files remain separate from the initial x2 corpus.

- **Manual resize:** the operator changed the adapted experiment from 208×184 to 208×208 by adding 24 to the north, preserving old coordinates and extending playable/camera bounds. The user confirmed save/reopen success and closure. This is scoped `Editor accepted` for that manual resize, not a generated arbitrary resize writer.
- **Manual cliff sample:** on the separate already saved v115 experiment, the operator used a size-16 square Lower Cliff brush near `(154,188)`, lowering two levels, and confirmed save/reopen success. Project helpers later reused witnessed cells. Manual sample acceptance does not establish their arbitrary topology output, corner cases or native traversal.
- **Visual feedback:** the user reported the first expansion as coarse, then the Polished scene as still too empty. New substantial scenery, an intact-bridge candidate and the tunnel-floor connection were written to Improved. Neither the final scene composition nor those crossings have user-accepted visual/travel results.
- **GUI organization:** on 2026-10-27 the user confirmed that the Improved map and LoyalWOL retained their folders and compiled normally after saving, closing and reopening, then closed both. The record `projects/liberation-day-expanded/reports/uprising-gui-organization.json` binds saved component hashes and caller-attested evidence. Its `Editor accepted` scope is directory persistence and compilation; it cannot promote the same map's terrain or gameplay.

Current bridge/tunnel travel, rescue movement, voiced playback and permanent reward behavior have no `packaged runtime passed` result. Their static component and GUI-state checks remain separate. Use the [adaptation workflow](map-adaptation.md) for the reusable lessons; local helper paths and design values are examples, not additions to the generic capability ledger.
