# SC2 编辑器指南与组件安全矩阵

本页说明编辑器的一般注意事项、组件目录结构，以及 AI 智能体和开发者的文件访问边界。

---

## 组件目录结构与智能体访问安全

将 `.SC2Map` 和 `.SC2Mod` 解包为 Components 目录后，Git 和编码智能体就能访问原始脚本与 XML。不过，SC2 编辑器同时也是编译器和代码生成器，保存时会自动覆盖部分文件。智能体和开发者必须严格遵守以下访问边界：

| 组件目标 | 文件路径模式 | 主要用途 | 智能体访问级别 | 覆盖风险与引擎处理 |
|---|---|---|---|---|
| **地图脚本引导文件** | `MapScript.galaxy` | 自动生成的初始化与触发器包装器 | **只读** | **严重**：SC2 编辑器每次保存都会重建，手工修改会丢失 |
| **库包装器** | `Lib[HASH].galaxy` | 编辑器生成的模块实现包装器 | **只读** | **高**：在 GUI 中修改库触发器时会被覆盖 |
| **库头文件** | `Lib[HASH]_h.galaxy` | 编辑器生成的头声明 | **只读** | **高**：库编译时会被覆盖 |
| **组件清单** | `ComponentList.SC2Components` 或编辑器管理的组件清单 | 地图/模组包含的组件列表 | **只读** | **高**：由 SC2 编辑器在保存时管理和更新 |
| **地图放置对象** | `Objects` | 包含编辑器放置对象的 `PlacedObjects` XML | **只读（可检查）** | **高**：用于区分预放置内容和触发器创建内容；应在 SC2 编辑器中修改 |
| **自定义脚本块** | 主模组 `Base.SC2Data/Epi_Main.galaxy` 或项目规定的 `*_ScriptBlock.galaxy` | 模组触发器脚本块的手写源码 | **读写** | **低**：以项目 `AGENTS.md` 规定的源真值为准；编辑器交接时核对同步结果 |
| **自定义脚本目录** | `Base.SC2Data/Scripts/*.galaxy` | 用户编写的辅助 Galaxy 逻辑 | **读写** | **低**：通过自定义 include 引用时可跨保存保留 |
| **GameData Catalog** | `Base.SC2Data/GameData/*.xml` | Unit、Ability、Actor、Behavior 等 XML catalog | **读写** | **低**：允许修改，但必须保持合法 XML 节点层级 |
| **UI Layout 定义** | `Base.SC2Data/UI/Layout/*.SC2Layout` | 自定义界面与 frame 声明 | **读写** | **低**：由引擎直接解析，不经过触发器编译 |
| **本地化数据** | `enUS.SC2Data/LocalizedData/*.txt` 等语言目录 | `GameStrings.txt`、`ObjectStrings.txt` | **读写** | **低**：允许修改；编辑器会规范化未引用字符串 |

> 实际脚本源真值由当前项目的 `AGENTS.md` 决定。不要根据旧模板假定仓库根目录一定存在 `*_ScriptBlock.galaxy`。

---

## 安全打开 Blizzard 地图

- 打开 Blizzard 战役地图前，**禁用外部模组 override**，否则编辑器可能打开已经被模组覆盖的版本。
- 将 Blizzard 地图保存为 **Components**，放入配置的 `paths.campaign_maps_dir`，并保留原始战役分类目录名。
- 地图保存到本地后，再添加 `<ModName>.SC2Mod` 依赖。
- 在 `wiki/implementation/per-map-setup.md` 中记录每张地图的触发器接线方式。

---

## 验证流程

- 将 SC2 编辑器中的 XML 警告视为真实错误处理。
- 运行 `python tools/test-suite.py` 执行静态预检。
- 手写 XML 前，使用 `tools/sc2-catalog-query.py` 查询，或在 `DataEditorXML/` 中搜索字段名和现有 ID。
- 修改单位后，检查所有相关变体，例如潜地形态、变形单位和兵种升级。
- 编辑器保存通过后，运行 `python tools/audit-gamestrings-anchors.py --fill`，确保文本锚点仍然存在。
- 静态通过后仍需记录编辑器打开/保存结果和最小游戏场景测试；两者不能互相替代。

---

## 打包

- `publish/` 是由用户管理的打包和发布输出目录。
- 不要把 `publish/` 当作实现源码；应从工作模组和地图重新生成发布副本。
