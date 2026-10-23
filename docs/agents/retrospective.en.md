# Evidence and selection of Ihanrii development lessons

[中文](retrospective.md)
<!-- translation-source: docs/agents/retrospective.md; sha256: 18d86df98daa30ab72dbad7085960d0a9688bf87ade576071e19e86e1403bb9f -->

Author: 扯蛋虾米. This page scopes reusable lessons for maintaining the agent. Project statistics, heroes and mission contracts remain in project data/current source; historical chat never overrides current source.

## Source scope

On 2026-10-21 the archive interface was paged through all 591 turns of eight core chats, plus the latest six turns of two maintenance chats. User corrections, conclusions, counterexamples and acceptance evidence were reviewed. Images were not all reinterpreted; game tests were not rerun. Interrupted/failed turns and assistant completion claims are not acceptance.

The following provenance titles are retained in their original Chinese; IDs/counts identify the sources:

| Source | Original archived title | Chat ID | Turns |
|---|---|---|---:|
| S1 | 帮我检查下为什么使用太阳能射线枪之后会导致游戏越来越卡 | `01a0d073-a8d7-73b0-ad90-24877f228013` | 31 |
| S2 | 伊罕利纪元议会升级 | `01a0b259-dceb-77e3-a1ff-20d87b4ad1f6` | 264 |
| S3 | 修改地图目标 | `01a1435c-ebe4-7433-ae80-021cc3d5f8fa` | 18 |
| S4 | 我更新了依赖项文件，SCORE-Ihanrii.SC2Mod是新依赖项，SCORE-Ihanrii.SC2Mod.ba… | `01a134bb-e91f-7a11-8b66-7c7d2da272f0` | 32 |
| S5 | 天空之盾和战火兄弟都有几乎触发闪退。天空之盾13分钟左右，攻打完左下角莫比斯的阵地后闪退 | `01a0f343-8624-7f03-9441-5d7fcea6e79e` | 22 |
| S6 | 伊罕利英雄设计与调整 | `01a0d1de-df6a-71a1-bc5c-d10969131f57` | 208 |
| S7 | 当前主模组的Epilogue Selection Dialog中还有不少使用自定义代码的内容，先了解galaxy脚本，… | `01a15222-4ea8-7f60-adf1-9eec9498ee06` | 13 |
| S8 | 泽瑞拉的共鸣之盾能否在死亡后重新折跃泽瑞拉仍然继承层数？先帮我给我实现方案 | `01a0e1d7-d21a-7683-9068-e08f12e1fe3d` | 3 |

Auxiliary chats: 01a111b7-d25f-7442-a47e-52f705539ec4 (project-data separation/independent workspace), and 01a11672-71fd-7e50-a603-0fe102973c7d (official trigger queries/Hub boundaries). Only agreements applicable to this independent workspace are adopted.

## Reusable lessons

- S1, turns 01a15d5a-a357-7fe2-9d88-e7c8889bb185 and 01a15d95-cdb4-7f13-8938-d7e7c43f8c05: missing global registration generated undeclared lv_; shared mutable initializer Params lost references on save. Check declarations, registration and instance ownership separately. Reuse definitions, not mutable calls. See [trigger knowledge](../../wiki/reference/trigger-knowledge.en.md).
- S1, 01a0e10b-1dca-7e20-90e8-3134461a916c and 01a12994-1d3f-7712-a7c1-042381b3a672: claimed cleanup had no executable code, or fixes never reached generated scripts. Verify real calls/paths then generated output; nodes/names/tests alone prove no execution. See [handoff](../../wiki/guides/editor-handoff.en.md).
- S7, 01a15296-78ce-71c1-a2ae-943bf3becbb1: disabling a popup did not prevent crashes; six stacks pointed to building placement before campaign AI startup. An independent EventUnit error was separate. Isolate faults with controlled comparisons/stacks, use iterated objects in periodic scans and check subsystem preconditions.
- S5 top-bar restoration failed; later logs identified layout bounds. S3 black blocks came from overriding official texture paths. Identify presentation surface/assets before changing terrain/logic, and correlate logs to reproduction.
- S4, 01a14326-1af6-75b2-8a1f-81ef201870d3: production-command changes affected ArmyUnit/ArmyCategory/Actor/Upgrade and new dependency events. Audit consumers/inheritance and apply only the effective missing change, avoiding duplicate bulk replacements. See [production patterns (English original)](../../wiki/implementation/xml-patterns/production.md) (English technical reference).
- S3: rescue-before-discovery meant no objective handle; survival rewards froze before animation and committed on victory. Make event order idempotent, separating session state, result freeze and permanent commit.
- S6, 01a15d18-6539-7e41-8966-828655d27163: initialization duplicated native cooldown; damage sharing could consume temporary-unit cleanup damage. Separate deployment/evolution/respawn initialization from normal cast; evaluate frequency, damage source and cleanup.
- S8: user requested mod-layer pure GUI; a new respawned unit does not automatically retain old behaviors. Honor requested write scope and verify ownership/event timing/lifetime.
- S1: victory transitions and ordinary saves used different load paths. Distinguish disk Bank, memory and transition initialization. See [Bank reference (Chinese original)](../../wiki/implementation/bank-system.md) (English).

Runtime cases are explained in [runtime diagnosis](../../wiki/implementation/runtime-diagnostics.en.md); source labels identify evidence, not universal engine rules.

## Claims not promoted

Undestroyed timers, dense searches or many models are performance hypotheses; later S1 still reported accumulation, so no proven leak/FPS fix. Brief idle success in S7 did not cover choices/later AI/all missions. S2's energy display recovered by user report, not an agent repair. S4's healing candidate lacked runtime causal evidence. Historical hero values, reverted designs, Epi_Main and Bank names are not new-project defaults; verify present Triggers even when an old epilogue script was replaced by GUI.

## Future archive reviews

List relevant chats and page all needed turns, prioritizing user corrections/latest valid conclusions. Resolve conflicts using current source/newer observations. Update existing reusable topics with scope/provenance; project conclusions go through tools/project-paths.py. Do not copy entire chats or create change diaries. A rule must change a future action/check to justify entry context.
