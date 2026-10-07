# 问题追踪

本工作区使用已提交的 Markdown 账本处理日常问题，而不是 GitHub Issues。除非用户明确要求，否则不要在 GitHub 上创建或镜像常规战役问题。

## 规范位置

- 活动问题状态与测试人员交接：`wiki/implementation/bug-reports/latest.md`
- 当前优先级与阻塞项：`wiki/implementation/current-work.md`
- 问题摄入、修复计划与保留证据：`wiki/implementation/bug-reports/`
- 生命周期与证据规则：`wiki/implementation/testing-feedback-workflow.md`

## 工作流

在活动账本中记录报告及其复现上下文：地图/运行环境、玩家选择、创建路径、实际结果和相关 Bank 状态。问题只能按以下顺序推进：

`reported` → `root cause confirmed` → `source fixed` → `static validation passed` → `Editor accepted` → `packaged runtime passed`。

修改数值前，记录本地 catalog 条目、父对象、继承值和目标覆盖值。修改 UI 文本前，识别准确的 UI 表面及实际生效的本地化锚点。静态证据不能替代编辑器或发布包运行门槛。

保持活动账本简洁。将长期有效的实现事实移动到相关系统页或参考页；仅当某项决策的理由可能丢失时才使用 `wiki/log.md`。

## 本地日志错误报告提取器

用户或智能体可以在手动游戏测试后，通过 `tools/extract-playtest-bugreport.py` 生成 `bugreport.txt`。当用户要求分析日志或授权检查本地《星际争霸 II》游戏测试日志时，智能体可以运行该工具。将生成的报告视为输入证据，保留无关的本地日志；不要把提取出的运行时证据误当作 `Editor accepted` 或 `packaged runtime passed` 生命周期门槛。
