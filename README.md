# StarCraftIIAgent — 星际Ⅱ模组开发智能体

[English](README.en.md)

用于星际争霸Ⅱ自定义战役开发的本地工作区，提供开发规则、知识库、查询与校验工具，以及34个按需加载的技能（15个根技能、13个 Galaxy 子技能、6个 SC2Data 子技能）。

作者：**扯蛋虾米**。统一声明见 [AUTHORS.md](AUTHORS.md)。

[安装指南](setup.md) · [工作区规则](AGENTS.md) · [Wiki](wiki/index.md) · [工具指南](tools/README.md) · [完整开发示例](wiki/guides/development-conversations.md)

## 简介

在能够读取本地工作区并执行工具的 AI 助手中打开本目录，用自然语言描述要调查、修改或制作的内容。智能体会按任务读取规则与技能，核对当前项目及依赖，再操作实际开发源。

知识库包含 WoL/HotS/LotV 的 DataEditorXML 导出、W3C XSD schema，以及 Catalog、Actor、GUI 触发器、Galaxy 和 Bank 参考。参考资料用于查询；当前项目实际加载的数据以配置和组件证据为准。

## 功能概览

| 任务 | 能做什么 | 需要提供什么 | 编辑器与游戏验证 |
|---|---|---|---|
| 单位、技能与科技 | 查询有效值和数据链，修改属性，制作技能、升级与单位变体 | 项目路径、对象 ID、期望行为；已有信息由智能体查询 | 修改后检查编辑器加载及游戏行为 |
| Actor、模型与音效 | 排查表现链，查询官方素材，替换外观或接入特效 | 对象、目标外观或异常现象 | 需要观察动画、附着点、声音和实际画面 |
| GUI 触发器与攻击波 | 制作目标、计时器、胜败和对白，缩放或迁移攻击波 | 明确地图、玩家、条件及目标对象 | 需要编辑器保存与游戏事件验证 |
| Bank 与现有 Galaxy | 设计战役存档、兼容旧档，维护已确认的手写脚本 | 存档需求或实际脚本入口 | 需要加载、保存及相关运行场景验证 |
| 开发文字 | 维护玩家文字键、语言文件与缺失字符串锚点 | 对象、文字显示位置、目标数据语言 | 需要核对游戏显示；不提供整项目汉化服务 |
| 地形与场景 | 调查地图，按当前支持范围制作独立副本、摆放物件和调整地形 | 有效地图基底、输出路径、布局与保留约束 | 按具体操作查询能力；视觉、通行与保存重开分别验证 |
| 单位迁移与层合并 | 分析来源、数据链、冲突和资源，按明确方案导入 | 来源、目标、单位列表或层优先级 | 导入后验证生产、技能与表现；层合并不等于完整迁移 |
| 检查、部署与项目资料 | 静态校验、日志排错、部署预览及授权部署，维护设计与问题账本 | 明确目标、检查范围或复现材料 | 静态检查不能替代编辑器和打包运行验收 |

基础工作流使用本地规则、技能和 Python 工具。共享 CLI/MCP、模型分包及 Harness2 是可选扩展，分别需要本机环境和连接配置；未安装时仍可使用不依赖它们的功能。

## 环境要求

- Windows，建议 Windows x64 Python 3.12；共享工具要求 Python 3.12+。
- 能够读取本地工作区并执行工具的 AI 助手。
- 已安装 StarCraft II；编辑器保存、视觉检查和游戏验证需要对应环境可用。
- 正式 XML schema 校验需要 `lxml`（`python -m pip install lxml`）或可执行的 `xmllint`；缺少后端时不能报告正式校验通过。
- 可选 Harness2 需要 Linux/WSL、Python 3.12/3.13 和自己的 Codex 登录；模型分包另需本机 Harness 与已保存的 provider/model 配置。

## 快速开始

### 1. 打开工作区

在 AI 助手中打开本目录，发送：

```text
先读取 AGENTS.md 和 skills/sc2-project-entry/SKILL.md，再按我的任务加载对应技能。
```

无需将整套技能重复安装到全局目录。若宿主不能自动发现技能，明确要求读取上述文件即可。

### 2. 检查环境

在工作区根目录运行，或让智能体执行：

```powershell
python tools/test-suite.py --ui-language zh-CN --scope docs
python tools/test-suite.py --ui-language zh-CN --scope tools
```

这两项不要求选择项目。缺失环境的安装方法见 [setup.md](setup.md)。

### 3. 初始化项目

提供主 Mod 的 Components 文件夹路径，例如：

```text
我的主 Mod 文件夹是 E:\Program Files (x86)\StarCraft II\Mods\MyCampaign.SC2Mod，请完成项目初始化。
```

智能体会运行 `python tools/init-project.py "<主Mod路径>"`，推导路径、递归检查本地依赖并验证项目身份。只有归档或尚未保存组件时，先按[初始化指南](wiki/guides/project-initialization.md)准备有效输入。

`agent-config.json` 由初始化工具生成，保存本机项目路径，不随 Git 分发，无需手工编辑。新克隆没有此文件是正常情况；不要复制其他机器的活动项目配置。

### 4. 提出任务

说明目标和期望结果即可。单位名称有歧义或目标不明确时，智能体应先查询并澄清；配置与源码中已有的信息无需重复提供。

## 常见场景示例

以下六类请求可直接发送；路径和对象名称替换为自己的项目内容。

| 需求 | 简短请求 | 预期交付 |
|---|---|---|
| 初始化项目 | 我的主 Mod 文件夹是 `<Components路径>`，请完成初始化。 | 路径、递归依赖、实际编辑源与项目身份核对结果 |
| 查询单位 | 帮我看看当前项目中陆战队员的生命、武器和生产条件，这次只查询。 | 对应对象、有效值、本地覆盖和依赖来源 |
| 修改属性 | 把当前项目中陆战队员的基础生命改成120，其他属性保持原样，先不用部署。 | 修改前后基础值、实际源修改和相关静态检查 |
| 添加技能 | 给追猎者添加一个冷却10秒的“暗影闪现”，保留原技能。 | 独立能力、按钮和命令卡接线、文字及相关检查 |
| GUI 任务目标 | 在 `<地图路径>` 中增加目标“摧毁三座敌方基地”，目标是 `<三个对象>`。 | 可编辑 GUI 目标与计数逻辑、引用检查和游戏验证步骤 |
| 只读检查 | 检查当前项目有什么问题，这次不修改文件。 | 实际目标、检查范围、通过项、失败项与待验项 |

完整需求见[36个开发场景](wiki/guides/development-conversations.md)，跨技能接入见[18个技能场景与两组多轮对话](wiki/guides/skill-conversations.md)，地形专项见[26个制图场景与两组多轮对话](wiki/guides/terrain-conversations.md)。

## 进阶指南

### 任务路由

智能体先读取 [AGENTS.md](AGENTS.md)、当前配置和 [wiki/index.md](wiki/index.md)，再由[项目入口技能](skills/sc2-project-entry/SKILL.md)路由到专用技能。Galaxy 与 SC2Data 子技能由各自根技能继续路由；[AGENT.md](AGENT.md)提供身份与知识架构说明。

| 任务 | 根技能 |
|---|---|
| 项目身份与路由 | `sc2-project-entry` |
| Catalog XML／Actor | `sc2-catalog-xml`／`sc2-actor-system` |
| GUI 触发器／攻击波 | `sc2-map-triggers`／`sc2-attack-wave-scaling` |
| 手写 Galaxy／Bank | `sc2-galaxy-scripting`／`sc2-bank-system` |
| 开发文字与锚点 | `sc2-localization` |
| 校验部署／编辑器交接 | `sc2-tools-validation`／`sc2-editor-handoff` |
| 地形／单位迁移／官方素材 | `sc2-terrain-editing`／`sc2-unit-migration`／`sc2-official-assets` |
| 共享工具／受限模型分包 | `sc2-shared-tools`／`sc2-deepseek-tasks` |

### 文件结构与项目资料

```text
StarCraftIIAgent/
├── README.md / README.en.md    使用说明
├── AGENTS.md / AGENT.md        工作区规则 / 身份说明
├── AUTHORS.md                 作者声明
├── setup.md / setup.en.md      安装与配置指南
├── agent-config.json          初始化后生成，本机使用，不分发
├── skills/                    34个按需加载的技能
├── tools/                     查询、校验、部署及 XSD schema
├── integrations/              可选共享工具与模型集成源码
├── wiki/                      通用开发规则、参考与指南
├── docs/                      套件开发资料
├── DataEditorXML/             官方数据参考导出
├── DesignDocument.md          通用能力来源
└── publish/                   发布产物，不作为编辑源
```

实际主模组、编辑源和地图路径由配置解析。`in_place` 直接编辑所选源；`workspace_copy` 编辑指定副本，按需部署。手写脚本入口及 include 顺序从目标 Triggers 核对。

运行 `python tools/project-paths.py --ui-language zh-CN` 定位项目资料。默认资料目录为主模组旁的 `<模组名>.agent`，初始化可用 `--project-data-dir` 指定；读取和初始化不创建空资料目录。项目设计、机制与跨次问题写入该目录的 `docs/`，来源摘要写入 `docs/sources.md`；索引、报告与临时调查放入 `runtime/`。项目文档可单独版本管理，运行文件默认忽略；套件 wiki 维护通用规则。详见[项目资料说明](docs/agents/project-data.md)。

Git 分发通用规则、技能、源码、测试和参考资料；`projects/`、本机配置、`.runtime/`、环境变量、虚拟环境、报告、凭据与个人模型设置不分发。新机器应重建环境和索引。

### 工具与可选扩展

| 需求 | 入口 |
|---|---|
| 工具、命令卡审计、日志、归档转换与索引 | [工具指南](tools/README.md) |
| 项目初始化、切换与依赖排错 | [安装指南](setup.md)、[初始化指南](wiki/guides/project-initialization.md) |
| 官方数据、触发器与素材参考 | [Wiki 路由](wiki/index.md)、[CASC 缓存](wiki/reference/official-casc-cache.md) |
| 地形操作与单位迁移 | [地形指南](wiki/guides/sc2-terrain-editing.md)、[迁移指南](wiki/guides/unit-migration.md) |
| 共享 CLI/MCP 与模型分包 | [本机安装、配置、诊断和注册](wiki/guides/shared-tools.md) |
| Harness2 实验与技能优化 | [Linux/WSL 安装、基线、复核及恢复](wiki/guides/harness2.md)；实际运行消耗模型额度 |

按修改范围运行检查：`--scope tools` 检查工具，`--scope docs` 检查文档，`--scope mod` 检查目标组件；地图和临时外部目标应显式指定。命令参数以工具 `--help` 为准。

攻击波工具可用 `python skills/sc2-attack-wave-scaling/scripts/wrap_attack_wave_counts.py "<地图路径>/Triggers"` 只读检查，`--apply` 写入，`--check` 检查数量包装；使用前加载对应技能并核对实际 GUI 定义。

编辑器保存后按实际语言运行 `python tools/audit-gamestrings-anchors.py --ui-language zh-CN --locale <实际locale> --fill` 恢复缺失玩家文字锚点；`--fill` 会写入。部署先用 `python tools/deploy-mod.py --ui-language zh-CN --dry-run` 核对方向，按用户授权范围执行复制。

### 中英双语使用

使用层提供中英文页面，技能与深层技术参考保持单一来源，由智能体按所选语言解释。[语言规则](wiki/guides/agent-language.md)支持自动选择、临时 `--ui-language` 和固定偏好。`python tools/agent-language.py --ui-language zh-CN` 只读查看；`--set en`、`--set zh-CN` 或 `--set auto` 显式保存。界面语言不改变 SC2 `--locale`、配置或索引身份。

## 限制与排错

### 硬性规则

[AGENTS.md](AGENTS.md)是规则入口：新触发器优先 GUI；地图通过模组导出的 GUI action 接线。只修改实际开发源，不手改 `MapScript.galaxy`、`Lib*.galaxy` 等生成脚本或 `publish/`。

写 XML 前先运行 catalog 查询核对当前项目、父对象和活动依赖，按需使用参考查询或 DataEditorXML 导出确认字段与案例。XML 注释和属性值只用 ASCII；不使用无效 `AbilAutoCmd` 按钮类型或 `CBehaviorBuff.InitEffect`，catalog 不能只有注释。Galaxy 局部变量放函数体顶部，按保守兼容策略使用 `while` 和显式赋值（`i = i + 1;`），include 使用无扩展名相对路径。详细规则由工作区入口与专用技能维护。

问题按证据推进：`reported` → `root cause confirmed` → `source fixed` → `static validation passed` → `Editor accepted` → `packaged runtime passed`。静态全绿最高只能报告 `static validation passed`；编辑器保存重开和打包游戏复现分别验收。

### 编辑器与能力边界

地形、地图扩建和场景布置先查询当前能力；支持的操作可写入独立 Components 副本。保存、重开、视觉核对、未支持操作的实验及过场制作依赖实际编辑器。GUI 控制已验证可用且获得授权时可由智能体完成，无法执行的必要步骤交给用户。地形实验先保留原始保存差异，再按[交接流程](wiki/guides/editor-handoff.md)处理锚点。

不要在项目模组作为外部 override 激活时打开 Blizzard 地图。添加依赖使用地图 → Modules → Dependencies。打开和保存 Blizzard 地图需要 SC2 账号登录。开发文字维护不包含完整汉化、翻译知识库、自动 UI 文本提取或百科产品。

### 常见问题

- 无法读取规则或技能：确认打开的是本工作区，宿主具备本地文件访问能力，`AGENTS.md`、项目入口技能和 `wiki/index.md` 存在，Python 可执行。
- 未选择项目：提供主 Components 模组路径完成初始化；tools/docs 范围检查和显式目标研究仍可独立进行。
- 缺少可选工具：按接入指南重建本机环境；注册成功与客户端实际连接成功分别确认。
- `os error 206` 或字符串替换失败：按[恢复指南](wiki/implementation/agent-context-efficiency.md)缩小操作，保留编码和换行，并运行相关范围检查。
- 运行问题：提供实际地图或模组、复现步骤、编辑器版本、日志及截图；按[运行时排错指南](wiki/implementation/runtime-diagnostics.md)调查。
