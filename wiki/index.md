# Wiki 任务路由器

[English](index.en.md)

先阅读 [工作区规则](../AGENTS.md)，当前选择以本机 `agent-config.json` 为准。用户提供主 Components 模组路径后运行 `python tools/init-project.py "<路径>"`。

- 技能：[统一入口](../skills/sc2-project-entry/SKILL.md)，按任务加载专用技能及 Galaxy、SC2 Data 子技能。
- 日常开发请求：[36个开发场景](guides/development-conversations.md)，按单位、表现、触发器、对白、存档和验证分组。
- 技能调用与新能力：[18 个场景与两组多轮对话](guides/skill-conversations.md)，含地形、迁移、官方资源、MCP、模型分包与 Harness2。
- 地形模块制图对话：[26 个图层操作场景与两组多轮对话](guides/terrain-conversations.md)，从选参考、画地形、摆物件到寻路和编辑器续作。
- 工具：[工具指南](../tools/README.md)。未初始化时运行 `python tools/test-suite.py --scope tools` 和 `python tools/test-suite.py --scope docs`。
- 官方依赖：[CASC 诊断、缓存与共用查询](reference/official-casc-cache.md)。
- XML：[模式](implementation/xml-patterns.md)、[Catalog 规则](implementation/xml-patterns/catalog-rules.md)。
- Galaxy：[语法陷阱](implementation/galaxy-gotchas.md)、[语言参考](reference/galaxy-language.md)。
- 本地化：[规则](implementation/localization.md)。
- 触发器：[依赖查询与案例](reference/trigger-knowledge.md)、[游戏对白与对话框](reference/trigger-dialogue-examples.md)、[用户对话示例](reference/trigger-agent-dialogue-examples.md)、[GUI 模板](reference/trigger-templates/README.md)、[XML 概述](reference/triggers-overview.md)、[地图接线](implementation/per-map-setup.md)。
- Bank：[约定](implementation/bank-system.md)、[接口](reference/galaxy-bank.md)。
- 项目初始化：[指南](guides/project-initialization.md)。
- 验收：[反馈流程](implementation/testing-feedback-workflow.md)、[编辑器交接](guides/editor-handoff.md)。
- 基础地形制图：[制图工具与实验](guides/sc2-terrain-editing.md)、[地形技能](../skills/sc2-terrain-editing/SKILL.md)、[改图与场景组织](../skills/sc2-terrain-editing/references/map-adaptation.md)；任务对象与目录整理转[地图GUI改编](../skills/sc2-map-triggers/references/map-adaptation.md)。基础绘制范围以能力清单为准，未实现项保持可见。
- 卡顿、闪退、UI 与事件顺序：[运行时排错](implementation/runtime-diagnostics.md)。归档聊天复盘：[经验来源与取舍](../docs/agents/retrospective.md)。
- 项目设计定位：[说明](design/README.md)；套件通用能力：[来源](../DesignDocument.md)。
- 项目资料：[路径与归属](../docs/agents/project-data.md)、[问题模板](implementation/bug-reports/latest.md)。
- 全部页面：[catalog.md](catalog.md)。大型参考库 `DataEditorXML/` 与 `wiki/reference/triggers-native/` 按具体 ID 查询。

- 使用语言：[自动选择与个人偏好](guides/agent-language.md)。

- 单位迁移：[数据链分析、来源选择与安全导入](guides/unit-migration.md)。

- 共享工具与 MCP：[接入、能力归属与 DeepSeek](guides/shared-tools.md)、[统一路由技能](../skills/sc2-shared-tools/SKILL.md)。
- Harness2：[项目内安装与本地递归 demo](guides/harness2.md)。
