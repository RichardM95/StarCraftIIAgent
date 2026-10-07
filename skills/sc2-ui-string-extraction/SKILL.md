---
name: sc2-ui-string-extraction
description: Extract hardcoded player-facing text from StarCraft II `.SC2Layout` UI layouts and Galaxy scripts into GameStrings.txt keys, then localize across locales. Use when a mod hardcodes literal text in `<Text val="..."/>` or `StringToText("...")` and it must become translatable.
---

# SC2 UI 文本外置（布局 + 银河 → GameStrings）

把硬编码在界面里的文案抽成 GameStrings 键，让同一份布局/脚本可以按语言加载不同文本。适用于给第三方 mod 补本地化，或给自己 mod 重构文案层。

## 一、原理（必须先懂这个）

SC2 的界面文本有三个来源：

| 来源 | 载体 | 外置前 | 外置后 |
|---|---|---|---|
| 布局文件 | `*.SC2Layout` | `<Text val="Credits"/>` | `<Text val="@UI/Kit_ScoreScreen/Credits"/>` |
| 银河脚本 | `*.galaxy` | `StringToText("Error")` | `StringExternal("UI/WCMI/Error")` |
| 数据表 | `*.xml` | `<Name value="Button/Name/X"/>` （本来就外置） | —— |

引用语法唯一：**`@` + GameStrings 键**。`<Text val="@UI/WoLTravelPanel/Armory"/>` 会在运行时到当前 locale 的 GameStrings 里查 `UI/WoLTravelPanel/Armory`。

文件位置：`<Mod>\<locale>.SC2Data\LocalizedData\GameStrings.txt`，一行一条 `Key=Value`：

```text
# enUS.SC2Data\LocalizedData\GameStrings.txt
UI/WoLTravelPanel/Armory=<h/>ARMORY

# zhCN.SC2Data\LocalizedData\GameStrings.txt
UI/WoLTravelPanel/Armory=<h/>军械库
```

值的标记**原样保留**，不要翻译/删除：`<h/>`（高亮段）、`<c val="#ColorAttackInfo">…</c>` / `<c val="FFFF80">…</c>`（染色）、`<s val="RONameHighlight">…</s>`、`<n/>`（换行）、`<d ref="…"/>`（数据引用）。

**同一批键必须在每个 locale 文件里都存在**，否则该语言下会显示空白或裸键。

## 二、操作步骤

### 第 0 步 前置确认

- 目标 mod 根目录（`.SC2Mod` 文件夹）与主 mod 是否 `in_place`。
- 要覆盖哪些 locale（列出 `<Mod>\*.SC2Data\LocalizedData\GameStrings.txt` 实际存在的那些，别凭空建目录）。
- 能备份就备份（整份 locale 文件各存一份到 `backups/`）。
- 若子进程工具不可用（见第八节坑 6），**明确记住"没备份"**，交付时要写出来。

### 第 1 步 侦察：找出所有硬编码文本

**1.1 布局文件**

目录（都查）：`<Mod>\Base.SC2Data\UI\Layout\`、`<Mod>\<locale>.SC2Data\UI\Layout\`。

```powershell
rg -n '<Text val="' --glob '*.SC2Layout' "<Mod>\Base.SC2Data\UI\Layout"
```

**要提取**：值不是 `@` 开头、不是 `$` 开头、非空、非纯符号/数字，是给人看的文字。

**不要动**（常见误伤）：

| 写法 | 含义 |
|---|---|
| `<Text val="@UI/…"/>` | 已经外置好了 |
| `<Text val="$parent"/>` | 布局内部引用 |
| `<Text val=""/>` | 故意留空 |
| `<Text val="<d ref="…"/>"/>` | 数据引用 |
| `Style`/`Type`/`RenderType` 等属性 | 不是文本 |

每条记录：**绝对路径 + 行号 + 原文 + 所在 `Frame`/`Label` 的 `name` 与 `Style`**。后者是判断语义的关键（例：`Frame name="CreditsReward"` + `Label name="RewardTitleLabel"` 说明 Credits 是"军费"而非"制作人员"）。

**1.2 银河脚本**

```powershell
rg -n 'StringToText\(' --glob '*.galaxy' "<Mod>\Base.SC2Data"
```

注意：

- `Base.SC2Data\Lib<LibraryID>.galaxy` 是**编译产物**，可能没有对应的源码 `.galaxy`（源码可能内嵌在 `Triggers` 的 CustomScript 元素里）。只能改这份编译产物，并注明"重编译会覆盖"。
- `StringToText` 的实参可能是拼接表达式，不能只替换第一个参数。
- 只用于调试输出的（`TriggerDebugOutput(StringToText("…"))`）也一并外置，保持一致。

**1.3 产出清单**

一张表：`文件 | 行 | 原文 | 上下文名 | 目标键`。没有这张表不要开始改。

### 第 2 步 设计键名

- **优先沿用既有命名空间**：`Button/Name/*`、`Unit/Name/*`、`Character/Name/*`、`GameString/*` 等，别自创。
- 布局元素：`UI/<布局文件名去掉 .SC2Layout>/<语义名>`，例 `UI/Kit_ScoreScreen/Credits`、`UI/Kit_ResearchPanel/ProtossCategory`。
- 脚本：`UI/<ModTag>/<语义名>`，例 `UI/WCMI/Error`（WCMI 是脚本库名）。
- 同一字面量在多处出现 → **复用同一个键**（例 `Credits` 在 `Kit_ScoreScreen.SC2Layout` 和 `Kit_ScoreScreenProtoss.SC2Layout` 里都要指向 `UI/Kit_ScoreScreen/Credits`）。

### 第 3 步 确认键是否已存在 ← 最容易翻车的一步

**必须全文件确认，绝不能只比两个文件的末行。**（真实事故：只比末行就断言"zhCN 缺这个键"，实际上 zhCN 在 10234 行的序列位早就有了，结果补出一条重复键。）

GameStrings 按 **Key 的 ASCII 字典序**排列：`/`(47) < `0-9` < `A-Z` < `_` < `a-z`。据此可以预估目标键该落在哪一段：

```text
Abil/Name/…  →  Behavior/Name/…  →  Button/Name/…  →  Button/Tooltip/…
→  Campaign/…  →  Cethlenn  →  Character/Attitude|Description|Name/…
→  Conversation/…  →  …  →  Unit/…  →  UI/…  →  Z…  →  小写键
```

**两个陷阱：**

1. 作者常常把新增的 `UI/*` 键**追加到文件末尾**（破坏顺序）。所以同一个键可能出现在"序列位"，也可能出现在"文件尾"，甚至两者都有（=重复键，缺陷）。
2. 上一批追加到末尾的键，会让两个 locale 文件的末行错位 —— 两边行数不等并不代表谁缺键。

**最省事的核验方式**是本地化工具（见下节），它直接报 duplicate / missing。否则就用 `read` 逐段确认目标键所在区间。

### 第 4 步 写 GameStrings

- 路径：`<Mod>\<locale>.SC2Data\LocalizedData\GameStrings.txt`，UTF-8。
- 格式：`Key=Value`，一行一条，**每行恰好一个 `=`**（值里的 `=` 会让解析出错，必要时改写文案）。
- **保留文件原有的换行符**（CRLF/LF），不要混用；插入的行要跟邻居一致。
- 值里的标记原样保留。
- 每个 locale 都加同名的键，且**新增键在两边排成同一顺序**（这样两个文件尾部形成对称结构，后续 diff 方便）。
- **绝不产生重复键。**

### 第 5 步 改布局

```xml
<!-- 前 -->
<Text val="SECRET MISSION"/>
<!-- 后 -->
<Text val="@UI/Kit_TravelPanel/SecretMission"/>
```

保留缩进与属性顺序；一次只改 `<Text val="…"/>` 的值。

### 第 6 步 改银河

```galaxy
// 前
libNtve_gf_SetDialogItemText(lp_dialog, lv_item, StringToText("Error"), PlayerGroupAll());
// 后
libNtve_gf_SetDialogItemText(lp_dialog, lv_item, StringExternal("UI/WCMI/Error"), PlayerGroupAll());
```

同一字面量出现多次 → 一次性全部替换。

### 第 7 步 翻译（enUS → zhCN）

- 交给翻译工作区 `E:\Program Files (x86)\StarCraftIITranslateAgent`（独立项目，见其 `AGENTS.md`）。
- 查词：`python skills/sc2-translation/scripts/lookup.py "<原文>"`；词典 `skills/sc2-translation/data/terms.tsv`（**禁止整本载入**）。
- **一词多义必须按 UI 上下文判断**：`credits` 有 `scope=resource → 军费` 与 `scope=credits-screen → 制作人员` 两条，计分屏奖励标题用前者。
- 已确认官方术语：Protoss=星灵、Zerg=异虫、Archive=文献馆、Hyperion=休伯利安号、Research=研究、Air=对空、Ground=对地、cheats=秘籍、None=无。
- 保留标记；中文句末用「。」。

### 第 8 步 验收

- [ ] 各 locale 的**键集合/顺序逐行一致**（用二分 diff 定位分歧，不要只比末行）。
- [ ] 每个新增 `@键` / `StringExternal("键")` 都能在**所有** locale 里解析到。
- [ ] 无重复键、无空值、无缺 `=` 的行。
- [ ] `sc2loc check-missing <locale 文件>` 干净（见下节）。
- [ ] 翻译工作区 `python validate.py --workspace .`（若做过翻译）。
- [ ] SC2 编辑器数据/本地化校验通过，进游戏目视四处（计分屏、面板分类、旅行面板、脚本提示框）。

### 第 9 步 交付记录

写出：布局改动 N 处、银河调用点 M 处、新增键 K 个 × locale 数、以及**没做的事**（备份、validate、编辑器校验）。凡判断过的地方（如 Credits 的取义）标成待确认项。

## 三、配套工具

**Localization Editor SC2 KSP CLI**（`sc2loc`）——专门做这类校验，能报：缺失 locale 文件、跨语言缺键、空值、无 `=` 的坏行、**重复键**、读取错误。

```powershell
sc2loc check-missing "C:\…\zhCN.SC2Data\LocalizedData\GameStrings.txt" --json
```

退出码：`0` 干净 / `1` 有警告错误 / `2` 用法错误 / `3` 运行时异常。若用户没装，建议先装（安装见 skill `sc2-localization`）。

**`tools/audit-gamestrings-anchors.py`** —— 管的是 XML 锚点（`<Description value="Unit/Tooltip/X"/>`），**不管布局和银河的字面量**，别指望它发现本次这类问题。可用 `--locale zhCN --mod-dir "<mod>"` 指定语言。

## 四、实战样例：`RevolutionOverdrive.SC2Mod`（Golden Armada edition）

12 处布局 + 14 处银河调用点 → 18 个键 × 2 locale。

**布局（`Base.SC2Data\UI\Layout\`）**

| 文件 | 行 | 原文 | 目标键 |
|---|---|---|---|
| `Kit_ScoreScreen.SC2Layout` | 206 | `Credits` | `@UI/Kit_ScoreScreen/Credits` |
| `Kit_ScoreScreen.SC2Layout` | 238 | `Protoss Research` | `@UI/Kit_ScoreScreen/ProtossResearch` |
| `Kit_ScoreScreen.SC2Layout` | 268 | `Zerg Research` | `@UI/Kit_ScoreScreen/ZergResearch` |
| `Kit_ScoreScreen.SC2Layout` | 298 | `None` | `@UI/Kit_ScoreScreen/NoReward` |
| `Kit_ScoreScreenProtoss.SC2Layout` | 1107 / 1149 / 1189 / 1229 | 同上 4 条 | 同上 4 键 |
| `Kit_ResearchPanel.SC2Layout` | 399 | `PROTOSS` | `@UI/Kit_ResearchPanel/ProtossCategory` |
| `Kit_ResearchPanel.SC2Layout` | 764 | `ZERG` | `@UI/Kit_ResearchPanel/ZergCategory` |
| `Kit_TravelPanel.SC2Layout` | 421 | `SECRET MISSION` | `@UI/Kit_TravelPanel/SecretMission` |
| `Kit_UnitStatus_Terran.SC2Layout` | 107 | `Tosh` | `@Character/Name/Tosh` |

**银河**

| 文件 | 行 | 原文 | 目标键 |
|---|---|---|---|
| `Base.SC2Data\Scripts\UI\score_screen.galaxy` | 138 | `"GLORIOUS END!"` | `UI/Kit_ScoreScreen/GloriousEnd` |
| 同上 | 140 | `"VICTORY!"` | `UI/Kit_ScoreScreen/Victory` |
| 同上 | 168 | `"Continue to the Archives."` | `UI/Kit_ScoreScreen/ContinueToArchives` |
| 同上 | 170 | `"Continue to the Hyperion."` | `UI/Kit_ScoreScreen/ContinueToHyperion` |
| `Base.SC2Data\Scripts\UI\utils.galaxy` | 75 / 76 / 77 | `"VS Air"` / `"VS Ground"` / `"Hell"` | `UI/Kit_TravelPanel/VsAir` / `/VsGround` / `/Hell` |
| `Base.SC2Data\LibWCMI.galaxy` | 475 / 487 / 494 / 504 / 510 | `"Error"`（5 处） | `UI/WCMI/Error` |
| 同上 | 478 | `"Error: Trigger not set for this Button"` | `UI/WCMI/ErrorNoTrigger` |
| 同上 | 537 | `"Maximum Mission Cheats reached!"` | `UI/WCMI/MaxMissionCheats` |

**新增键（enUS / zhCN）**

| 键 | enUS | zhCN |
|---|---|---|
| `UI/Kit_ResearchPanel/ProtossCategory` | `PROTOSS` | 星灵 |
| `UI/Kit_ResearchPanel/ZergCategory` | `ZERG` | 异虫 |
| `UI/Kit_ScoreScreen/ContinueToArchives` | `<h/>Continue to the Archives.` | `<h/>返回档案室。` |
| `UI/Kit_ScoreScreen/ContinueToHyperion` | `<h/>Continue to the Hyperion.` | `<h/>返回休伯利安号。` |
| `UI/Kit_ScoreScreen/Credits` | `Credits` | 军费 |
| `UI/Kit_ScoreScreen/GloriousEnd` | `GLORIOUS END!` | 荣耀的结局！ |
| `UI/Kit_ScoreScreen/NoReward` | `None` | 无 |
| `UI/Kit_ScoreScreen/ProtossResearch` | `Protoss Research` | 星灵研究 |
| `UI/Kit_ScoreScreen/Victory` | `VICTORY!` | 胜利！ |
| `UI/Kit_ScoreScreen/ZergResearch` | `Zerg Research` | 异虫研究 |
| `UI/Kit_TravelPanel/Hell` | `Hell` | 地狱 |
| `UI/Kit_TravelPanel/SecretMission` | `SECRET MISSION` | 秘密任务 |
| `UI/Kit_TravelPanel/VsAir` | `VS Air` | 对空 |
| `UI/Kit_TravelPanel/VsGround` | `VS Ground` | 对地 |
| `UI/WCMI/Error` | `Error` | 错误 |
| `UI/WCMI/ErrorNoTrigger` | `Error: Trigger not set for this Button` | 错误：此按钮未设置触发器 |
| `UI/WCMI/MaxMissionCheats` | `Maximum Mission Cheats reached!` | 已达到任务秘籍上限！ |
| `Character/Name/Tosh` | `Tosh` | 托什 |

**新命名空间要自造键的例子**：`@Character/Name/Tosh` 是本次新造的键 —— 该 mod 的 `Character/Name/` 命名空间真实存在，但只有 `Zagara`、`Zeratul`；不补键的话界面会直接显示 `Character/Name/Tosh` 原文。插入时按字典序放在 `Character/Name/Zagara` **之前**（`Tosh` < `Zagara`）。

## 五、坑与教训（全都是踩过的）

1. **判断"键是否已存在"必须全文件确认**。只比两个 locale 的末行 → 误判缺失 → 补出**重复键**。（本次真实事故：`UI/HelpMenuDialogTechGlossary_Control_Unit/Category/GoldenProtoss` 在 zhCN 的 10234 行序列位早就存在且已译好，enUS 那份则被作者追加在 12219 行末尾。）
2. **同一个文件不要并发 `edit`**。会触发 `Error: ReplaceFileW EIO (Win32 1175)`；串行改，失败就单独重发那一条。
3. **写前必须读**（fs-observation-policy）。若期间文件被外部改动，会得到 `file changed since it was read` —— 重新 `read` 再写。发现外部改动时**不要回改别人的值**，先确认是谁改的。
4. 重复键是缺陷（`sc2loc check-missing` 会报），必须去掉。
5. `Lib*.galaxy` 是编译产物；若日后从源码重编译，改动会被覆盖。要在交付里注明。
6. **子进程工具可能整体不可用**（`Error: spawn … EACCES` 影响 `pwsh`/`grep`/`glob`/后台作业）。此时只能 `read`/`write`/`edit`：做不了备份、跑不了 `lookup.py` 与 `validate.py`。要如实写进交付，并改用 `read` 分块定位。
7. 标记（`<h/>`、`<c val>`）在翻译时原样带过去，不要"顺手"翻掉颜色名或删掉换行符。
8. 两个 locale 的**行数不等**可能只是某条键位置不同（序列位 vs 尾部追加），不等于缺键。

## 六、相关技能与文档

- `sc2-localization` —— GameStrings / ObjectStrings / TriggerStrings 基础、XML 锚点、`sc2loc` CLI、`audit-gamestrings-anchors.py`
- `sc2-translation` —— 术语与翻译流程（英文/中文）
- `wiki/implementation/localization.md` —— 本地化文件参考
- `E:\Program Files (x86)\StarCraftIITranslateAgent` —— 独立翻译工作区（词典、语料、`validate.py`）
