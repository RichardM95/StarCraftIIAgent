# 安装与配置指南——自定义战役智能体起始套件

> **作者：扯蛋虾米。** 项目统一作者声明见 [AUTHORS.md](AUTHORS.md)。

本仓库是一个用于制作《星际争霸 II》自定义战役的**起始工作区**，面向 Cursor、Claude Code、Codex、Antigravity 等 AI 编码智能体，工作流源自 Custom Campaign Manager（CCM）社区的实践经验。

你需要准备：战役构想、任意格式的设计文档、可用的 SC2 编辑器，以及战役地图或模组。  
本套件提供：智能体规则（`AGENTS.md`）、预飞行检查与 schema 校验工具（`tools/`）、节省上下文的 catalog 查询工具、完整的 wiki 知识库（`wiki/`）和 `DataEditorXML/` 参考导出。

> 当前工作区为 **StarCraftIIAgent**，尚未选择活动项目。独立打开本目录后提供主 Components 模组路径；项目身份从当前配置和组件证据核对。

如果只需要完成首次安装或选择一个已有项目，请直接参阅[项目初始化配置](wiki/guides/project-initialization.md)。

---

## ⚡ 快速开始清单

1. 将本模板文件夹**复制或克隆**到项目位置。
2. 如果已有 Components 格式的主模组，运行：
   ```powershell
   python tools/init-project.py "<主模组.SC2Mod 文件夹路径>"
   ```
   工具会自动推导 SC2、Mods 和 Maps 路径，递归解析本地依赖并更新 `agent-config.json`。
3. 从当前配置、Triggers和手写入口核对**模组身份**，确认它与所选项目一致。不要猜测 Bank 名称、Library ID 或代码前缀。
4. 如果是新项目，在 SC2 编辑器中创建模组，并以 **Components** 格式保存到配置的 `paths.mods_dir` 目录。
5. 将准备修改的 Blizzard 战役地图以 **Components** 格式保存到配置的 `paths.campaign_maps_dir` 目录。
6. 选择项目后，将设计材料交给智能体：
   > “先定位当前项目资料目录，把设计中的持久事实写入项目 docs/design/，来源摘要写入 docs/sources.md；套件 wiki 只保存可复用规则。”
7. 构建本地 catalog 查询索引：`python tools/build-sc2-catalog-graph.py`。
8. 提交修改或打开编辑器前运行快速预检：`python tools/test-suite.py`。
9. 开发期间绝不编辑 `publish/`；它只用于最终发布包。

---

## 💬 与智能体对话示例

下面的文字可以直接复制到与智能体的对话中。路径请替换为你电脑上的实际 Components 文件夹。

### 配置已有项目的主 Mod

```text
我的主 Mod Components 文件夹是：
E:\Program Files (x86)\StarCraft II\Mods\MyCampaign.SC2Mod

请完成项目初始化：运行 tools/init-project.py，递归检查本地组件依赖，
更新 agent-config.json；完成后核对 AGENTS.md 中的模组身份，并运行配置验证。
不要让我手工编辑 JSON，也不要根据 Mods 目录内容猜测依赖。
```

智能体应直接调用初始化工具，而不是要求你逐项提供 SC2、Mods、Maps 路径。只有标准布局无法推导时，才应询问缺失目录。

### 只预览配置，不写入文件

```text
主 Mod 路径是：D:\SC2\Mods\MyCampaign.SC2Mod。
请先用 tools/init-project.py --dry-run 预览配置和递归依赖，
不要修改 agent-config.json。把将要写入的路径、主 Mod 和缺失依赖报告给我。
```

### 切换到另一个项目

```text
请把当前智能体切换到这个主 Mod：
D:\StarCraft II\Mods\AnotherCampaign.SC2Mod

运行项目初始化工具更新默认项目，验证递归依赖，
并检查 AGENTS.md 中的 Campaign、Library ID、Compiled Galaxy、Script Block、
Bank 名称和代码前缀是否仍与新项目一致。发现不一致时先报告证据，不要沿用旧项目身份。
```

### 临时检查另一个 Mod，但不切换默认项目

```text
不要修改 agent-config.json。请临时检查：
D:\StarCraft II\Mods\Experimental.SC2Mod

运行 test-suite.py --mod-dir 指向该目录，告诉我实际扫描目标、
通过项、失败项，以及这次检查是否包含它的依赖。
```

### 项目不是标准目录布局

```text
我的目录布局不是标准的 <StarCraft II>/Mods：
- 主 Mod：D:\Projects\MyCampaign.SC2Mod
- Mods 目录：D:\SC2Data\Mods
- SC2 安装目录：C:\Games\StarCraft II
- 战役地图目录：D:\SC2Data\Maps\Campaign

请使用 tools/init-project.py 的显式目录参数完成初始化；
先验证这些目录和递归依赖，只有验证通过后才写入配置。
```

### 还没有 Components 格式的 Mod

```text
我现在只有编辑器里的 Mod，还没有 Components 文件夹。
请告诉我需要在 SC2 编辑器中怎样保存为 Components，
保存后我应该把哪个文件夹路径发给你。暂时不要创建或猜测 agent-config.json。
```

### 首次打开工作区，让智能体确认规则

```text
请先读取这个工作区的AGENTS.md与wiki/index.md，确认本地技能和工具入口。
检查是否已有活动项目；没有则不要猜项目，只说明我还需要提供哪些输入。
本次只读，不修改配置或源文件。
```

预期行为：找到当前工作区契约；安装状态和项目状态分别报告，不把目录中的任意模组自动选为项目。

### 检查安装环境，不选择项目

```text
检查这份StarCraftIIAgent工作区能否使用：Python、规则入口、skills、wiki和tools是否可访问。
只运行适用的工具/文档范围检查，不初始化项目，也不安装额外软件。
列出缺失项和最小修复步骤。
```

预期行为：无项目也能检查套件；实际SC2编辑器打开保存仍由用户操作。

### 查看当前项目与编辑源

```text
请只读检查当前配置，告诉我主模组、实际编辑源、source_mode、Mods、地图和项目资料目录。
核对路径是否存在，区分源码、副本与部署目标；不要切换项目或修复配置。
```

预期行为：配置缺失则明确报告；存在时从配置解析，不假定所有项目都是in_place。

### 从零建立新模组

```text
我还没有主模组，希望基于<自由之翼/虫群之心/虚空之遗或具体依赖>建立战役。
先整理我需要在SC2编辑器中完成的新建、依赖选择与Components保存步骤。
暂不创建项目配置，等我提供真实Components路径后再初始化。
```

预期行为：提供编辑器交接；依赖选择基于用户目标，不因磁盘有库就声称已经加载。

### 修复初始化时的缺失依赖

```text
初始化报告缺失<依赖引用>，完整输出如下：<输出>。
请核对真实依赖声明、组件清单和目录解析，解释具体缺口。
不要用--allow-incomplete掩盖问题或自动添加依赖，修复方案准备好后说明需要的输入。
```

预期行为：定位声明和缺失文件；失败时保留原配置，尚未补齐证据不能确认完整可用性。

### 项目搬家后重新配置

```text
主模组已移动到<新的Components路径>，旧配置指向<旧路径>。
请用初始化工具重新推导新布局并验证依赖，成功后更新配置。
保留旧目录内容和未提交改动，核对是否仍有旧项目身份被沿用。
```

预期行为：重新解析路径；不搬动、删除旧源，也不根据旧索引推断新目标已经可用。

### 跨盘符工作区与SC2

```text
智能体工作区在<盘符A的目录>，主Mod在<盘符B的标准Mods布局>。
请从主Mod路径初始化，检查相对路径和跨盘符绝对路径是否正确。
报告这些配置是否依赖当前机器，不要求我把两者搬到同一盘。
```

预期行为：使用现有路径工具处理跨盘符，不把机器路径写入通用技能或模组源码。

### 指定项目资料目录

```text
主Mod为<Components路径>，项目资料希望保存在<资料目录>。
请使用初始化工具的--project-data-dir设置资料位置并验证配置。
说明docs和runtime的用途；读取或初始化时不要创建无用的空资料目录。
```

预期行为：项目事实与运行输出定位到指定目录，套件wiki保留通用规则。

### 配置副本编辑模式

```text
主Mod位于<Mods中的部署目录>，我希望在<开发副本目录>中编辑。
请核对两者内容与路径，配置workspace_copy及实际source_mod，并验证编辑和部署方向。
保留两边已有内容，暂不部署；副本不存在时先报告，不能回退编辑部署目录。
```

预期行为：实际编辑源必须明确；没有专用入口的配置调整由智能体按当前契约完成，不让用户猜字段或编造命令参数。

### 确认原位编辑模式

```text
我希望直接编辑<主Mod的Components目录>，不建立副本。
请核对当前source_mode和主模组身份，确认实际编辑源，完成配置验证。
不要把publish或已部署副本误当作源码，也不要执行不必要的复制。
```

预期行为：只有确认in_place后才直接使用主组件；与配置不一致时依据真实路径修正并验证。

### 只调查一张地图，不切换主模组

```text
本次只读检查<地图.SC2Map>，Mods为<目录>，Campaigns为<目录>。
列出实际加载的触发器库、依赖路径和缺口，不修改agent-config.json或默认项目。
地图本地函数不能算成主模组本身提供的函数。
```

预期行为：显式目标调查与默认项目配置分开；地图依赖不反向补给被引用模组。

### 提供官方资料构建参考索引

```text
官方解包资料在<SC2GameData Mods目录>与<Campaigns目录>。
请构建外部触发器参考索引，并说明已有定义、精选案例和依赖元数据缺口。
不选择项目，不修改官方源，不把整个资料库复制进工作区。
```

预期行为：允许无项目参考研究；LibraryList不能代替组件依赖证据，参考命中不确认项目可用。

### 初始化项目的Catalog查询索引

```text
当前项目已经初始化，请核对活动依赖后构建Catalog查询索引。
优先生成SQLite查询文件，报告实际输入范围和缺失依赖。
不要为这次查询生成不需要的完整报告，构建失败保留旧索引。
```

预期行为：索引跟随项目运行数据目录；输入不完整不伪造完整状态。

### 初始化后提交设计材料

```text
这是选定项目的设计文档：<内容或附件>。
先定位项目资料目录，将确认需求写入docs/design/，来源摘要写入docs/sources.md。
标明待决定事项；不要把具体项目设计写进套件wiki或覆盖通用DesignDocument.md。
```

预期行为：设计事实进入项目资料，实质设计选择单独确认。

### 让智能体安排第一个可验证任务

```text
项目路径和依赖已确认。我想先做<具体小机制>。
检查现有源后，给出最小可验证实现、所需输入和Editor/游戏验收场景。
本次先规划；不要同时重构其他机制或直接修改项目源。
```

预期行为：计划围绕真实项目；需要地图对象或资源时列出具体缺口，而非宽泛地要求重交全部材料。

### 从规划转入实现

```text
按刚才确认的方案实现<机制>，只修改实际编辑源，保留现有未提交改动。
完成引用、参数、字符串和相关静态检查；暂不部署。
交付实际修改与检查结果，并给我Editor和游戏验证步骤。
```

预期行为：已有授权内直接完成可编辑源工作，静态通过只记录static validation passed。

### 第一次编辑器交接

```text
源码静态检查已经通过。请列出我在SC2编辑器里要打开的实际组件与操作步骤。
说明需要重载/保存检查的GUI、地图对象和生成调用，以及保存后文字锚点检查。
不要提前记录Editor accepted。
```

预期行为：交接对应源版本和实际目标，不让用户打开错误部署副本或在override激活时打开原版地图。

### 提交编辑器保存结果

```text
我已在Editor<版本>打开并重载保存<实际目标>，结果为<现象>。
保存前后文件位于<路径>，编译信息或截图位于<路径>。
请对照结构和生成调用，确认是否可以记录Editor accepted；未通过则定位具体差异。
```

预期行为：依据保存证据推进Editor状态；编辑器接受不代表打包运行通过。

### 提交第一次打包测试结果

```text
测试包使用<源版本和打包方式>，实际步骤是<操作>，结果是<现象>。
日志、截图或录像位于<路径>；正常、跳过、重复触发等覆盖情况为<内容>。
请核对受影响场景，在项目问题账本中更新实际状态，并列出未覆盖项。
```

预期行为：有具体打包场景证据才记录packaged runtime passed，不根据“没看到报错”泛化所有机制通过。

### 多轮对话：先调查，再执行

> **用户：**“这是我的主Components模组：`<路径>`，先预览初始化，不写配置。”
>
> **智能体：**调用dry-run，报告推导路径和实际依赖缺口。
>
> **用户：**“我已经补齐所列缺口，正式初始化，然后查询`<单位ID>`；先不修改单位。”
>
> **智能体：**重新验证后写配置，查询有效值与来源；不把初始化授权扩大成修改单位。
>
> **用户：**“按核对结果把基础生命改为120，完成静态检查，暂不部署。”
>
> **智能体：**修改实际开发源并验证，交付结果和实际验收步骤。

### 多轮对话：静态通过后出现运行问题

> **用户：**“Editor重载保存正常，这是保存前后文件。”
>
> **智能体：**核对结构与生成调用，有证据后记录Editor accepted。
>
> **用户：**“打包后按钮显示了，但点击没有进入分支，日志在`<路径>`。”
>
> **智能体：**调查实际包、事件玩家、控件句柄和分支状态，保留运行失败证据，修复可编辑源。
>
> **用户：**“这是同版本重新打包后正常和重复点击的录像。”
>
> **智能体：**按实际覆盖结果更新状态，未测的超时或多人场景仍单独列出。

更多配置、验证与纠错示例见[项目初始化配置](wiki/guides/project-initialization.md)。 日常数据、技能、触发器、Bank、排错和部署的可复制需求见 [README常见场景](README.md#常见场景示例)。

---

## 📁 仓库结构

| 路径 | 用途 |
|---|---|
| `agent-config.json` | 项目路径、主模组与依赖校验策略；优先使用相对路径，也支持跨盘符绝对路径 |
| `AGENTS.md` | **智能体主入口**——硬性规则、模组身份、命名前缀与工作流 |
| `setup.md` | 本安装与配置指南 |
| `DesignDocument.md` | 套件通用能力来源；具体项目设计保存到项目资料目录 |
| `tools/` | 预飞行测试、XML/Galaxy 静态校验、catalog 图查询与模组部署工具 |
| `tools/schemas/sc2-xsd/` | Catalog、GameData、SC2Layout 等 XML 的 W3C XSD schema |
| `wiki/` | 结构化知识库；`wiki/index.md` 是任务路由器，`wiki/catalog.md` 是完整目录 |
| `wiki/design/` | 项目设计资料的定位说明，不保存具体项目设计 |
| `wiki/implementation/` | 实现细节，如 XML 模式、本地化、Galaxy 陷阱与 Bank 系统 |
| `wiki/reference/` | SC2 引擎与编辑器参考，如 Actor 架构、Galaxy 语言与触发器 XML |
| `wiki/guides/` | 分步指南，如编辑器交接、多电脑配置和模拟 Bank 测试 |
| `wiki/log.md` | 记录架构决策及其原因的决策日志 |
| `<configured editing source>/` | 按 source_mode 确认的实际开发源 |
| `<project data>/docs/` | 项目设计、来源、机制约定与问题记录 |
| `<configured campaign_maps_dir>/` | 从 SC2 编辑器保存的任务 Components 目录（`.SC2Map`） |
| `DataEditorXML/` | 随仓库提供的 WoL、HotS 和 LotV 参考 XML 导出 |
| `publish/` | 仅用于发布包输出；智能体绝不能编辑此目录 |

---

## 第 1 步——选择项目并确认模组身份

### 已有 Components 模组

运行项目初始化工具：

```powershell
python tools/init-project.py "<主模组.SC2Mod 文件夹路径>"
```

初始化完成后，从当前配置、Triggers和手写源码核对模组身份。以下仅示范需要确认的字段，不代表已选择项目：

| 字段 | 示例 | 说明 |
|---|---|---|
| Mod file | `MyCampaignMod` | SC2 `Mods/` 下的文件夹名：`MyCampaignMod.SC2Mod/` |
| Library ID | `<实际 Library Id>` | 从 Triggers/库定义读取，显示名称不等于实际 ID |
| Compiled Galaxy | `Lib91A49292.galaxy` | 触发器编译后在 `Base.SC2Data/` 下生成的文件 |
| Script block name | `"MyCampaign_ScriptBlock"` | 触发器编辑器中的脚本块名称 |
| Bank name | `"MyCampaignBank"` | 必须与 Bank 触发器和 `BankLoad` 调用一致 |
| Galaxy function prefix | `libMy_` | 例如 `libMy_InitCampaign` |
| Galaxy global prefix | `libMy_g_` | 例如 `libMy_g_CurrentMission` |

初始化工具只负责路径和依赖配置；模组身份必须根据库 XML、GUI Action Definition 与现有源码核实。

### 新建模组

新项目应使用独立的模组身份和命名前缀。为所有自定义数据 ID（`CUnit`、`CAbil`、`CBehavior`、`CUpgrade` 等）使用统一前缀，便于查询并减少智能体上下文歧义。

---

## 第 2 步——创建模组并保存为 Components

1. 在 **StarCraft II 编辑器**中新建模组，或打开已有模组。
2. 根据战役基础设置依赖，例如 LotV 可使用 `Void.SC2Campaign` 和 `VoidStory.SC2Campaign`。
3. 新触发器先用 GUI 事件、条件和动作实现；只有 GUI 难以表达的局部逻辑才嵌入少量自定义代码。仅在明确采用独立 Galaxy 脚本时创建脚本块，入口和名称从实际项目核对。
4. 选择 **File → Save As → Components**，将模组保存到 SC2 的 `Mods/` 目录，例如：
   ```text
   MyCampaign.SC2Mod/
   ```
5. 确认已编辑的数据和本地化文件位于组件目录；独立 Galaxy 源文件仅在项目实际使用时存在：
   ```text
   MyCampaign.SC2Mod/
     Base.SC2Data/GameData/*.xml
     enUS.SC2Data/LocalizedData/*.txt
   ```
   独立脚本入口以实际 Triggers 为准。`Lib*.galaxy` 是编辑器生成文件，不要手工修改。
6. 如果这是新项目或改用了其他文件夹名，重新运行 `tools/init-project.py`，并同步更新 `AGENTS.md` 中经证据确认的模组身份。
7. **实现与验证：** 新触发器保持 GUI 可编辑。明确要求独立 Galaxy 或维护现有脚本时，只修改已确认的手写入口。若使用 `workspace_copy`，先通过部署预览核对方向，再按授权部署；`in_place` 直接编辑实际开发源。最后在 SC2 编辑器中打开并保存组件，重新生成编译库。

---

## 第 3 步——将战役地图保存为 Components

对于每张准备修改的战役任务地图：

1. 在 SC2 编辑器中打开原版战役地图，并确保项目模组没有作为外部 override 激活。
2. 选择 **File → Save As → Components**，保存到：
   ```text
   <configured campaign_maps_dir>/<Category>/<MissionName>.SC2Map/
   ```
   例如：`<configured campaign_maps_dir>/void/paiur01.SC2Map/`。
3. 在地图中选择 **Modules → Dependencies → Add**，添加项目的 `.SC2Mod` 组件。
4. 使用模组中定义的 **GUI action** 连接地图初始化触发器。不要使用原始 Custom Script 调用，否则 SC2 链接器可能静默丢弃模组库。
5. 在当前项目资料目录记录地图接线与项目约定；通用接线参考见 [地图设置](wiki/implementation/per-map-setup.md)。

---

## 第 4 步——构建 Catalog 图索引

使用随仓库提供的 XML 导出、主模组及其递归组件依赖生成 SQLite 查询索引：

```powershell
python tools/build-sc2-catalog-graph.py
```

构建完成后，你和 AI 智能体可以快速查询单位、技能、武器、Actor 与依赖关系，无需整篇读取大型 XML：

```powershell
python tools/sc2-catalog-query.py find Marine
python tools/sc2-catalog-query.py unit-chain Marine
python tools/sc2-catalog-query.py production-chain Barracks
python tools/sc2-catalog-query.py show CAbilTrain:BarracksTrain --limit 20
```

Catalog 索引是导航快照，不是运行时生效性的证明。修改重要数据前仍应核对当前 XML 和实际依赖声明。

---

## 第 5 步——运行预飞行校验

提交修改或打开 SC2 编辑器前运行：

```powershell
python tools/test-suite.py
```

该命令会根据 `agent-config.json` 执行静态检查，并按配置校验选中的本地组件依赖：

- 使用正式 XSD schema 校验 GameData XML catalog。
- 解析 UI layout，并执行兼容引擎的根元素、顶层结构和 ASCII 检查。`SC2Layout.xsd` 仅用于 IDE 和参考，因为它无法覆盖全部编辑器生成格式。
- 检查 Galaxy 语法、局部变量提升、include 路径和禁用运算符。
- 检查 GUI 触发器与完整活动依赖的引用、参数、预设和子动作；明确无 GUI 定义时显示不适用，证据不足仍失败。
- 审计命令卡槽位冲突。
- 检查 `GameStrings.txt` 的玩家可见文本锚点。
- 校验技能 frontmatter 和 Markdown 文档链接。

静态检查通过只代表 `static validation passed`，不等于 SC2 编辑器已经接受，也不等于游戏运行测试通过。

---

## 第 6 步——编辑器交接与安全规则

- 阅读 [SC2 编辑器指南](wiki/reference/editor-guide.md)，了解完整的文件访问与安全矩阵。
- 在 AI 修改与 SC2 编辑器之间切换时，遵循[编辑器交接指南](wiki/guides/editor-handoff.md)。
- SC2 编辑器保存时会规范化 XML，并可能将字符串移动到 `ObjectStrings.txt`。保存后运行 `python tools/audit-gamestrings-anchors.py --fill`，恢复 `GameStrings.txt` 中缺失的玩家可见文本锚点。
- 绝不编辑 `publish/`；该目录只存放发布包产物。
- 问题状态依次为：`reported` → `root cause confirmed` → `source fixed` → `static validation passed` → `Editor accepted` → `packaged runtime passed`。没有对应证据时不要提前推进状态。

---

## 🤝 社区与支持

欢迎在 Custom Campaign Manager（CCM）Discord 社区分享改进、报告问题并讨论工作流。
