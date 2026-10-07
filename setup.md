# 安装与配置指南——自定义战役智能体起始套件

> **作者：扯蛋虾米。** 项目统一作者声明见 [AUTHORS.md](AUTHORS.md)。

本仓库是一个用于制作《星际争霸 II》自定义战役的**起始工作区**，面向 Cursor、Claude Code、Codex、Antigravity 等 AI 编码智能体，工作流源自 Custom Campaign Manager（CCM）社区的实践经验。

你需要准备：战役构想、任意格式的设计文档、可用的 SC2 编辑器，以及战役地图或模组。  
本套件提供：智能体规则（`AGENTS.md`）、预飞行检查与 schema 校验工具（`tools/`）、节省上下文的 catalog 查询工具、完整的 wiki 知识库（`wiki/`）和 `DataEditorXML/` 参考导出。

> **当前工作区已经配置为** **Legacy of the Ihanrii** 战役。路径和主模组定义在 `agent-config.json`，模组身份定义在 `AGENTS.md`。下文同时说明当前项目和通用模板的配置流程。

如果只需要完成首次安装或选择一个已有项目，请直接参阅[项目初始化配置](wiki/guides/project-initialization.md)。

---

## ⚡ 快速开始清单

1. 将本模板文件夹**复制或克隆**到项目位置。
2. 如果已有 Components 格式的主模组，运行：
   ```powershell
   python tools/init-project.py "<主模组.SC2Mod 文件夹路径>"
   ```
   工具会自动推导 SC2、Mods 和 Maps 路径，递归解析本地依赖并更新 `agent-config.json`。
3. 核对 `AGENTS.md` 中的**模组身份**表，确认它与所选项目一致。不要猜测 Bank 名称、Library ID 或代码前缀。
4. 如果是新项目，在 SC2 编辑器中创建模组，并以 **Components** 格式保存到配置的 `paths.mods_dir` 目录。
5. 将准备修改的 Blizzard 战役地图以 **Components** 格式保存到配置的 `paths.campaign_maps_dir` 目录。
6. 将设计文档粘贴或摘要到 `DesignDocument.md`，然后告诉 AI 智能体：
   > “读取 AGENTS.md、wiki/index.md 和 DesignDocument.md，将设计中的持久事实整理到 wiki/design/，并更新 wiki/implementation/status.md。”
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

更多配置、验证与纠错示例见[项目初始化配置](wiki/guides/project-initialization.md)。

---

## 📁 仓库结构

| 路径 | 用途 |
|---|---|
| `agent-config.json` | 项目路径、主模组与依赖校验策略；优先使用相对路径，也支持跨盘符绝对路径 |
| `AGENTS.md` | **智能体主入口**——硬性规则、模组身份、命名前缀与工作流 |
| `setup.md` | 本安装与配置指南 |
| `DesignDocument.md` | 原始设计笔记、GDD 或大纲 |
| `tools/` | 预飞行测试、XML/Galaxy 静态校验、catalog 图查询与模组部署工具 |
| `tools/schemas/sc2-xsd/` | Catalog、GameData、SC2Layout 等 XML 的 W3C XSD schema |
| `wiki/` | 结构化知识库；`wiki/index.md` 是任务路由器，`wiki/catalog.md` 是完整目录 |
| `wiki/design/` | 结构化设计文档，如任务、单位与机制 |
| `wiki/implementation/` | 实现细节，如 XML 模式、本地化、Galaxy 陷阱与 Bank 系统 |
| `wiki/reference/` | SC2 引擎与编辑器参考，如 Actor 架构、Galaxy 语言与触发器 XML |
| `wiki/guides/` | 分步指南，如编辑器交接、多电脑配置和模拟 Bank 测试 |
| `wiki/log.md` | 记录架构决策及其原因的决策日志 |
| `<configured mods_dir>/AeonOfIhanrii.SC2Mod/Base.SC2Data/Epi_Main.galaxy` | 自定义脚本块源码，会被包含进编译后的库 |
| `<configured mods_dir>/AeonOfIhanrii.SC2Mod/` | 主模组 Components 目录 |
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

初始化完成后，检查 `AGENTS.md` 中的**模组身份**表是否与实际项目一致：

| 字段 | 示例 | 说明 |
|---|---|---|
| Mod file | `MyCampaignMod` | SC2 `Mods/` 下的文件夹名：`MyCampaignMod.SC2Mod/` |
| Library ID | `MyCampaignLib` | 触发器编辑器中的库名称或标识 |
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
3. 新触发器先在触发器编辑器中用 GUI 事件、条件和动作实现；只有 GUI 难以表达的局部逻辑才在触发器内嵌入少量自定义代码。仅在明确采用独立 Galaxy 脚本时创建脚本块，并核对 `AGENTS.md` 中的名称；当前项目已有 `Epi_Main`。
4. 选择 **File → Save As → Components**，将模组保存到 SC2 的 `Mods/` 目录，例如：
   ```text
   AeonOfIhanrii.SC2Mod/
   ```
5. 确认已编辑的数据和本地化文件位于组件目录；独立 Galaxy 源文件仅在项目实际使用时存在：
   ```text
   AeonOfIhanrii.SC2Mod/
     Base.SC2Data/GameData/*.xml
     enUS.SC2Data/LocalizedData/*.txt
   ```
   当前项目还包含 `Base.SC2Data/Epi_Main.galaxy`。`Lib*.galaxy` 是编辑器生成文件，不要手工修改。
6. 如果这是新项目或改用了其他文件夹名，重新运行 `tools/init-project.py`，并同步更新 `AGENTS.md` 中经证据确认的模组身份。
7. **实现与验证：** 新触发器保持 GUI 可编辑。明确要求独立 Galaxy 或维护现有脚本时，才修改 `Base.SC2Data/Epi_Main.galaxy` 或 `Base.SC2Data/Scripts/` 下的源码。若使用 `workspace_copy`，先运行 `python tools/deploy-mod.py --dry-run` 核对方向，再复制组件；当前 `in_place` 模式无需部署。最后在 SC2 编辑器中打开并保存组件，让编辑器重新生成编译库。

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
5. 在 `wiki/implementation/per-map-setup.md` 中记录地图触发器接线方式。

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
