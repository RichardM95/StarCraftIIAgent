# 开发调查与研究

普通只读查询定向取得证据后直接回答。需要跨次复用的项目结论写入 [项目资料](project-data.md)，通用且带来源与适用范围的发现写入套件参考页。

Catalog 事实先用 tools/sc2-catalog-query.py 查询当前项目与活动依赖，再核对原始 XML。需要官方或合作先例时使用 tools/sc2-reference-query.py 限定组件、类型、语言和数量。参考样例不证明当前有效值。同一任务复用未变化的证据。

项目设计、实现事实分别进入项目 docs/design/ 与 docs/implementation/。临时输出按需保存 runtime/tmp/，测试与日志报告使用 runtime/reports/；不要为一次查询创建持久文档。
