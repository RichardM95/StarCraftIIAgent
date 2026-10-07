# 领域文档

本工作区只对应一个战役上下文。长期有效的术语、设计决策和实现契约存放在 `wiki/`，不放在 `CONTEXT.md` 或 `docs/adr/`。

## 开始查找前

1. 首先阅读 `AGENTS.md`，了解仓库级约束。
2. 使用 `wiki/index.md` 作为**任务路由器**，前往相关页面。仅当路由器不足时才打开 `wiki/catalog.md`。
3. 战役设计查阅 `wiki/design/` 下的相关页面；实现行为查阅 `wiki/implementation/` 下的对应页面；经过验证的 SC2 与编辑器事实放在 `wiki/reference/`。

## 文档规则

- 将主题页面和系统页面视为当前契约。新指导取代旧指导时，应替换过时内容，而不是追加修复历史。
- 用户提供设计文档或大纲时，将长期有效的事实提取到 `wiki/design/`，并在 `DesignDocument.md` 中摘要来源。
- 当设计决策、TODO 或阶段变化改变当前契约时，更新相关 wiki 页面。不要把 `wiki/log.md` 当作变更日志。
- 保留“开场地图”“`Editor accepted`”和“`packaged runtime passed`”等项目术语。依赖不熟悉的术语前，应先在相关 wiki 页面中给出定义。
