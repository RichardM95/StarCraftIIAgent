# Attack Wave Concepts

Use this page for underlying SC2 concepts. Add a project guide under `wiki/guides/` when you implement waves on specific maps.

## Two Main Ways SC2 Does Waves

| Approach | Best for |
|---|---|
| AI module / campaign wave system | Existing Blizzard campaign bases that already build and launch waves |
| Direct trigger spawns | Custom reinforcements, enhancement spawns, or scripted ambushes |

## Core Wave Ingredients

- spawn point or rally area
- composition definition
- timing or repeat rule
- pathing checkpoints or target region
- owning AI/enemy player

## Useful AI Terms

| Term | Meaning |
|---|---|
| WaveInfo | Unit composition package for an AI wave |
| Strength / Tech level | Difficulty knobs for quantity and composition |
| Bully units | Pre-placed units the AI can eventually commit |
| Waypoints | Gathering or pathing points before the final target |

## Rule Of Thumb

- If the base game mission already owns the wave system, extend it instead of rebuilding it.
- If we only need to inject extra units, use a direct trigger or `UnitCreate` pattern.
- For no-build or hero-only maps, direct trigger spawns are usually simpler and safer than AI-module edits.

## Common Failure Modes

- spawning units for the wrong player
- using the wrong checkpoint chain so units idle instead of attacking
- assuming a map has a working AI base when it actually uses one-off scripted reinforcements
