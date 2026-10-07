# 问题追踪

需要跨次跟踪的问题保存到活动项目资料 docs/issues.md；用 `python tools/project-paths.py` 定位，模板见 [问题模板](../../wiki/implementation/bug-reports/latest.md)。简单修改直接完成，不强制建账。

生命周期仍为 reported → root cause confirmed → source fixed → static validation passed → Editor accepted → packaged runtime passed。按阶段保存必要复现、原因、修改和验证证据；静态结果不能替代编辑器与游戏门槛。

修改数值前核对本地、父对象、依赖与目标覆盖；UI 文字先识别生效表面及键。长期机制约定更新项目主题，不将账本变成历史流水账。

游戏日志在用户要求或明确授权时提取，默认报告在项目 runtime/reports/bugreport.txt。无活动项目时提供显式 --output；原始游戏日志只读。账本审计默认跳过尚未建立的账本，显式 --ledger 必须存在且合法。
