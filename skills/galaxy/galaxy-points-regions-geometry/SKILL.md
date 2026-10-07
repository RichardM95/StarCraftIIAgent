---
name: galaxy-points-regions-geometry
description: Points, regions, geometry, pathfinding, and map coordinate helpers in Galaxy script. Use when working with point creation, distance calculations, offsets, region checks, PointWithOffset, PointWithPolarProjection, region creation, or testing if a unit or point is inside a region.
---

## Loading Boundary

- **This sub-skill owns:** points, regions, geometry, pathfinding, and map coordinate helpers (PointWithOffset, PointWithPolarProjection, region checks)
- **Parent root skill (`sc2-galaxy-scripting`) owns:** project conventions, schema/syntax rules, source-of-truth, naming prefixes
- **Sibling sub-skills own:** `galaxy-math-strings-conversion` (numeric math primitives), `galaxy-units-and-groups` (unit position queries), `galaxy-sound-camera-environment` (camera target points)

# Galaxy Scripting – Points, Regions & Geometry

## Prerequisite

Load [`sc2-galaxy-scripting`](../../sc2-galaxy-scripting/SKILL.md) first for project-wide Galaxy syntax constraints (variable hoisting, no `++`/`--`, `while` not `for`, include paths without extensions), source-of-truth rules, modular script boundaries, and naming conventions (e.g. `libMy_` function prefix, `libMy_g_` global prefix). This sub-skill owns deep API reference only; project conventions live in the router skill.

## Key References

| Resource | URL |
|---|---|
| Native function reference | https://mapster.talv.space/galaxy/reference |
| Galaxy syntax definition | https://github.com/Talv/vscode-sc2-galaxy/blob/master/syntaxes/galaxy.json |
| **SC2-IngameDevTools (PRIMARY — #1 codebase)** | https://github.com/abrahamYG/SC2-IngameDevTools/tree/main/DevToolsIngame.SC2Mod/Script |
| SSF codebase (secondary style) | https://github.com/Cristall/SC2-SwarmSpecialForces/tree/main/SwarmSpecialForces.SC2Map/scripts |
| SC2 editor guides | https://s2editor-guides.readthedocs.io |
| SC2Mapster wiki | https://sc2mapster.wiki.gg/ |

---

## Points

A `point` is a 2D (or 3D with height) map coordinate.

### Creating points

```galaxy
point lv_p = Point(16.5, 32.0);                          // x, y
point lv_p3 = libNtve_gf_PointFromXYZ(16.5, 32.0, 4.0); // x, y, z

// Named point from map (placed in editor)
point lv_named = PointFromName("StartLocation1");
```

### Modifying points

```galaxy
// Move a point in place
PointSet(lv_p, 20.0, 40.0);

// Set facing angle on a point
PointSetFacing(lv_p, 90.0);

// Set height
PointSetHeight(lv_p, 2.0);
```

### Reading point components

```galaxy
fixed lv_x = PointGetX(lv_p);
fixed lv_y = PointGetY(lv_p);
fixed lv_facing = PointGetFacing(lv_p);
fixed lv_height = PointGetHeight(lv_p);
```

### Measurements between points

```galaxy
fixed lv_dist  = DistanceBetweenPoints(lv_a, lv_b);
fixed lv_angle = AngleBetweenPoints(lv_a, lv_b);  // degrees, from lv_a toward lv_b
```

### Offsets and movement

```galaxy
// Create new point offset by x/y
point lv_offset = PointWithOffset(lv_origin, lv_dx, lv_dy);

// Move in a direction (polar)
point lv_ahead  = PointWithOffsetPolar(lv_origin, lv_distance, lv_angleDegrees);

// Step from A toward B by a distance
point lv_step   = libNtve_gf_PointOffsetTowardsPoint(lv_a, lv_b, lv_dist);

// Add Z offset (above terrain)
point lv_above  = libNtve_gf_PointWithZOffset(lv_p, 2.5);

// Point at the facing angle of another point
point lv_front  = libNtve_gf_PointFacingAngle(lv_p, lv_range);
```

### Terrain queries at a point

```galaxy
fixed lv_h      = WorldHeight(lv_p);            // terrain height
string lv_tex   = TerrainTexture(lv_p);         // terrain texture id
int    lv_cliff = CliffLevel(lv_p);             // cliff height level (int)
fixed  lv_cliff2 = PointPathingCliffLevel(lv_p); // cliff level (fixed)
bool   lv_pass  = PointPathingPassable(lv_p);   // is ground passable?
bool   lv_conn  = PointPathingIsConnected(lv_a, lv_b); // are pts connected?
int    lv_cost  = PointPathingCost(lv_a, lv_b); // pathing cost
```

---

## Regions

A `region` is an area shape (rectangle, circle, polygon) that can be placed in the editor or created in code.

### Useful predefined regions

```galaxy
region lv_all  = RegionEntireMap();     // the whole map
region lv_play = RegionPlayableMap();   // playable area only
region lv_emp  = RegionEmpty();         // zero-size region
region lv_named = RegionFromName("MySpawnRegion");
```

### Creating regions in code

```galaxy
// Rectangle (from two corners)
region lv_rect = RegionRect(lv_minPt, lv_maxPt);

// Circle
region lv_circle = RegionCircle(lv_center, 8.0);

// Add/subtract regions
RegionAdd(lv_dest, lv_addRegion);
RegionRemove(lv_dest, lv_removeRegion);
```

### Region measurements

```galaxy
point lv_center = RegionGetCenter(lv_region);
point lv_min    = RegionGetBoundsMin(lv_region);
point lv_max    = RegionGetBoundsMax(lv_region);
fixed lv_width  = PointGetX(lv_max) - PointGetX(lv_min);
fixed lv_height = libNtve_gf_HeightOfRegion(lv_region);
```

### Point-in-region tests

```galaxy
bool lv_in = RegionContainsPoint(lv_region, lv_point);
```

### Random point inside a region

```galaxy
point lv_rand = RegionRandomPoint(lv_region);
```

### Region events

```galaxy
// Fire when a unit enters or leaves
TriggerAddEventUnitRegion(myTrigger, null, lv_region, true);   // enter
TriggerAddEventUnitRegion(myTrigger, null, lv_region, false);  // leave

// Inside handler
unit   lv_ent = EventUnit();
region lv_reg = EventUnitRegion();  // which region triggered
```

---

## Pathing

```galaxy
// Does a line cross a cliff edge?
bool lv_cross = CrossCliff(lv_from, lv_to);

// Pathing type constants (returned by PathingType)
c_pathingTypeAny
c_pathingTypeGround
c_pathingTypeAir
c_pathingTypeWalkable
```

---

## Visibility

```galaxy
// Reveal area for a player (removes FoW)
VisRevealArea(lv_player, lv_region, 0.0, false);

// Explore (permanent reveal without sight)
VisExploreArea(lv_player, lv_region, true, false);

// Check if a point is currently visible
bool lv_vis = VisIsVisibleForPlayer(lv_player, lv_point);

// Enable/disable FoW
VisEnable(lv_player, false);  // disable fog of war for player

// FoW alpha (0 = fully transparent)
VisSetFoWAlpha(0.5);
VisResetFoWAlpha();

// Revealer (persistent vision source at a point)
VisRevealerCreate(lv_player, lv_point, 12.0);
revealer lv_rev = VisRevealerLastCreated();
VisRevealerEnable(lv_rev, true);   // enable/disable without destroying
VisRevealerDestroy(lv_rev);
```

---

## Creep

```galaxy
// Check if Zerg creep is present at a point
bool lv_hasCreep = CreepIsPresent(lv_point);

// Add or remove creep in a radius
CreepModify(lv_point, 5.0, true,  false);  // add creep (spread = false)
CreepModify(lv_point, 5.0, false, false);  // remove creep
```

---

## Minimap Pings

```galaxy
PingCreate(PlayerGroupAll(), lv_point, 5.0, ColorWithAlpha(1.0, 0.0, 0.0, 1.0), "");
ping lv_ping = PingLastCreated();
PingSetDuration(lv_ping, 8.0);
PingDestroy(lv_ping);
PingDestroyAll();
```

---

## Text Tags (Floating World-Space Text)

Display floating text above a map location:

```galaxy
TextTagCreate();
int lv_tag = TextTagLastCreated();

TextTagSetText(lv_tag, StringToText("+50"), 14, false, PlayerGroupAll());
TextTagSetColor(lv_tag, ColorWithAlpha(1.0, 0.9, 0.0, 1.0), PlayerGroupAll());
TextTagSetPosition(lv_tag, lv_point, 1.0, false);
TextTagSetVelocity(lv_tag, 0.0, 45.0, 0.5, false);   // float upward
TextTagSetLifespan(lv_tag, 2.5);                       // disappear after 2.5s
TextTagSetFadeTime(lv_tag, 1.0);                       // fade last 1s
TextTagShow(lv_tag, true, PlayerGroupAll());

// Attach to a unit (floats with the unit)
TextTagAttachToUnit(lv_tag, lv_unit, 1.0, false);
```
