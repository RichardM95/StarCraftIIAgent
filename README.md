# StarCraftIIAgent — 星际Ⅱ模组开发智能体

> 星际争霸2自定义战役开发智能体。统一知识库 + 29 个技能（10 根 + 13 galaxy + 6 sc2data），开发规则、工具与资料均在本目录维护。
>
> **作者：扯蛋虾米**。参见 [AUTHORS.md](AUTHORS.md)。

---

## 目录

- [简介](#简介)
- [作者声明](#作者声明)
- [文件结构](#文件结构)
- [环境要求](#环境要求)
- [快速开始](#快速开始)
- [任务路由](#任务路由)
- [工具速查](#工具速查)
- [常见场景示例](#常见场景示例)
- [硬性规则](#硬性规则)
- [智能体限制](#智能体限制)
- [故障排除](#故障排除)

---

## 作者声明

本智能体及其配套知识库、技能、工具、配置与文档由 **扯蛋虾米** 创作和维护。统一声明见 [AUTHORS.md](AUTHORS.md)。

---

## 简介

本智能体专为星际争霸2自定义战役开发而设计，整合两大模块（全部位于本目录下）：

1. **统一知识库** — wiki 设计/实现/参考文档、DataEditorXML 导出、W3C XSD schema、Python 工具链、catalog 图查询
2. **统一技能库**（`skills/`） — 29 个技能按需加载（10 根技能 + 13 个 Galaxy 子技能 + 6 个 SC2 Data 子技能）

当前尚未选择项目。提供主 Components `.SC2Mod` 路径后运行 `python tools/init-project.py "<路径>"`。

---

## 文件结构

```
./StarCraftIIAgent/
├── README.md                          ← 本文件（中文使用说明）
├── AUTHORS.md                         ← 统一作者声明
├── AGENT.md                            ← 智能体身份与系统提示词
├── AGENTS.md                           ← 工作区规则入口
├── agent-config.json                   ← 工作区与 SC2 项目路径配置
├── DesignDocument.md                  ← 通用能力来源（项目设计保存到项目资料）
├── setup.md                            ← 安装指南
├── agents\
│   └── trae.yaml                      ← Trae 智能体配置
├── skills\                            ← 统一技能库（29 个技能）
│   ├── sc2-project-entry\             ← 统一入口（路由+工具+流程）
│   ├── sc2-catalog-xml\               ← Catalog XML 路由器
│   ├── sc2-galaxy-scripting\          ← Galaxy 脚本路由器
│   ├── sc2-actor-system\              ← Actor 系统
│   ├── sc2-map-triggers\              ← 地图触发器
│   ├── sc2-bank-system\               ← Bank 存档
│   ├── sc2-localization\              ← 本地化
│   ├── sc2-tools-validation\          ← 工具校验
│   ├── sc2-editor-handoff\            ← 编辑器交接
│   ├── sc2-attack-wave-scaling\       ← 攻击波缩放（含 scripts/）
│   ├── galaxy\                         ← Galaxy 子技能（13 个）
│   │   ├── galaxy-language-fundamentals\
│   │   ├── galaxy-code-organization\
│   │   ├── galaxy-math-strings-conversion\
│   │   ├── galaxy-units-and-groups\
│   │   ├── galaxy-points-regions-geometry\
│   │   ├── galaxy-players-and-alliances\
│   │   ├── galaxy-actor-and-visuals\
│   │   ├── galaxy-sound-camera-environment\
│   │   ├── galaxy-ui-and-dialogs\
│   │   ├── galaxy-triggers-and-functions\
│   │   ├── galaxy-game-systems\
│   │   ├── galaxy-ai-and-techtree\
│   │   └── galaxy-debug-data-catalog\
│   └── sc2data\                       ← SC2 Data 子技能（6 个）
│       ├── sc2data-units-abilities\
│       ├── sc2data-behaviors-validators\
│       ├── sc2data-effects-weapons\
│       ├── sc2data-actors-visuals\
│       ├── sc2data-wizards\
│       └── sc2data-units-reference\
├── wiki\                              ← 战役领域文档
│   ├── index.md                       ← 任务路由器
│   ├── catalog.md                     ← wiki 完整清单
│   ├── log.md                         ← 决策日志
│   ├── design\                        ← 我们在建什么
│   ├── implementation\                ← 怎么建（XML 模式、本地化、陷阱、状态）
│   ├── reference\                     ← 查找表、Actor 架构、SC2 参考
│   └── guides\                        ← 逐步指南
├── tools\                             ← Python 工具链
│   ├── test-suite.py                  ← 预飞行测试套件
│   ├── validate-mod.py                ← 静态校验器
│   ├── sc2-catalog-query.py           ← catalog 查询工具
│   ├── build-sc2-catalog-graph.py     ← 重建 catalog 图数据库
│   ├── deploy-mod.py                 ← 模组部署
│   ├── audit-gamestrings-anchors.py   ← 字符串锚点审计
│   ├── audit-actor-and-card-integrity.py ← 命令卡审计
│   ├── extract-playtest-bugreport.py   ← 游戏测试错误提取
│   ├── check-doc-links.py             ← 文档链接检查
│   └── schemas\sc2-xsd\               ← W3C XSD schema
├── DataEditorXML\                    ← XML 导出（写 XML 前 grep 查询）
└── （项目索引保存到项目资料 runtime/catalog/，不写入套件）
├── docs\                              ← 智能体文档
└── publish\                           ← 发布打包 — 不要编辑
```

### 外部路径（由 `agent-config.json` 解析）

| 用途 | 路径 |
|---|---|
| 主模组与实际编辑源 | 根据 `project.primary_mod`、`project.source_mode` 与 `project.source_mod` 定位 |
| 自定义脚本 | 从当前目标 Triggers 核对手写入口与 include 顺序；项目未必使用独立脚本 |
| 战役地图文件夹 | `<paths.campaign_maps_dir>/` |

---

## 环境要求

- **操作系统：** Windows
- **Python：** 3.x（用于工具链）
- **StarCraft II：** 已安装，编辑器可用
- **TraeCode：** 已安装

---

## 快速开始

### 1. 让 AI 助手加载智能体

在 TraeCode 中对话时，告诉 AI：

```
加载 sc2-project-entry 技能，帮我 [具体任务]
```

AI 会先读取 `AGENTS.md`，再读取 `agent-config.json` 与 `wiki/index.md`，随后加载 `sc2-project-entry` 获取模组身份、任务路由与工具速查；仅在需要智能体身份与知识架构说明时补读 `AGENT.md`。

### 2. 常见启动指令示例

```
加载 sc2-project-entry 技能，帮我给单位 Stalker 添加一个闪现技能变体
```

```
加载 sc2-project-entry 技能，帮我检查当前模组的 XML 是否通过预飞行测试
```

```
加载 sc2-project-entry 技能，帮我把 paiur01 地图的攻击波数量按难度缩放
```

配置或切换项目主 Mod 时，可以直接提供 Components 文件夹路径：

```text
我的主 Mod Components 文件夹是：
E:\Program Files (x86)\StarCraft II\Mods\MyCampaign.SC2Mod

请运行 tools/init-project.py 完成项目初始化，递归检查本地依赖，
更新 agent-config.json；完成后核对 AGENTS.md 中的模组身份并运行配置验证。
不要让我手工编辑 JSON，也不要根据 Mods 目录内容猜测依赖。
```

更多可直接复制的对话模板见[安装与配置指南](setup.md#-与智能体对话示例)和[项目初始化配置](wiki/guides/project-initialization.md#可直接复制的对话示例)。

### 3. 手动加载顺序（供参考）

1. 读取 `AGENTS.md` — 工作区硬性规则、模组身份与统一入口顺序
2. 读取 `agent-config.json` 与 `wiki/index.md` — 解析实际项目路径并路由任务
3. 加载 `skills/sc2-project-entry/SKILL.md` — 统一入口（路由表+工具速查+实现流程）
4. 按任务加载对应深技能；仅在需要身份说明时补读 `AGENT.md`

---

## 任务路由

收到任务后，AI 按以下路由加载对应根技能，再按子主题加载 `skills/galaxy/` 或 `skills/sc2data/` 下的子技能：

| 任务类型 | 加载根技能 | 子技能 |
|---|---|---|
| 项目入口、模组身份、硬性规则、任务路由 | `sc2-project-entry`（统一入口） | — |
| 编写/编辑 Galaxy 脚本 | `sc2-galaxy-scripting` | 见根技能内 Galaxy Sub-Skill Router 表（13 个 galaxy-*） |
| 编写/编辑模组 XML（单位/技能/行为/效果/武器/升级/验证器/足迹） | `sc2-catalog-xml` | 见根技能内 Catalog Sub-Skill Router 表（6 个 sc2data-*） |
| 深入 Actor 工作（CActorUnit/Action/Model/Beam/Sound，VFX/音频，贴图切换） | `sc2-actor-system` | — |
| 编辑地图触发器、GUI 动作接线、胜利/失败钩子 | `sc2-map-triggers` | — |
| Bank 系统、战役持久化、任务存档、解锁 | `sc2-bank-system` | — |
| 本地化（GameStrings/ObjectStrings/TriggerStrings/GameHotkeys）、字符串锚点 | `sc2-localization` | — |
| 运行工具、校验、部署 | `sc2-tools-validation` | — |
| 编辑器交接、问题生命周期、游戏测试 | `sc2-editor-handoff` | — |
| 攻击波缩放、AI 性格波迁移 | `sc2-attack-wave-scaling` | — |

完整路由表（含 13 个 galaxy-* 与 6 个 sc2data-* 子技能的逐项映射）见 [skills/sc2-project-entry/SKILL.md](skills/sc2-project-entry/SKILL.md)。

---

## 工具速查

所有工具路径均相对于当前智能体工作区根目录；实际 SC2、Mods 与地图路径由 `agent-config.json` 解析。

| 需求 | 命令 |
|---|---|
| 当前项目静态预检 | `python tools/test-suite.py` |
| XML schema + Galaxy 语法校验 | `python tools/validate-mod.py` |
| 查询单位/技能/数据链 | `python tools/sc2-catalog-query.py <cmd>` |
| 查询目标触发器库、定义与引用 | `python tools/sc2-trigger-query.py libraries|find|show|check` |
| 查询官方触发器参考案例 | `python tools/sc2-trigger-query.py --reference examples <机制> --summary` |
| 重建 catalog 图数据库 | `python tools/build-sc2-catalog-graph.py` |
| 部署模组到 SC2 安装目录 | `python tools/deploy-mod.py` |
| 检查/填充 GameStrings 锚点 | `python tools/audit-gamestrings-anchors.py --fill` |
| 审计命令卡完整性（保留旧文件名） | `python tools/audit-actor-and-card-integrity.py` |
| 校验技能 SKILL.md frontmatter | `python tools/audit-skill-frontmatter.py` |
| 提取游戏测试错误与日志 | `python tools/extract-playtest-bugreport.py` |
| 检查文档链接 | `python tools/check-doc-links.py` |

### 攻击波工具

| 需求 | 命令 |
|---|---|
| 检查攻击波数量（不修改） | `python skills/sc2-attack-wave-scaling/scripts/wrap_attack_wave_counts.py "<map_path>/Triggers"` |
| 应用攻击波数量包装 | `python skills/sc2-attack-wave-scaling/scripts/wrap_attack_wave_counts.py "<map_path>/Triggers" --apply` |
| 校验所有数量已包装 | `python skills/sc2-attack-wave-scaling/scripts/wrap_attack_wave_counts.py "<map_path>/Triggers" --check` |

---

## 常见场景示例

这些文字可以直接复制到与智能体的对话中。先按 [setup.md 的对话示例](setup.md#-与智能体对话示例) 选择项目；只读研究不要求选择项目。把 `<…>` 替换为实际输入，下面的名称、数值和路径只是需求示例，不代表当前项目。智能体应先读取工作区规则并按任务加载技能，无需每次重复指定技能名称。

### 先明确工作范围

```text
目标：<当前项目或显式组件路径>
需求：<想实现或修复的行为>
输入：<单位/技能/玩家/区域/资源等已知信息>
范围：<只读调查 / 先设计 / 直接修改并静态检查>
交付：说明实际编辑源、关键证据和检查结果，附编辑器与游戏验证步骤。
```

若信息已在项目配置或源中，直接让智能体查询；只有影响实现且无法查到的输入才需要补充。下面的“交付”是检查结果应包含的内容，不代表示例已经执行。

### A. 单位、有效值与技能

#### 1. 只读查询单位完整数据链

```text
调查当前项目 Unit:<单位ID> 的生命、护甲、武器、技能和生产条件。
列出本地覆盖、父对象及活动依赖来源，并说明升级或行为是否会改变这些值。
本次只读，不修改文件。
```

交付：当前有效值及来源，不把参考导出当成项目已经加载的数据。

#### 2. 修改基础生命，保留其他影响

```text
把 Unit:<单位ID> 的未升级基础生命改为120。
先核对继承值、本地覆盖和活动依赖，只编辑实际开发源。
保留已有升级与行为效果，完成相关静态检查，暂不部署。
```

交付：修改前后基础值、修改位置与测试范围。

#### 3. 排查编辑值与游戏显示不一致

```text
编辑器里这个单位生命是120，游戏中却显示150。
请调查 Unit:<单位ID> 的父对象、升级、行为、触发器设置和实际加载版本。
先确认原因并给出证据，再修复源，不直接用另一个覆盖值抵消问题。
```

交付：确认的影响链；未缩小原因时说明缺少什么证据。

#### 4. 复制单位并接入生产

```text
以 Unit:<原单位ID> 为基础创建一个项目独立单位变体。
新单位名称为<名称>，成本为<资源成本>，由<建筑ID>训练。
复用可用模型，检查训练能力、命令卡、Actor和文字，ID前缀沿用实际项目约定。
```

交付：单位到生产/表现的完整接线与对象 ID。

#### 5. 创建闪现技能变体

```text
给 Unit:<单位ID> 添加闪现技能变体，冷却10秒，名称为“暗影闪现”。
先查询现有技能链，创建独立ID，保留原技能；检查按钮、需求、命令卡与Actor。
中文名称使用实际项目的文字键，完成静态检查。
```

交付：能力及关联对象，不假定旧项目的函数或数据前缀。

#### 6. 实现范围伤害技能

```text
实现一个半径<范围>、伤害<数值>的范围技能，只影响<阵营与单位类型>。
查询已有能力、效果、搜索过滤与Actor案例，优先复用活动依赖中的对象。
说明目标过滤、伤害类型、施法入口和视觉表现，并验证相关XML。
```

交付：能力→效果→过滤→表现的实际链路。

#### 7. 临时 Buff 与属性恢复

```text
给<单位ID>添加持续<秒数>的增益，提升<属性与数值>。
使用行为/效果表达，检查叠加、刷新和移除后的恢复；不要凭记忆添加字段。
给出重复施加与提前移除的游戏测试步骤。
```

交付：行为生命周期与适用范围。

#### 8. 条件验证器

```text
让<技能ID>只在目标满足<具体条件>时可用。
先检查依赖中是否已有对应validator，确认字段形状和实际有效条件。
实现后说明限制施法入口还是效果执行，并检查相关引用。
```

交付：条件的作用位置，避免“按钮禁用”和“效果无效”混淆。

#### 9. 升级与科技解锁

```text
增加<升级名称>：完成<前置科技>后可研究，影响<单位和属性>。
核查升级、Requirement、研究能力、按钮和生产入口，检查是否重复解锁。
保留旧升级效果，使用项目独立ID并完成静态检查。
```

交付：前置条件、研究入口和效果对象。

### B. Actor、命令卡与开发文字

#### 10. 投射物或特效不显示

```text
<武器或技能ID>能够造成伤害，但投射物/命中特效不显示。
调查实际效果链及Actor事件、模型、附着点、创建与销毁条件，给出来源证据后修复。
不要只新增一个无接线的模型对象。
```

交付：表现失败的具体链路和游戏复现步骤。

#### 11. 替换模型或音效

```text
给<对象ID>使用已存在的<模型或音效资源>，保留原有玩法。
检查实际资源路径、Actor绑定、动画与音频事件；缺失资源先报告，不猜路径。
给出出生、攻击、死亡等受影响场景的检查步骤。
```

交付：资源及绑定来源；美术资源存在不代表事件已连接。

#### 12. 命令卡冲突

```text
<单位ID>新增按钮后覆盖了原来的<按钮>。
检查有效命令卡、槽位、能力Command索引与Requirement，修复冲突并审计相关单位。
保留原有操作位置，确实需要改布局时先说明选择。
```

交付：冲突原因、最终槽位与能力绑定。

#### 13. 区分不同文字入口

```text
我想修改<对象ID>的<选择面板名称 / 命令卡按钮文字 / tooltip / 世界悬停文字>。
先识别实际文本类型、来源字段与文字键，再更新<语言>对应文本。
不要把编辑器显示名当成玩家文字，也不要扩大成整项目翻译。
```

交付：实际文本类型、字段和字符串锚点。

#### 14. Editor 保存后补文字锚点

```text
编辑器已保存当前组件，部分玩家文字现在显示为键名。
请检查<语言>的GameStrings与ObjectStrings，恢复缺失锚点并检查编码和引用。
保留已有译文，不凭对象名称猜正文。
```

交付：恢复的键及尚缺的文字输入。

### C. 初始化、目标、计时器与攻击波

#### 15. 地图调用模组初始化

```text
在<地图.SC2Map>初始化时调用当前模组导出的GUI初始化动作。
先确认地图实际依赖、模组Library及既有初始化顺序，避免重复执行。
只修改可编辑Triggers，生成的Galaxy用于只读核对。
```

交付：GUI action 接线及加载证据。

#### 16. 创建并完成任务目标

```text
玩家摧毁<三个建筑或单位对象>后完成目标“<目标文字>”。
创建目标后保存专用句柄，统计指定对象，不误完成其他LastCreated目标。
检查重复死亡事件、初始状态和目标完成条件。
```

交付：目标句柄、统计变量和事件/动作关系。

#### 17. 胜败与战役进度

```text
<基地对象>被摧毁时失败，满足<条件>时胜利。
先核查项目已有结算和进度保存入口，再接入GUI胜败条件。
分别验证两条路径，避免直接结束游戏绕过项目存档。
```

交付：胜败条件、项目结算接线与验证步骤。

#### 18. 玩家与区域过滤

```text
只有玩家<编号>的<英雄或单位类型>进入<已建立区域>时触发一次提示。
核对实际地图对象、过滤条件与一次性状态；找不到区域时说明需要的编辑器输入。
完成GUI引用检查，并给出错误玩家、其他单位和重复进入的测试步骤。
```

交付：明确的区域/玩家/单位依赖，不猜地图对象 ID。

#### 19. 倒计时与到期事件

```text
任务开始时显示两分钟倒计时，到期后执行<动作>。
创建并保存timer，窗口、启动动作和到期事件使用正确对象。
检查重复启动、暂停及窗口清理，完成GUI静态检查。
```

交付：timer 和窗口生命周期。

#### 20. 按难度缩放攻击波

```text
把<地图.SC2Map>的普通GUI攻击波按实际难度缩放。
先检查AI启动、目标点、单位组及数量表达式，保留现有调度方式。
查询目标可用的难度函数和预设，不引入未加载库，完成检查后说明Editor验证步骤。
```

交付：包装范围、未处理项和间接依赖。

#### 21. Custom AI 波次迁移

```text
将<地图.SC2Map>中的Custom AI personality波次迁移为可编辑GUI触发器。
保留波次条件、顺序、目标和数量规则，接入原有AI编排入口。
不修改MapScript.galaxy，并检查转换后是否缺引用、参数或资源。
```

交付：迁移范围、调用入口及无法等价转换的部分。

### D. 游戏内对白、对话框与过场

#### 22. 一次性语音、头像与字幕

```text
玩家<编号>进入<区域>后播放一次对白。
声音为<资源>，头像为<模型>，字幕为<文字或键>。
先确认目标依赖和发送定义，保存状态防止重复触发，并检查玩家作用域与资源。
```

交付：事件、状态与对白资源；库兼容不代表声音/画面已经游戏验收。

#### 23. 多句对白或 Conversation

```text
让<角色A>、<角色B>、<角色A>依次说三句台词，上一句结束后再播放下一句。
比较顺序Transmission与项目已有Conversation数据，选用符合目标依赖的GUI写法。
保存实际句柄和上下文，说明等待、打断及缺少配音时的处理。
```

交付：机制选择、台词/资源输入与完整调用关系。

#### 24. 两个选项与超时默认值

```text
弹出两个剧情选择按钮，分别进入<分支A>和<分支B>；十秒未选默认A。
保存窗口和控件句柄，按事件玩家与按钮识别选择。
点击与超时共用只提交一次的入口，完成后清理窗口和timer。
```

交付：选择状态与竞争处理；多人需求需另行明确同步策略。

#### 25. 过场跳过与状态恢复

```text
实现可跳过的<过场或对白段落>，正常完成和按<按键>跳过后都继续任务。
保存进入前镜头、选择、暂停和控制状态，使用同一清理流程，避免重复推进目标。
现有摄影机和场景对象为<输入>，缺少的编辑器对象单独列出。
```

交付：正常/跳过/打断路径与需要用户完成的编辑器步骤。

### E. Bank、脚本与项目资料

#### 26. 先设计 Bank

```text
为当前战役设计Bank，记录任务完成、难度与解锁单位。
先核查已有Bank名称、格式和预加载入口，给出section/key、版本与迁移方案。
本次只设计；尚未约定的信息列出具体选择，不修改源码。
```

交付：基于项目证据的存档方案，不默认创建独立 Galaxy。

#### 27. 实现存档并兼容旧档

```text
按已经确认的Bank设计实现保存和读取，旧档缺新字段时使用约定默认值。
接入现有GUI动作和结算入口，保留旧键并检查预加载顺序。
给出新档、旧档、缺失文件和重复保存的测试场景。
```

交付：版本兼容策略、接线和状态检查。

#### 28. 明确维护手写 Galaxy

```text
维护当前项目的<已确认手写脚本入口>，添加按难度返回倍率的函数。
先从Triggers核对函数前缀及include顺序，只修改手写源码。
遵循项目Galaxy语法规则，完成静态检查，不编辑Lib*.galaxy或MapScript.galaxy。
```

交付：实际入口和调用方式，不沿用别的项目 Library ID。

#### 29. 整理设计材料

```text
这是当前项目的设计材料：<附件或内容>。
先定位项目资料目录，把持久事实写入docs/design/，来源摘要写入docs/sources.md。
区分已确认需求、待决定事项与实现约束，不把项目事实写进套件wiki。
```

交付：设计的当前状态和实质待选项。

#### 30. 保存跨次问题

```text
把<问题>写入当前项目的问题账本，保留复现、已确认原因和证据位置。
更新当前状态与必要决策原因，链接相关规范，不写重复的修改流水账。
状态按实际证据推进，已有未提交改动保留。
```

交付：可继续工作的项目记录。

### F. 检查、部署、排错与官方资料

#### 31. 只检查，不修改

```text
对当前项目执行适用的静态检查，本次不修改文件。
报告实际目标、依赖范围、通过与失败项；地图触发器使用显式目标检查。
没有Editor和游戏证据时，结论最多为static validation passed。
```

交付：实际验证范围，而非一句“全部正常”。

#### 32. 使用 Editor 保存前后证据排错

```text
外部修改后Editor保存时<动作消失或参数变化>，这是保存前后文件和Editor版本。
对照GUI定义、参数归属、子动作与生成代码，确认原因后修复可编辑源。
保留这些证据，给出重载、保存和游戏复现步骤。
```

交付：静态与 Editor 问题分开记录。

#### 33. 从游戏日志追查运行问题

```text
打包运行后出现<现象>，复现步骤是<步骤>，日志和截图位于<路径>。
调查实际加载组件、源版本、触发器调用和资源，确认原因后修复。
给出相同场景的重测步骤，不把静态通过当成运行通过。
```

交付：原因证据、源修复和受影响场景。

#### 34. 部署预览与已授权部署

```text
先按当前source_mode预览部署，列出源、目标和覆盖范围，不执行复制。
若是in_place，确认实际编辑源并说明是否需要部署。
```

预览确认后可继续说：

```text
按刚才核对的方向执行部署，保留恢复能力，检查复制结果。
给出Editor重载保存步骤；发布包目录不作为编辑源。
```

交付：具体方向与实际结果；预览授权不等于复制授权。

#### 35. 构建官方触发器参考索引

```text
官方Mods在<目录>，Campaigns在<目录>。
构建可重建的外部触发器索引，按机制列出精选案例。
不选择项目，不修改官方源；缺失依赖元数据如实报告，不推测完整加载关系。
```

交付：参考来源与输入指纹；查询可用性仍需实际目标。

#### 36. 工具与文档维护

```text
改进本工作区的<工具或文档问题>，保留已有未提交改动，不选择新项目。
复用现有实现与路径规则，修改后运行适用的tools/docs范围检查。
交付变更原因、验证范围及尚未验证的行为。
```

交付：通用工具/资料改进，不修改开发项目或官方资料。

更多安装、切换、路径修复与索引初始化示例见 [setup.md](setup.md#-与智能体对话示例)。触发器专题的多轮沟通见 [详细对话示例](wiki/reference/trigger-agent-dialogue-examples.md)，游戏机制来源见 [对白与对话框案例](wiki/reference/trigger-dialogue-examples.md)。

---

## 硬性规则

以下规则不可协商，违反会导致编译/链接/游戏运行失败：

1. **编辑范围：** 按当前配置 `source_mode` 选择实际编辑源。绝不编辑 `publish/` 文件夹。
2. **Galaxy 源真值：** 从当前 Triggers 核对手写源码和 include 顺序，只修改手写源码或可编辑触发器。具体Library、Bank及前缀来自项目证据，绝不手改生成Galaxy。
3. **地图调用必须用 GUI 动作：** 地图通过模组导出的 GUI 动作接线；链接器行为的证据范围见 [触发器说明](wiki/reference/trigger-knowledge.md#编辑器行为的证据范围)。
4. **目录/XML：** 写 XML 前先运行 `python tools/sc2-catalog-query.py` 或 grep `DataEditorXML/`。字段名和 ID 区分大小写。提交前运行 `python tools/test-suite.py`。
5. **XML 仅 ASCII：** XML 注释和属性值只用 ASCII 字符。
6. **禁用 XML 模式：** `AbilAutoCmd` 按钮类型无效；`CBehaviorBuff` 不支持 `InitEffect`；纯注释 catalog 会被解析器拒绝。
7. **Galaxy 语法：** 局部变量必须提升到函数体最顶部。不支持 `++`/`--` 和 `for(...)` 循环——用 `i += 1;` 和 `while(...)`。include 指令用无扩展名的相对路径。
8. **编辑器交接：** 地图必须由用户保存为 Components。编辑器保存后运行 `python tools/audit-gamestrings-anchors.py --fill`。

---

## 智能体限制

智能体无法完成以下操作，必须由用户在 SC2 编辑器中手动完成：

- 打开和保存 Blizzard 地图（需要 SC2 账号登录）
- 地形、区域、装饰物、寻路
- 过场动画和电影
- 将模组/地图保存为 Components（用户操作）

---

## 故障排除

### 工具报告 `os error 206` 或字符串替换错误

参考 `wiki/implementation/agent-context-efficiency.md` 中的恢复指南。使用精确文本替换、保留编码/换行、按受影响范围运行 `python tools/test-suite.py --scope tools|docs|mod` 或对应回归。

### 编辑器打开地图加载了模组而非原版

**绝对不要**在项目模组作为外部 override 激活时打开地图——会加载模组版本而非原版。

### 添加依赖

地图 → Modules → Dependencies → `<ModName>.SC2Mod`

### 智能体无法读取本地知识库

确认：
1. TraeCode 已安装且工作目录设置为本智能体工作区根目录
2. `AGENT.md` 存在
3. `skills/` 目录下有 10 个根技能子目录 + `skills/galaxy/`（13 个）+ `skills/sc2data/`（6 个）
4. `wiki/index.md` 存在
5. `tools/test-suite.py` 可执行（Python 3.x 已安装）

## 独立使用

在 AI 工具中打开本目录，读取 [AGENTS.md](AGENTS.md) 与 [项目入口技能](skills/sc2-project-entry/SKILL.md)。无需安装其他智能体工作区。

```text
选择 ../StarCraft II/Mods/MyCampaign.SC2Mod 作为开发项目。
调查 Unit:MyMarine 的武器、生产条件及升级影响，本次只读。
```

```text
将当前项目 Unit:MyMarine 的未升级基础生命调整为120。
核对本地覆盖、父对象和活动依赖，只修改实际开发源并验证相关组件。
暂不部署，给出编辑器与游戏验证步骤。
```

按需执行与验收见 [工作区规则](AGENTS.md#独立工作区与按需执行)。本工作区提供开发所需本地化键维护和字符串锚点检查；完整汉化、翻译知识库、自动 UI 文本提取及百科产品不属于本工作区能力。

## 项目资料与运行文件

项目初始化默认配置主模组旁 `<模组名>.agent`，可用 --project-data-dir 指定。先运行 `python tools/project-paths.py` 定位；读取和初始化不创建空资料目录。

项目设计、机制和跨次问题写入该目录 docs/，索引、报告及临时调查使用 runtime/；运行文件默认忽略，项目文档可随项目版本管理。套件 wiki/ 只维护通用规则与参考，历史产物保留原地。详细约定见 [项目资料说明](docs/agents/project-data.md)。

```text
选择 ../StarCraft II/Mods/MyCampaign.SC2Mod，项目资料使用默认旁目录。
核对一个单位的基础值并直接回答；如果发现需要跨次追踪的问题，再写入项目账本。
不要在开发套件里写项目工作记录。
```
