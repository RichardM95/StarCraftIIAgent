---
name: sc2-art
description: SC2 美术任务入口，按按钮图标、单位肖像和战场单位外观分流，涵盖参考选材、现有模型改造及视觉回查。
---

# SC2 美术

先确认玩家看到的位置、需要保留的身份特征、目标项目和所需交付物。

| 交付物 | 专业技能 |
|---|---|
| 按钮、技能、天赋、状态图标 | [图标绘制](../sc2-icon-art/SKILL.md)，使用已有 856 枚原图库 |
| 单位动态肖像、静态回退图、取景与灯光 | [单位肖像](../sc2-unit-portrait/SKILL.md) |
| 战场单位的模型、材质、配色、动画与附着表现 | [单位外观与 Actor](../sc2-unit-actor-art/SKILL.md) |

命名及说明文字转[数据命名与文本](../sc2-data-naming-and-text/SKILL.md)。不可见、重复 Actor、贴图错位等接线故障进入 [Actor 系统](../sc2-actor-system/SKILL.md)。需要操作项目资源时使用既有 Catalog、素材事务和编辑器交接入口。

[四组 SCORE 接线案例](references/score-actor-cases.json)记录本地声明与来源哈希。缺少显式 Model、依赖中的 PortraitActor 或父级字段时，先解析活动依赖和有效值。声明检查、静态图片观察、编辑器预览和打包运行分别保存证据。

[五类外观回查与四组预览交接](references/score-review.md)列出证据范围和待补项。
