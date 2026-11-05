# StarCraftIIAgent — 星际Ⅱ模组开发智能体

[English](README.en.md)

用于星际争霸Ⅱ自定义战役开发的本地工作区，提供开发规则、知识库、查询与校验工具，以及按任务加载的根技能、Galaxy 与 SC2Data 子技能。当前技能入口见下方[任务路由](#任务路由)。

作者：**扯蛋虾米**。统一声明见 [AUTHORS.md](AUTHORS.md)。

[安装指南](setup.md) · [工作区规则](AGENTS.md) · [Wiki](wiki/index.md) · [工具指南](tools/README.md) · [完整开发示例](wiki/guides/development-conversations.md)

<a id="常见场景示例"></a>

## 从你的第一项任务开始

| 可以直接发送的请求 | 第一次回复应给你什么 |
|---|---|
| “查一个官方战役里只完成一次任务目标的例子。” | 来源组件、触发器和生效条件。只读研究无需初始化项目。 |
| “检查 `<地图.SC2Map>` 里的撤离区触发器，先预览怎样改成只有玩家 1 能完成一次。” | 实际检查的 Components 地图路径、区域和现有条件，再展示拟修改的行为。 |
| “我的主 Mod 在 `<主模组.SC2Mod>`，请初始化项目。” | 解析出的主项目、实际编辑源和活动依赖。 |
| “查询当前项目中陆战队员的生命、武器和生产条件，这次不修改。” | 对应单位 ID、当前有效值及来源；重名时先确认对象。 |
| “把当前项目中陆战队员的基础生命改成120，保留已有升级效果，先不部署。” | 修改前后基础值、实际源位置和相关静态检查结果。 |
| “给追猎者新增一个冷却10秒的暗影闪现，保留原技能。” | 能力、按钮、命令卡和文字的接线结果，以及编辑器与游戏验证步骤。 |

在能够读取本地工作区并执行工具的 AI 助手中打开本目录，将路径替换成实际 Components 目录。通常直接描述目标即可，已知信息由智能体查询；不需要记住技能名称或工具参数。[完整36个开发场景](wiki/guides/development-conversations.md) · [已保存地图的多轮协作](wiki/guides/development-conversations.md#saved-map-examples) · [游戏内对白制作案例](wiki/reference/trigger-dialogue-examples.md)

第一次提需求时，说明目标、期望结果和本轮范围即可，例如：

```text
目标是 <地图或模组的Components路径>。
我想让玩家1首次进入撤离区时完成任务，重复进入不再触发。
先只读检查现有逻辑，再给出修改预览，不应用到目标源。
```

| 你可以怎么说 | 智能体应怎样处理 |
|---|---|
| “这次只读调查。” | 查询现有内容和来源，不修改目标地图或模组源码。 |
| “先给我预览，不应用。” | 展示拟修改的行为、差异和影响；工具可能生成隔离副本、候选或报告。 |
| “按这个方案修改，暂不部署。” | 修改已明确的开发源，运行相关检查并报告实际结果；修改与部署可以分别指定。 |

## 按任务准备环境

基础工具推荐 Windows 和 Python 3.12。使用共享 CLI/MCP 时安装独立的 Python 3.12+ 环境。离线 Galaxy 编译还需要 Node 22+ 和已安装的前端。编辑器与游戏验收需要本机 SC2，正式 XML schema 校验需要 lxml 或 xmllint。[安装指南](setup.md) · [完整集成回归与 Windows UAC 补验](wiki/guides/shared-tools.md)

## 快速开始

1. **加载规则。** 在助手中打开本工作区，发送“先读取 AGENTS.md 和 skills/sc2-project-entry/SKILL.md，再处理我的任务”。宿主未自动发现技能时，也可直接读取这些文件。
2. **检查安装。** 在工作区根目录运行下列检查，或让助手执行；两项都不需要选择项目。

   ```powershell
   python tools/test-suite.py --ui-language zh-CN --scope docs
   python tools/test-suite.py --ui-language zh-CN --scope tools
   ```

3. **提供目标。** 修改模组前，发送“我的主 Mod Components 文件夹是 `<实际路径>`，请完成项目初始化”，再提出具体任务。只研究官方案例或检查一张地图时，可以直接给出目标，无需切换主项目。

初始化会运行 `tools/init-project.py`，递归检查依赖并生成本机 `agent-config.json`，无需手工编辑 JSON。新克隆没有此文件是正常情况。Components 是编辑器保存出的组件文件夹；只有 `.SC2Mod` / `.SC2Map` 归档文件时，先按[初始化指南](wiki/guides/project-initialization.md)和[归档指南](tools/README.md#打包组件与格式转换)确认读取或转换方式。

## 功能概览

| 任务 | 能做什么 | 需要提供什么 | 编辑器与游戏验证 |
|---|---|---|---|
| 单位、技能与科技 | 查询有效值和数据链，修改属性，制作技能、升级与单位变体 | 项目路径、对象 ID、期望行为；已有信息由智能体查询 | 修改后检查编辑器加载及游戏行为 |
| Actor、模型与音效 | 排查表现链，查询官方素材，替换外观或接入特效 | 对象、目标外观或异常现象 | 需要观察动画、附着点、声音和实际画面 |
| GUI 触发器与攻击波 | 制作目标、计时器、胜败和对白，缩放或迁移攻击波 | 明确地图、玩家、条件及目标对象 | 需要编辑器保存与游戏事件验证 |
| Bank 与战役存档 | 设计战役存档、兼容旧档，接入任务结算与解锁 | 存档需求、已有 Bank 与结算入口；已有信息由智能体查询 | 需要新旧档加载、保存及进度验证 |
| 手写 Galaxy 与离线检查 | 维护已确认的手写源码，使用已安装前端进行离线编译诊断 | 源码入口、目标组件与实际依赖；离线编译另需 Node 22+ 和前端 | 离线编译结果不能替代编辑器接受和游戏运行 |
| 官方案例与数据研究 | 查询官方数据、触发器案例及资源引用链 | 对象 ID、机制描述或组件范围 | 参考命中后仍需核对目标项目实际加载的依赖 |
| 开发文字 | 维护玩家文字键、语言文件与缺失字符串锚点 | 对象、文字显示位置、目标数据语言 | 需要核对游戏显示；不提供整项目汉化服务 |
| 地形与场景 | 调查地图，按当前支持范围制作独立副本、摆放物件和调整地形 | 有效地图基底、输出路径、布局与保留约束 | 按具体操作查询能力；视觉、通行与保存重开分别验证 |
| 单位迁移与层合并 | 分析来源、数据链、冲突和资源，按明确方案导入 | 来源、目标、单位列表或层优先级 | 导入后验证生产、技能与表现；层合并不等于完整迁移 |
| 图标制作与检查 | 按身份、玩法和派系参考制作或重绘图标，检查小尺寸辨识度及指定 DDS 格式 | 原图或用途、目标尺寸与压缩格式、视觉参考；格式检查需要 Pillow | 候选压缩后回读，替换后检查实际界面显示 |
| 肉鸽机制 | 设计和排查天赋、抽取、商店、奖励、叠层与跨图恢复 | 项目规则、条目或可复现的异常 | 分别验证领取、满层、重复操作及存档恢复 |
| 天赋清单导出 | 探测 UserData 与静态 GUI 注册，按项目映射导出双语 Excel，解析说明基础数值 | 模组路径、字段与品质映射；Excel 导出需要 openpyxl | 回读工作簿并报告缺失、歧义和未解析项；运行时加成另验 |
| 检查、部署与项目资料 | 静态校验、日志排错、部署预览及授权部署，维护设计与问题账本 | 明确目标、检查范围或复现材料 | 静态检查不能替代编辑器和打包运行验收 |

基础工作流使用本地规则、技能和 Python 工具。共享 CLI/MCP、模型分包及 Harness2 是可选扩展，分别需要本机环境和连接配置；未安装时仍可使用不依赖它们的功能。

数据查询会说明本地覆盖、继承和依赖来源；静态解析无法确定的合并规则或缺失依赖会单独列出。升级、行为和触发器还可能在运行时改变数值，游戏内最终表现需要实际验证。预览图用于检查布局和数据，实际画面与寻路以编辑器和游戏观察为准。

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
| 图标制作与小图审查 | [sc2-icon-art](skills/sc2-icon-art/SKILL.md) |
| 肉鸽机制与恢复审计 | [sc2-roguelike-mechanics](skills/sc2-roguelike-mechanics/SKILL.md) |
| 双语天赋 Excel 导出 | [sc2-roguelike-talent-export](skills/sc2-roguelike-talent-export/SKILL.md) |

### 文件结构与项目资料

```text
StarCraftIIAgent/
├── README.md / README.en.md    使用说明
├── AGENTS.md / AGENT.md        工作区规则 / 身份说明
├── AUTHORS.md                 作者声明
├── setup.md / setup.en.md      安装与配置指南
├── agent-config.json          初始化后生成，本机使用，不分发
├── skills/                    按任务加载的根技能与子技能
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

按修改范围选择检查，命令均从工作区根目录运行：

| 检查范围 | 命令 | 前提 |
|---|---|---|
| 使用说明与技能文档 | `python tools/test-suite.py --ui-language zh-CN --scope docs` | 不要求活动项目 |
| 通用工具回归 | `python tools/test-suite.py --ui-language zh-CN --scope tools` | 不要求活动项目 |
| 模组或地图组件 | `python tools/test-suite.py --ui-language zh-CN --scope mod --mod-dir "<Components路径>"` | 有效目标及所需依赖；不传目标时使用当前项目 |
| 共享 SC2 工具集成回归 | `python tools/test-suite.py --ui-language zh-CN --scope integration` | 已安装共享工具独立环境；先退出 SC2 游戏 |

地图和临时外部目标应显式指定，参数以工具 `--help` 为准。Windows 目录符号链接权限不足时，按[集成回归指南](wiki/guides/shared-tools.md)使用可选 UAC 补验，并分别报告普通回归与补验结果。

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
- 初始化提示官方依赖未解析：先检查[CASC 缓存覆盖](wiki/reference/official-casc-cache.md#初始化中的官方依赖未解析)，恢复工具读取证据后再重试；缓存缺项不代表游戏缺少依赖。
- 缺少可选工具：按接入指南重建本机环境；注册成功与客户端实际连接成功分别确认。
- `os error 206` 或字符串替换失败：按[恢复指南](wiki/implementation/agent-context-efficiency.md)缩小操作，保留编码和换行，并运行相关范围检查。
- 运行问题：提供实际地图或模组、复现步骤、编辑器版本、日志及截图；按[运行时排错指南](wiki/implementation/runtime-diagnostics.md)调查。
