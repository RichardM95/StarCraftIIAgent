# AGENTS.md — 入口文件

**作者：扯蛋虾米。** 统一作者声明见 `AUTHORS.md`。

**本文件是工作区规则入口。** 需要项目路径时读取 `agent-config.json`；需要领域文档时从 `wiki/index.md` 路由；仅在路由器未覆盖时打开 `wiki/catalog.md`。`README.md` 是面向人类的概述，`wiki/reference/editor-guide.md` 是 SC2 Editor 工作流笔记。

> **项目初始化规则：** 当用户给出主 `.SC2Mod` Components 文件夹路径并要求初始化或选择项目时，直接运行 `python tools/init-project.py "<主Mod文件夹路径>"`。该工具负责推导 SC2/Mods/Maps 路径、递归解析依赖并写入 `agent-config.json`；不要要求用户手工编辑 JSON。仅当目录不是标准 `<StarCraft II>/Mods/<Name>.SC2Mod` 布局且无法推导时，才询问缺失路径。初始化后检查“模组身份”是否与所选项目相符，不要猜测 Bank、Library ID 或代码前缀。

> **编辑规则：** 初始化后遵循 `agent-config.json` 的 `project.source_mode`。`in_place` 直接编辑配置的主模组；`workspace_copy` 编辑 `project.source_mod` 指定的副本（相对工作区或绝对路径，缺失时停止写入）并通过 `tools/deploy-mod.py` 部署。绝不编辑 `publish/`。
>
> **Galaxy 编辑规则：** 从当前项目的 Triggers 核对手写源码入口和 include 顺序，仅修改手写源码；绝不直接编辑 `Lib*.galaxy`、`MapScript.galaxy` 或其他编译输出。
>

> **维护规则：** 当设计决策、TODO 或阶段变更改变当前契约时，更新相关 wiki 页面。仅在原因可能丢失时才向 `wiki/log.md` 添加记录。主题页面描述当前状态；替换被取代的指导，而非追加带日期的修复叙述。
>
> **日志规则：** 记录决策和原因，而非实现摘要。链接到规范页面；不要添加冗余的文件列表、验证输出、问题详情或 commit hash。使用 Git 历史查看先前状态。
>
> **问题工作流规则：** 每个问题遵循 `reported` → `root cause confirmed` → `source fixed` → `static validation passed` → `Editor accepted` → `packaged runtime passed`。编辑前要求有效值证据：对于统计数据，记录本地单位、父对象、继承值和目标覆盖值；对于 UI 文本，识别文本类型是世界悬停、选择面板、命令卡按钮、tooltip 还是编辑器文本。交付结论必须使用上述精确状态：静态工具全绿只能报告 `static validation passed`；没有编辑器重载/保存证据时不得写 `Editor accepted`，没有游戏内复现步骤与结果时不得写 `packaged runtime passed`。
>
> **研究规则：** 需要帮助或澄清时向用户索取更多信息。若反复搜索未能缩小问题范围，停止并向用户总结当前发现。
>
> **设计摄入规则：** 当用户提供设计文档（Word、PDF、Markdown、聊天大纲）时，将持久事实提取到 `wiki/design/` 并在 `DesignDocument.md` 中摘要来源。不要将一次性设计细节仅留在聊天历史中。

## 仓库用途

用于 **StarCraft II 自定义战役**开发的起始工作区，配合 AI 辅助（CCM 社区）。包含 WoL/HotS/LotV `DataEditorXML/` grep 导出、正式 XSD schema、快速静态 linter、token 高效的 catalog 查询工具、Galaxy/XML 陷阱，以及结构化的 wiki 布局用于设计、实现和参考。

## 智能体技能与指导

### 技能库
统一技能库位于 `skills/`，采用 router + sub-skill 布局。SC2 模组/地图实现任务加载 `skills/sc2-project-entry/SKILL.md`，再按主题加载对应技能；普通文档或工具维护任务只读取相关规则与文件。布局概览见 `wiki/index.md#skills-unified`。

工作区内的 `AGENTS.md`、`agent-config.json`、本地 `skills/` 与工具 `--help`/源码是当前契约。所有规则、工具和样例均从本工作区定位；全局技能只负责入口定位。

### 问题追踪
问题记录在提交的 Markdown 账本中，而非 GitHub Issues。见 `docs/agents/issue-tracker.md`。

### 领域文档
`wiki/` 树是战役的领域文档；从 `wiki/index.md` 路由。见 `docs/agents/domain.md`。

### 战役研究
将可复用的 SC2 发现捕获到相关 `wiki/` 页面，附来源和范围。先使用 `tools/sc2-catalog-query.py` 查询当前项目、依赖和已有 TXT 导出；需要具体官方或合作案例时，用 `tools/sc2-reference-query.py` 限定组件、catalog 类型和结果数量，再打开命中的 XML 片段。见 `docs/agents/research.md`。

## 项目状态

当前尚未选择项目，工作区没有活动的 `agent-config.json`。用户提供主 Components `.SC2Mod` 路径后，运行 `python tools/init-project.py "<路径>"`，再从配置和 Triggers 核对项目身份、源码入口和依赖。Bank、Library ID、函数前缀均以新项目证据为准。

## 关键文件位置

| 路径 | 用途 |
|---|---|
| `AUTHORS.md` | 智能体统一作者声明（扯蛋虾米） |
| `agent-config.json` | 可移植路径配置：工作区、SC2 安装、Mods、战役地图、主模组与递归依赖解析 |
| `wiki/index.md` | **任务路由器** — 最快到达相关文档的路径 |
| `wiki/catalog.md` | 完整 wiki 清单；仅在任务路由器不够时使用 |
| `wiki/log.md` | 持久决策的紧凑记录；Git 保留历史 |
| `wiki/design/` | 我们在建什么（用户 + 智能体） |
| `wiki/implementation/` | 怎么建（XML 模式、本地化、陷阱、状态） |
| `wiki/reference/` | 查找表、Actor 架构、SC2 参考 |
| `wiki/guides/` | 逐步指南（编辑器交接、多 PC 设置、模拟 bank 测试） |
| `skills/` | **统一技能库**（项目路由、翻译与 galaxy/sc2data 子技能，按需加载） |
| `skills/sc2-project-entry/SKILL.md` | 统一入口技能 — 模组身份、硬性规则、任务路由、工具速查 |
| `skills/galaxy/` | 13 个 Galaxy 子技能（深度 API 参考，在 `sc2-galaxy-scripting` 之后加载） |
| `skills/sc2data/` | 6 个 SC2 Data 子技能（深度 XML schema 参考，在 `sc2-catalog-xml` 之后加载） |
| `tools/` | 预飞行测试套件（`test-suite.py`）、静态校验器（`validate-mod.py`）、catalog 查询工具（`sc2-catalog-query.py`） |
| `tools/schemas/sc2-xsd/` | 用于 Catalog、GameData、SC2Layout 校验的 W3C XSD schema |
| `DataEditorXML/` | XML 导出 — 写 XML 前 grep 或查询 |
| `<configured mods_dir>/<Dep>.SC2Mod/` | 从主 Mod 递归解析得到的依赖模组组件文件夹 |
| `<SC2_INSTALL>/Maps/Campaign/` | 战役地图组件文件夹（如 `void/paiur01.SC2Map`） |
| `DesignDocument.md` | 原始设计来源 / 摘要 |
| `publish/` | 仅用于发布打包 — 不要编辑 |

## DataEditorXML 范围

预包含的导出覆盖 **Wings of Liberty**、**Heart of the Swarm** 和 **Legacy of the Void** 战役/模组层。若战役使用不同基础（Nova、Co-op、自定义扩展），向用户索取该特定导出并更新 `wiki/reference/data-editor-xml.md`。

## 工具故障恢复

若 patch helper 或工具报告 `os error 206` 或字符串替换错误，遵循 `wiki/implementation/agent-context-efficiency.md` 中的恢复指南。使用精确文本替换、保留编码/换行、按受影响范围运行 `python tools/test-suite.py --scope tools|docs|mod` 或对应回归。

## 关键规则（任何代码变更前必须知道）

### 新触发器优先使用 GUI
生成或改造触发器时，先用触发器编辑器可编辑的事件、条件、动作和 GUI 自定义定义实现。仅当 GUI 无法合理表达局部逻辑时，才在该触发器中嵌入最小必要的自定义代码；不要因此默认新建独立 Galaxy 脚本。只有用户明确要求使用 Galaxy，或任务本身是维护既有 Galaxy 源码时，才走独立脚本实现。无论采用哪种方式，均不得手改编辑器生成的 `MapScript.galaxy` 或 `Lib*.galaxy`。

### 地图调用必须使用 GUI action，而非 Custom Script
SC2 链接器会在地图未调用 GUI action 时静默丢弃模组库。在模组中定义这些 action。

### Catalog 和 XML 编写
- 写 XML 前运行 `python tools/sc2-catalog-query.py`；需要字段形状或案例时精确查询 `DataEditorXML/*.txt` 或 `python tools/sc2-reference-query.py`。字段名和 ID 区分大小写。组件样例不代表活动依赖。
- 模组源变更验证实际目标组件；工具与文档改动使用对应 scope 或具体回归，跨模块调整按主入口执行综合验收。
- Editor 保存通过后，运行 `python tools/audit-gamestrings-anchors.py --locale zhCN --fill` 恢复当前模组缺失的玩家面向字符串锚点；其他项目传其实际语言。

### SC2 Modding XML 规则
- XML 注释和属性值只用 ASCII 字符
- `AbilAutoCmd` 按钮类型在 SC2 的 XML schema 中无效 — 不要添加
- `CBehaviorBuff` 不支持 `InitEffect` — 不要提出使用它的架构
- 纯注释 catalog 会被 SC2 解析器拒绝 — 每个 catalog 必须有实际条目
- 编辑前检查依赖链中是否已存在 validator/entity，避免重复

### Galaxy Script 规则
- 局部变量必须提升到函数体最顶部，在任何可执行语句之前
- 后缀自增/自减运算符（`++`、`--`）和复合赋值循环（`for (...)`) 在 SC2 Custom Script 中不受支持 — 使用 `i += 1;` 和 `while (...)`
- Include 指令必须使用无扩展名的相对路径（如 `include "Scripts/MyScript"`）
- 地图内的 `MapScript.galaxy` 编辑是自动生成且保存时会被覆盖 — 在模组脚本块或 `Base.SC2Data/Scripts/` 中编写逻辑

## 需要 SC2 Editor GUI 的操作（智能体无法完成）

- 打开和保存 Blizzard 地图（需要 SC2 账号登录）
- 地形、区域、doodads、寻路
- 过场动画和 cinematics
- 将模组/地图保存为 Components（用户操作 — 见 `setup.md`）

## SC2 Editor 注意事项

- **绝不**在项目模组作为外部 override 激活时打开地图 — 会加载模组版本而非原版
- **添加依赖：** Map → Modules → Dependencies → `<ModName>.SC2Mod`

## 独立工作区与按需执行

本目录是独立的 StarCraftIIAgent 开发工作区，Git、忽略规则、工具、技能与开发资料由本目录维护。用户相对输入以本工作区为基准；开发项目由 agent-config.json 定位，project.source_mod 的相对路径也以本工作区为基准。

| 请求 | 执行与验证 |
|---|---|
| 查询、解释、只读调查 | 定向读取必要证据并直接回答，无需维护验收 |
| 文档或局部工具修改 | 检查相关链接、技能入口或具体回归；使用 --scope docs 或 tools |
| 模组/地图修改 | 核对有效值后编辑实际源，验证受影响组件；使用 --scope mod 和明确目标 |
| 共享工具调整或完整测试 | 运行工具、文档及实际目标所需检查；无活动项目时分别执行 tools 与 docs |
| 部署、恢复 | 用户请求或已授权任务确实需要时执行，保留路径保护与恢复能力 |

同一任务复用未变化的规则和证据；源文件、配置或实现变化后复核相关部分，保留索引新鲜度与发布前检查。相同输入与实现下已通过的检查不重复运行，专项交付说明验证范围。信息足够时直接执行，复杂且存在实质选择的任务再形成计划。

本工作区专注模组与地图开发，不提供整项目汉化、翻译知识库、自动 UI 文本提取或百科生成。开发所需 GameStrings/ObjectStrings 键维护、字符串锚点与编码检查仍由 sc2-localization 技能和本地工具负责。
