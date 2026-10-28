---
name: sc2-official-assets
description: Find official SC2 skins, models, Actors, icons, sounds and campaign/co-op assets, then audit their actual dependency and resource chains through the shared local/MCP implementation.
---

# Official SC2 assets

Follow [shared-tool routing](../sc2-shared-tools/SKILL.md). Open the explicit project read-only, then use `sc2_official_assets_search`, `sc2_official_assets_explain` and `sc2_official_assets_audit`. The CLI calls the same operation names and accepts the same argument objects. The bundled `official-assets.json.gz` is the only maintained snapshot; do not create a second asset table.

Search Skin/SkinPack and WarChest/WarChestSeason for skin families. A skin may replace a Unit's presentation without adding a Unit ID. Query Actor/Model, Sound and Button references for their respective resources; do not infer an independent icon or Doodad Catalog from a display label.

Distinguish player-wide skin application from a coexisting Unit variant before implementation. Inspect ReplacementArray and EffectArray separately, including body, death, corpse, portrait, build/placement, morph, turret and attachment chains. Use [Actor skill](../sc2-actor-system/SKILL.md) and [unit migration](../sc2-unit-migration/SKILL.md) for implementation.

Snapshot membership is metadata evidence, not target dependency membership or resource readability. Specify component where IDs repeat; retain incomplete/unknown statuses. Confirm current dependency order, inheritance and local overrides through existing Catalog tools and the shared SourceContext/asset audit. Locale-specific audio may require locale assets; an enUS probe does not establish a target's language fallback.

Knowledge-index presence, actual resource reads, active dependencies, Editor load, runtime and visual acceptance each require their own evidence. Snapshot coverage/version are obtained from the index at use time; no-match does not prove the game lacks an asset.
