"""Basic map-editing requirements, with the former full-module backlog retained."""

EDITOR_BASELINE = '5.0.15.98370'
BASIC_ACTIONS = {
    'height': 'raise lower smooth noise uniform',
    'brush': 'rectangle circle diamond falloff strength',
    'texture': 'add remove set uniform blur',
    'cliff': 'raise lower same-level change-type stamp-isolated-island',
    'ramp': 'add remove direction',
    'terrain-object': 'add move remove show-cells hide-cells',
    'water': 'add-rectangle update-rectangle remove-rectangle local-height local-state-properties clone-local-type',
    'road': 'add-straight-template duplicate-group move-group remove-group',
    'foliage': 'scatter-existing-flag remove-instances allow disallow density regenerate',
    'lighting': 'add remove',
    'creep': 'paint remove',
    'visibility': 'paint remove',
    'pathing': 'ground remove-ground doodad-blockers',
    'unit': 'template-add update-properties duplicate move rotate face-target delete-unreferenced',
    'doodad': 'template-add update-properties duplicate move rotate face-target scale grounding delete-unreferenced',
    'point': 'template-add update-properties duplicate move delete-unreferenced',
    'region': 'add-circle add-rect add-diamond update move union-copy delete-unreferenced',
    'history': 'plan preview apply diff undo redo',
    'preview': 'height cliffs water unit doodad point regions grid distance object-locate compare',
}
SOURCES = [
    'https://s2editor-guides.readthedocs.io/New_Tutorials/02_Terrain_Editor/019_Terrain_Editor_Interface/',
    'https://s2editor-guides.readthedocs.io/New_Tutorials/02_Terrain_Editor/020_Terrain_Layer/',
    'https://s2editor-guides.readthedocs.io/New_Tutorials/02_Terrain_Editor/021_Units_Layer/',
    'https://s2editor-guides.readthedocs.io/New_Tutorials/02_Terrain_Editor/022_Doodads_Layer/',
    'https://s2editor-guides.readthedocs.io/New_Tutorials/02_Terrain_Editor/023_Points_Layer/',
    'https://s2editor-guides.readthedocs.io/New_Tutorials/02_Terrain_Editor/024_Regions_Layer/',
    'https://s2editor-guides.readthedocs.io/New_Tutorials/02_Terrain_Editor/025_Cameras_Layer/',
    'https://s2editor-guides.readthedocs.io/New_Tutorials/02_Terrain_Editor/026_Pathing_Layer/',
    'https://github.com/sc2-arcade-watcher/sc2-file-format-docs',
]

# group, actions, implementation, operation, remaining evidence/work.
ROWS = [
    ('height', 'raise lower smooth noise', 'experimental', 'height', 'User accepted +1.0 raise on channels 0/1 in the MarSara diagnostic map; other modes and simulation behavior need separate proof'),
    ('height', 'set', 'needs_editor_pair', None, 'Absolute height, geometry scale/origin and sync conversion'),
    ('height', 'uniform', 'experimental', 'height', 'Sample a vertex within the same cliff level; absolute world-height conversion remains unimplemented'),
    ('brush', 'rectangle circle diamond falloff strength iterations seed', 'experimental', 'height/texture', 'Compare brush footprints and falloff against Editor'),
    ('brush', 'increment speed freehand custom-shape flood-fill', 'needs_editor_pair', None, 'Brush stroke sampling and per-brush fill boundaries'),
    ('texture', 'add remove set uniform blur', 'experimental', 'texture', 'User accepted 8x8 MarSaraDirt set patches after save/reopen; other modes and surface simulation properties need proof'),
    ('texture', 'fill allocate-texture-set change-texture-palette', 'needs_editor_pair', None, 'Block set allocation and catalog/sync palette updates'),
    ('cliff', 'raise lower same-level change-type shape', 'needs_editor_pair', None, 'Cliff cell topology, HMAP/CLIF/SMAP, mesh and pathing regeneration'),
    ('cliff', 'stamp-isolated-island', 'experimental', 'cliff-stamp', 'Reuse an Editor-authored two-level island on a compatible flat v115 area; general cliff drawing remains unimplemented'),
    ('ramp', 'add remove direction width style', 'needs_editor_pair', None, 'Paired XML and binary topology changes'),
    ('terrain-object', 'add move remove show-cells hide-cells', 'needs_editor_pair', None, 'Catalog footprint, cliffDoodadList and cell visibility bits'),
    ('water', 'add-rectangle update-rectangle remove-rectangle', 'experimental', 'water', 'Existing water configuration IDs only; rectangle visual roundtrip'),
    ('water', 'new-type state height', 'needs_editor_pair', None, 'Water configuration ownership and state/height serialization'),
    ('water', 'local-height local-state-properties clone-local-type clone-local-state', 'experimental', 'water-config', 'Explicit map-local state fields only; no inherited-value guessing or runtime state-selection claim'),
    ('road', 'duplicate-group move-group remove-group', 'experimental', 'roads', 'Whole HRDT groups only; confirm road versus other hard-tile use'),
    ('road', 'add-straight-template', 'experimental', 'roads', 'Native straight two-endpoint profile; new XY endpoints on gentle single-level terrain; preserve profile width/material and opaque fields; generated-map acceptance pending'),
    ('road', 'new-spline move-control-point width type join split', 'needs_editor_pair', None, 'Road control-point storage, mesh tessellation and UV generation'),
    ('foliage', 'scatter-existing-flag', 'experimental', 'foliage', 'Newly scattered entries precede existing ones; scoped Zerus flag-4 default writer accepted; other visible native flag/texture profiles still require evidence'),
    ('foliage', 'remove-instances', 'experimental', 'foliage', 'User confirmed clear area in Zerus probe; scope acceptance tracked separately'),
    ('foliage', 'prioritize-instances', 'experimental', 'foliage', 'Stable selected-prefix ordering; user observed visible Zerus flags 2..4 after order-only change; exact rendering budget remains unmeasured'),
    ('foliage', 'allow disallow density regenerate', 'needs_editor_pair', None, 'Paint flags and Editor foliage generator behavior'),
    ('lighting', 'add remove', 'experimental', 'lighting', 'Paint existing Editor light regions 1/2 at four pixels per world cell; generated-map acceptance and actual appearance pending'),
    ('lighting', 'uniform blur fill regions', 'needs_editor_pair', None, 'Additional regions, brush rules and linked light definitions'),
    ('lighting', 'read-raster', 'diagnostic', 'inspect/audit/diff', 'Lossless observed BGRA TGA; image coordinates are not yet linked to named light-region channels'),
    ('creep', 'paint remove', 'experimental', 'creep', 'Whole-world-cell CellAttribute_Cpl painting/clearing on unit-scale zero-offset maps; finer native brush samples, legacy migration and runtime creep sources remain separate'),
    ('creep', 'allow disallow fill', 'needs_editor_pair', None, 'Creep permission rules and native subcell/fill behavior need independent Editor pairs'),
    ('visibility', 'paint remove', 'experimental', 'visibility', 'Whole-cell CellAttribute_Vbl vision blockers; generated-map acceptance and runtime line-of-sight pending; global fog and unexplored areas are separate'),
    ('unit', 'template-add update-properties duplicate move rotate scale align distribute replace-existing-type delete-unreferenced', 'experimental', 'objects', 'Existing same-kind templates/types; all unobserved property dialogs remain unimplemented'),
    ('unit', 'arbitrary-catalog-placement all-properties', 'needs_editor_pair', None, 'Catalog availability and complete property/reference/footprint semantics'),
    ('unit', 'face-target', 'experimental', 'objects', 'Absolute atan2 facing from final position, static regression passed; rendered forward axis needs Editor evidence'),
    ('unit', 'schema-properties ai-active ai-rebuild ai-flags difficulty-resources', 'experimental', 'objects/object-schema', 'Schema-defined attributes/indexed children; assets and full dialog/runtime semantics need evidence'),
    ('doodad', 'template-add update-properties duplicate move rotate scale align distribute replace-existing-type delete-unreferenced', 'experimental', 'objects', 'Existing templates; verify height mode, variation and ground contact'),
    ('doodad', 'arbitrary-catalog-placement all-properties', 'needs_editor_pair', None, 'All placement filters/options, attachment and catalog/footprint semantics'),
    ('doodad', 'face-target', 'experimental', 'objects', 'Absolute target facing respects final position; visual axis/symmetric models and rotated blocking need verification'),
    ('doodad', 'grounding', 'experimental', 'objects', 'Absolute-height doodad moves/copies/XY alignment preserve terrain-relative offset; explicit XYZ keeps Z, opt-in snap/keep-z. Corrected MarSara RockSmall snap accepted; current automatic-move replay matches accepted Objects/Pnp/Regions. Unit-scale zero-offset HMAP terrain only; sampled cliff-edge interpolation refused'),
    ('doodad', 'schema-properties sound-height-flags', 'experimental', 'objects/object-schema', 'Known schema fields and indexed children; source asset availability still needs validation'),
    ('point', 'template-add update-properties duplicate move rotate delete-unreferenced', 'experimental', 'objects', 'Normal points only; existing typed references retained'),
    ('point', 'start-location add-special-types attachment-link', 'needs_editor_pair', None, 'MapInfo start_loc arrays, player linkage and special point properties'),
    ('point', 'schema-properties flags', 'experimental', 'objects/object-schema', 'Schema-defined fields/flags; reference identities remain protected'),
    ('region', 'add-circle add-rect add-diamond update move union-copy delete-unreferenced', 'experimental', 'regions', 'Union copies shapes and preserves source identities; verify composite shapes'),
    ('region', 'subtract intersect merge-delete-source all-properties', 'needs_editor_pair', None, 'Editor composite semantics and reference migration'),
    ('camera', 'template-add duplicate move rotate update-existing-values delete-unreferenced', 'experimental', 'objects', 'Position, target and yaw transformed together; verify other camera values'),
    ('camera', 'create-from-view all-properties render-camera-view', 'needs_editor_pair', None, 'Complete camera geometry, DOF/exposure semantics and native rendered preview'),
    ('camera', 'schema-lens-values flags', 'experimental', 'objects/object-schema', 'Known schema camera-value indices can be inserted/updated/removed; visual validation remains pending'),
    ('pathing', 'read-raw-overlay', 'diagnostic', 'render', 'Raw paint bytes are not labeled as walkable/unwalkable'),
    ('pathing', 'ground remove-ground', 'experimental', 'pathing', 'Scoped MarSara Pnp whole-cell 255/0 paint/remove accepted after save/reopen; legacy paint, finer samples, other masks and runtime traversal excluded'),
    ('pathing', 'air building no-build fill dynamic-blockers cell-attributes', 'needs_editor_pair', None, 'Separate paint lookup tables, native footprints and generated pathing'),
    ('pathing', 'doodad-blockers', 'experimental', 'doodad-blockers', 'Explicit local static occupancy rectangles transformed with placed rotation/scale; native profiles skipped; owned contributions follow object edits and preserve original/overlapping paint. Synthetic-rectangle C/D comparison accepted; whole-cell precision, actual occupancy evidence and runtime remain separate; arbitrary Catalog inference excluded'),
    ('selection', 'kind ids name type player rectangle', 'experimental', 'select', 'Exact filters; no native palette/UI reproduction'),
    ('selection', 'lasso connected visibility difficulty tags', 'needs_editor_pair', None, 'Additional selection and view-filter semantics'),
    ('edit', 'object-duplicate object-move object-rotate object-mirror object-align object-distribute group ungroup', 'experimental', 'objects', 'Group IDs separate from placed IDs; test all selected kinds'),
    ('edit', 'terrain-copy terrain-paste terrain-mirror cross-map-paste reference-remap', 'needs_editor_pair', None, 'Coordinated raster/topology/object transforms and typed reference migration'),
    ('history', 'plan preview apply diff undo redo', 'implemented', 'plan/apply/diff/undo/redo', 'Hash-bound plans, staged publication, retained component snapshots; external edits invalidate history'),
    ('map', 'read-dimensions read-bounds set-playable-bounds', 'experimental', 'inspect/bounds', 'MapInfo integrity-hash delta updated; Editor/runtime validation required'),
    ('map', 'resize crop extend change-tileset map-options camera-bounds', 'needs_editor_pair', None, 'All dimensions, block/cell indices, unknown layers, bounds and MapInfo integrity'),
    ('preview', 'height cliffs water unit doodad point camera regions grid raw-pathing', 'diagnostic', 'render', 'SVG coordinates and overlays only; not native SC2 materials or pathfinding'),
    ('preview', 'distance object-locate compare', 'implemented', 'measure/select/diff', 'Euclidean world coordinates and content hashes'),
    ('preview', 'all-native-view-filters skybox sounds textures materials game-view', 'needs_editor_pair', None, 'Native renderer and complete local Editor menu inventory'),
]


def capabilities():
    features = []
    for group, actions, implementation, operation, remaining in ROWS:
        for action in actions.split():
            features.append({'id': group + '.' + action, 'group': group,
                             'active_requirement': action in BASIC_ACTIONS.get(group, '').split(),
                             'implementation': implementation, 'operation': operation,
                             'editor': 'not_run', 'runtime': 'not_run', 'remaining': remaining})
    for feature in features:
        if feature['id'] == 'doodad.grounding':
            feature['editor'] = 'Editor accepted'
            feature['editor_scope'] = 'GroundedBlocker: RockSmall at (72,76), absolute Z corrected 9.923 to 11.924; user confirms visible and grounded after requested save/reopen. Current automatic move replay matches accepted Objects/Pnp/Regions exactly'
            feature['editor_complete'] = False
        if feature['id'] == 'pathing.doodad-blockers':
            feature['editor'] = 'Editor accepted'
            feature['editor_scope'] = 'DoodadBlockers: synthetic local rectangle moved (68,76) to (72,76), rotated 90 degrees; C old area clears and D 2x4 Pnp appears. Stone visibility issue is tracked separately under doodad.grounding'
            feature['editor_complete'] = False
        if feature['id'] in ('pathing.ground', 'pathing.remove-ground'):
            feature['editor'] = 'Editor accepted'
            feature['editor_scope'] = 'PathingWrite: clear native partial Pnp at (52,68), add 2x2 whole-cell no-ground-path at (60,68); exact generated Pnp retained after user save/reopen'
            feature['editor_complete'] = False
        if feature['id'] in ('unit.template-add', 'unit.move', 'unit.delete-unreferenced',
                              'doodad.template-add', 'doodad.move', 'doodad.delete-unreferenced',
                              'region.add-rect', 'region.move', 'region.delete-unreferenced'):
            feature['editor'] = 'Editor accepted'
            feature['editor_scope'] = 'BasicObjects: Marine and RockSmall additions/moves/deletions, rectangular region additions/moves/deletions; generated Objects and Regions bytes retained after user save/reopen'
            feature['editor_complete'] = False
        if feature['id'] == 'foliage.scatter-existing-flag':
            feature['editor'] = 'Editor accepted'
            feature['editor_scope'] = 'FoliageFixed: Zerus [32,144,38,150], flag 4, density 3, seed 20261026, 108 new entries prioritized first'
            feature['editor_complete'] = False
        if feature['id'] == 'foliage.prioritize-instances':
            feature['editor'] = 'Editor accepted'
            feature['editor_scope'] = 'FoliagePriority: only record order changed; Zerus strips 2..4 became visible'
            feature['editor_complete'] = False
        if feature['id'] == 'foliage.remove-instances':
            feature['editor'] = 'Editor accepted'
            feature['editor_scope'] = 'FoliageWrite: Zerus region [24,144,30,150], 82 original records removed; user reports no automatic foliage there'
            feature['editor_complete'] = False
        if feature['id'] == 'road.add-straight-template':
            feature['editor'] = 'Editor accepted'
            feature['editor_scope'] = 'RoadWrite: MarSara v115, new width-1 Mar Sara Road from (52,64) to (60,64)'
            feature['editor_complete'] = False
        if feature['id'] in ('lighting.add', 'lighting.remove'):
            feature['editor'] = 'Editor accepted'
            feature['editor_scope'] = 'LightingWrite: MarSara existing raster, default region 1 at (52,68), region 2 at (60,68)'
            feature['editor_complete'] = False
        if feature['id'] in ('visibility.paint', 'visibility.remove'):
            feature['editor'] = 'Editor accepted'
            feature['editor_scope'] = 'VisibilityWrite: MarSara v115, clear original blockers near (52,68), paint new blockers near (60,68)'
            feature['editor_complete'] = False
        if feature['id'] in ('creep.paint', 'creep.remove'):
            feature['editor'] = 'Editor accepted'
            feature['editor_scope'] = 'CreepWrite: MarSara v115, clear existing 2x2 world cells near (52,68), paint new 2x2 cells near (60,68)'
            feature['editor_complete'] = False
        if feature['id'] in ('height.raise', 'texture.set', 'cliff.stamp-isolated-island'):
            feature['editor'] = 'Editor accepted'
            feature['editor_scope'] = ('CliffStamp: compatible flat MarSara v115, one isolated island centered at (70,58), radius 4'
                                       if feature['id']=='cliff.stamp-isolated-island' else
                                       'ChannelProbe: MarSara, +1.0 height channels 0/1; texture slot 0, two 8x8 rectangles')
            feature['editor_complete'] = False
        if feature['id'] in ('water.local-height','water.local-state-properties','water.clone-local-type','water.update-rectangle'):
            feature['editor']='Editor accepted'
            feature['editor_scope']='WaterContrast: Agria local clone/state 0, height 2.2 to 4.2, blue Color and RefractionDistortion=0, existing rectangle reassigned; bed unchanged'
            feature['editor_complete']=False
    observations = [
        {'kind': 'tool_generated', 'features': ['doodad.grounding'],
         'scope': 'GroundedBlocker: explicit snap corrected buried RockSmall at (72,76); accepted bytes also reproduced by current default terrain-offset-preserving move sequence',
         'status': 'Editor accepted', 'runtime': 'not_run',
         'evidence': 'skills/sc2-terrain-editing/references/editor-evidence.md'},
        {'kind': 'tool_generated', 'features': ['pathing.doodad-blockers'],
         'scope': 'Synthetic static rectangle: old C Pnp restored and moved/rotated D Pnp accepted; actual stone visibility was reported missing and does not establish ground contact',
         'status': 'Editor accepted', 'runtime': 'not_run',
         'evidence': 'skills/sc2-terrain-editing/references/editor-evidence.md'},
        {'kind': 'tool_generated', 'features': ['pathing.ground', 'pathing.remove-ground'],
         'scope': 'PathingWrite MarSara: native partial brush cleared at A, full 2x2 Pnp patch painted at B; user reports correct after requested save/reopen',
         'status': 'Editor accepted', 'runtime': 'not_run',
         'evidence': 'skills/sc2-terrain-editing/references/editor-evidence.md'},
        {'kind': 'tool_generated', 'features': ['unit.template-add', 'unit.move', 'unit.delete-unreferenced',
                                              'doodad.template-add', 'doodad.move', 'doodad.delete-unreferenced',
                                              'region.add-rect', 'region.move', 'region.delete-unreferenced'],
         'scope': 'BasicObjects: Marine, RockSmall and rectangular regions; add/move/remove unreferenced probes',
         'status': 'Editor accepted', 'runtime': 'not_run',
         'evidence': 'skills/sc2-terrain-editing/references/editor-evidence.md'},
        {'kind': 'tool_generated', 'features': ['foliage.scatter-existing-flag', 'foliage.prioritize-instances'],
         'scope': 'Zerus order-only diagnostic and corrected default seeded scatter; flags/texture profiles 2..4 visibly confirmed in diagnostic, flag 4 in original B patch',
         'status': 'Editor accepted', 'runtime': 'not_run',
         'evidence': 'skills/sc2-terrain-editing/references/editor-evidence.md'},
        {'kind': 'tool_generated', 'features': ['foliage.remove-instances'],
         'scope': 'Zerus 6x6 area cleared; corrected companion scatter separately accepted',
         'status': 'Editor accepted', 'runtime': 'not_run',
         'evidence': 'skills/sc2-terrain-editing/references/editor-evidence.md'},
        {'kind': 'tool_generated', 'features': ['road.add-straight-template'],
         'scope': 'MarSara v115 native straight profile, grounded endpoints (52,64) and (60,64), width 1',
         'status': 'Editor accepted', 'runtime': 'not_run',
         'evidence': 'skills/sc2-terrain-editing/references/editor-evidence.md'},
        {'kind': 'tool_generated', 'features': ['lighting.add', 'lighting.remove'],
         'scope': 'Existing MarSara LightingMap region-1 restoration and region-2 painting',
         'status': 'Editor accepted', 'runtime': 'not_run',
         'evidence': 'skills/sc2-terrain-editing/references/editor-evidence.md'},
        {'kind': 'tool_generated', 'features': ['visibility.paint', 'visibility.remove'],
         'scope': 'Whole-cell CellAttribute_Vbl vision blockers, MarSara v115 VisibilityWrite comparison',
         'status': 'Editor accepted', 'runtime': 'not_run',
         'evidence': 'skills/sc2-terrain-editing/references/editor-evidence.md'},
        {'kind': 'tool_generated', 'features': ['creep.paint', 'creep.remove'],
         'scope': 'Whole-cell CellAttribute_Cpl painting and clearing, MarSara v115 CreepWrite comparison',
         'status': 'Editor accepted', 'runtime': 'not_run',
         'evidence': 'skills/sc2-terrain-editing/references/editor-evidence.md'},
        {'kind': 'tool_generated', 'features': ['height.raise', 'texture.set'],
         'scope': 'MarSara: two 8x8 rectangles, height +1.0 channels 0/1 and texture slot 0',
         'status': 'Editor accepted', 'runtime': 'not_run',
         'evidence': 'skills/sc2-terrain-editing/references/editor-evidence.md'},
        {'kind': 'manual_experiment', 'features': ['cliff.raise'],
         'scope': 'One user-authored cliff raise; terrain 113 upgraded to 115; not writer acceptance',
         'status': 'Editor accepted', 'runtime': 'not_run',
         'evidence': 'skills/sc2-terrain-editing/references/editor-evidence.md'},
        {'kind': 'tool_generated', 'features': ['cliff.stamp-isolated-island'],
         'scope': 'MarSara v115: reuse isolated one-level island on compatible clear flat area, radius 4',
         'status': 'Editor accepted', 'runtime': 'not_run',
         'evidence': 'skills/sc2-terrain-editing/references/editor-evidence.md'},
        {'kind': 'tool_generated', 'features': ['water.local-height','water.local-state-properties','water.clone-local-type','water.update-rectangle'],
         'scope': 'Agria: explicit local water state 0 clone, height 2.2→4.2, blue high-contrast surface, unchanged terrain; existing rectangle reassigned',
         'status': 'Editor accepted', 'runtime': 'not_run',
         'evidence': 'skills/sc2-terrain-editing/references/editor-evidence.md'},
    ]
    return {'schema_version': 1, 'editor_baseline': EDITOR_BASELINE,
            'scope': 'basic_reference_map_editing', 'full_editor_parity_required': False,
            'local_menu_inventory': {'status': 'partial_layers_confirmed',
                                     'layers': ['地形', '单位', '装饰物', '点', '区域', '镜头', '路径']},
            'complete': False, 'completion_basis': 'active_requirement features require implementation and scoped acceptance',
            'sources': SOURCES, 'features': features, 'observations': observations}
