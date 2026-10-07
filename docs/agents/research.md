# 战役研究

研究任务必须产出可复用、范围明确的结果，而不能只留下聊天回答。

尽可能使用第一方来源：官方《星际争霸 II》编辑器文档、Blizzard 制作的资源、本地战役/模组数据和导出的 XML。对于 catalog 事实，先使用 `tools/sc2-catalog-query.py` 查询当前项目、依赖和已索引导出；需要字段原文时读取命中的小片段；需要官方或合作组件的实现先例或本地化时，用 `tools/sc2-reference-query.py` 限定组件、catalog 类型、语言和结果数量。同一研究任务复用已经确认的案例。

将长期有效的发现写入范围最窄的规范位置：

- `wiki/design/`：面向玩家的预期设计、阵营决策和单位机制。
- `wiki/implementation/`：实现契约、校验方法和工作流。
- `wiki/reference/`：稳定的编辑器、Galaxy、XML、catalog 或战役事实。

对每个不明显的结论说明来源和适用范围。如果所需 XML catalog 覆盖缺失，应从 SC2 编辑器导出对应的特定 catalog，不要猜测。
