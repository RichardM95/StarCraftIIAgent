# Wiki 任务路由器

当前尚未选择项目。先阅读 [工作区规则](../AGENTS.md)。用户提供主 Components 模组路径后运行 `python tools/init-project.py "<路径>"`。

- 技能：[统一入口](../skills/sc2-project-entry/SKILL.md)，按任务加载专用技能及 Galaxy、SC2 Data 子技能。
- 工具：[工具指南](../tools/README.md)。未初始化时运行 `python tools/test-suite.py --scope tools` 和 `python tools/test-suite.py --scope docs`。
- XML：[模式](implementation/xml-patterns.md)、[Catalog 规则](implementation/xml-patterns/catalog-rules.md)。
- Galaxy：[语法陷阱](implementation/galaxy-gotchas.md)、[语言参考](reference/galaxy-language.md)。
- 本地化：[规则](implementation/localization.md)。
- 触发器：[依赖查询与案例](reference/trigger-knowledge.md)、[游戏对白与对话框](reference/trigger-dialogue-examples.md)、[用户对话示例](reference/trigger-agent-dialogue-examples.md)、[GUI 模板](reference/trigger-templates/README.md)、[XML 概述](reference/triggers-overview.md)、[地图接线](implementation/per-map-setup.md)。
- Bank：[约定](implementation/bank-system.md)、[接口](reference/galaxy-bank.md)。
- 项目初始化：[指南](guides/project-initialization.md)。
- 验收：[反馈流程](implementation/testing-feedback-workflow.md)、[编辑器交接](guides/editor-handoff.md)。
- 项目设计定位：[说明](design/README.md)；套件通用能力：[来源](../DesignDocument.md)。
- 项目资料：[路径与归属](../docs/agents/project-data.md)、[问题模板](implementation/bug-reports/latest.md)。
- 全部页面：[catalog.md](catalog.md)。大型参考库 `DataEditorXML/` 与 `wiki/reference/triggers-native/` 按具体 ID 查询。
