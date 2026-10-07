# 自定义战役工具指南

本目录包含《星际争霸 II》自定义战役开发所需的维护助手、静态检查器、catalog 查询工具和自动化测试入口。

项目路径从 `agent-config.json` 读取。相对路径以工作区根目录为基准解析，便于跨电脑使用；跨盘符初始化会退回到机器专属的绝对路径，并在校验时给出警告。单次命令显式传入的 `--mod-dir` 优先级最高；对于不采用配置布局的电脑，`SC2_MODS_PATH` 仅在未配置主项目时作为后备；存在明确配置时，目标缺失不会寻找同名旧副本；`workspace_copy` 必须设置 `project.source_mod`，不会回退安装目录。`validation.include_dependencies` 控制是否递归校验组件依赖内容，`validation.exclude_mods` 用于记录有意排除的依赖模组。

---

## ⚡ 智能体与开发者快速决策表

| 需求 | 命令 | 用途 |
|---|---|---|
| **通过一个 Mod 路径初始化/选择项目** | `python tools/init-project.py "<primary.SC2Mod>"` | 推导 SC2 布局、校验递归依赖并安全写入 `agent-config.json` |
| **提交前验证修改** | `python tools/test-suite.py` | 完整预检；工具或文档维护可加 `--scope tools` / `--scope docs`，模组专项可加 `--scope mod` |
| **检查问题生命周期账本** | `python tools/audit-issue-lifecycle.py` | 校验活动问题的状态标签与已达到阶段所需证据字段 |
| **校验 GameData XML 与 Galaxy** | `python tools/validate-mod.py` | 使用正式 XSD 校验 GameData XML，并检查 Galaxy 变量提升、非法语法和 include 路径 |
| **检查递归模组依赖** | `python tools/inspect-mod-dependencies.py` | 从 ComponentList 的 info 组件出发，递归解析本地 `.SC2Mod` 依赖 |
| **查询单位、技能或数据链** | `python tools/sc2-catalog-query.py <cmd>` | 节省上下文的 catalog 查询：查找对象、解析引用并输出依赖链，无需载入大型 XML |
| **查询精确样例对象** | `python tools/sc2-reference-query.py object Unit:Marine --component liberty` | 返回组件中的完整 XML 对象；可用 `--max-chars` 限制输出 |
| **核对或更新组件快照** | `python tools/refresh-sc2-reference.py --mods <目录> --campaigns <目录> --cm <目录>` | 默认只核对；确认差异后加 `--apply`，保留旧版备份 |
| **查找官方/合作组件案例或本地化** | `python tools/sc2-reference-query.py find <term> --family <Family> --component <name> --limit 20` | 按组件、数据类型和语言限定只读样例搜索 |
| **刷新 catalog 查询数据库** | `python tools/build-sc2-catalog-graph.py --sqlite-only` | 输入变化时只更新查询用 SQLite；完整图与报告去掉此参数 |
| **预览/部署模组到 SC2** | `python tools/deploy-mod.py --dry-run` | 只显示源与目标；核对后去掉 `--dry-run` 复制组件 |
| **检查 GameStrings/本地化锚点** | `python tools/audit-gamestrings-anchors.py --fill` | 检查 GameData XML 文本引用，并从 `ObjectStrings.txt` 自动恢复缺失键 |
| **审计命令卡** | `python tools/audit-actor-and-card-integrity.py` | 检测高置信度命令卡槽位冲突和攻击按钮被替换问题 |
| **定位项目资料和运行目录** | `python tools/project-paths.py` | 只读输出路径，不创建目录 |
| **提取游戏测试错误与日志** | `python tools/extract-playtest-bugreport.py` | 从 SC2 `GameLogs` 中提取警告和脚本错误，生成便于分诊的 `bugreport.txt` |
| **检查文档链接** | `python tools/check-doc-links.py` | 扫描仓库 Markdown，查找损坏的本地相对链接 |

---

## 1. 预飞行检查与测试

开发期间使用以下工具，在启动 SC2 或提交代码前捕获本地错误：

- **`init-project.py`**——对话式配置的统一项目选择入口。传入主 Components `.SC2Mod` 文件夹后，工具会推导标准 SC2 布局，递归校验本地依赖，并只在全部检查通过后原子更新 `agent-config.json`。使用 `--dry-run` 预览；仅非标准布局需要显式目录参数。
- **`test-suite.py`**——面向 AI 智能体与开发者的统一测试入口。它会发现配置的主模组、打印精确目标，并在没有找到模组时失败，而不是误报成功。默认遵循 `agent-config.json` 的依赖校验策略；可用 `--primary-only`、`--include-dependencies` 或可重复的 `--exclude-mod` 做单次覆盖。它运行工具单测，并调用 `validate-agent-config.py`、针对主模组和选定依赖的 `validate-mod.py`、`audit-actor-and-card-integrity.py`、`audit-gamestrings-anchors.py`、`audit-skill-frontmatter.py` 与 `check-doc-links.py`。
- **定向预检**——`--scope tools` 只运行工具单测；`--scope docs` 运行问题账本、技能格式和文档链接检查；`--scope mod` 运行项目配置、主模组、依赖与模组专项审计。交接或提交前仍运行完整预检。
- **`validate-agent-config.py`**——校验配置 schema、必需目录和主模组，然后递归验证本地组件依赖图。跨盘符绝对路径以及尚未创建的可选战役地图目录只产生警告，避免误判失败。
- **`inspect-mod-dependencies.py`**——读取每个模组的 `ComponentList.SC2Components`，定位 `Type="info"` 组件，解析 `<Dependencies>`，并在共享节点与循环保护下递归跟踪本地组件模组。使用 `--json` 获取机器可读输出。检查工具、预检套件与索引共用依赖根规则：配置的编辑源使用配置 Mods；临时显式组件寻找自己的 Mods 祖先；无法推导时必须传 `--mods-dir`，不使用另一安装的同名依赖。
- **`audit-skill-frontmatter.py`**——校验所有 `SKILL.md` 的 frontmatter：检查 YAML 块、`name` 是否与目录匹配、`description` 是否存在且为非空单行，以及正文是否非空。
- **`validate-mod.py`**——综合静态校验器：
  - 使用 `lxml` 或 `xmllint` 后备，对 GameData XML 执行正式 W3C XSD 校验（`tools/schemas/sc2-xsd/Catalog.xsd`）；两种后端都不存在时校验会失败关闭。
  - 解析 UI layout XML，并执行兼容引擎的根元素、顶层子元素与 ASCII 检查。随附的 `SC2Layout.xsd` 仅用于 IDE/参考，不作为强制校验，因为其命名空间和字段限制无法覆盖所有编辑器输出。
  - 执行项目 XML 规则，包括注释/属性仅 ASCII，以及拒绝只有注释的 catalog。
  - 校验 Galaxy 脚本 AST/语法，包括函数内变量提升、include 路径、禁用运算符和非 ASCII 字符。
- **`audit-actor-and-card-integrity.py`**——命令卡静态检查器。文件名为兼容旧工作流而保留，但不代表覆盖 Actor 绑定。高置信度错误会正常失败；由于活动依赖中的 Requirement 可能使共享槽位成为有意设计，歧义候选只做汇总。使用 `--show-warnings` 查看候选，或使用 `--strict` 让所有未解决候选导致失败。
- **`audit-gamestrings-anchors.py`**——检查活动 catalog 的 `Name`、`Tooltip`、`Description` 引用是否存在于 `GameStrings.txt`。编辑器保存后可用 `--fill` 从 `ObjectStrings.txt` 恢复缺失键。
- **`schemas/sc2-xsd/`**——随附的 SC2 GameData 与组件/IDE 参考 XSD。CLI 会强制校验 Catalog/GameData schema；出于上述兼容原因，`SC2Layout.xsd` 仅作参考。

---

## 2. Catalog 导航与查询

GUI 触发器使用独立的 `sc2-trigger-query.py`：`build` 从明确指定的 Mods/Campaigns 原库构建可重建索引；`libraries` 确认目标库范围；`find`/`show` 查询完整定义；`examples` 查询人工核查的七类案例；`check` 检查引用与参数。没有项目时使用显式 `--reference`；`check --templates` 检查首批 GUI 片段。完整命令与证据边界见 [触发器查询指南](../wiki/reference/trigger-knowledge.md)。

以下工具用于浏览 Blizzard 和自定义 catalog 数据，避免直接读取大型 XML 导出：

- **`sc2-catalog-query.py`**——主要的节省上下文查询工具，使用 `<项目资料>/runtime/catalog/catalog.sqlite`（或 `graph.json`）：
  - 查找对象：`python tools/sc2-catalog-query.py find <term> --source-class local_mod`
  - 检查单位链：`python tools/sc2-catalog-query.py unit-chain <Unit:Id>`
  - 检查生产链：`python tools/sc2-catalog-query.py production-chain <Unit:Id>`
  - 检查 Actor 链：`python tools/sc2-catalog-query.py actor-chain <Actor:Id>`
  - 跟踪依赖：`python tools/sc2-catalog-query.py show <Family:Id> --limit 30 --depth 2`
  - 查找未解析引用：`python tools/sc2-catalog-query.py unresolved --contains <term>`
- 默认索引用输入清单检查文件增删、大小与修改时间；未选择项目时仍检查参考资料，项目配置失效或源目录缺失时明确停止。查询发现过期会指出文件并停止。怀疑文件内容被替换但大小、时间都被保留时，在子命令前加 `--verify-input-hashes` 做严格校验（会多读一遍输入）。需要当前数据时运行一次 `python tools/build-sc2-catalog-graph.py --sqlite-only`；仅为查看旧快照可加 `--allow-stale`，输出会标记为历史检查，不能据此声称当前项目值已确认。SQLite 与完整图各有清单：`--sqlite-only` 不会把旧 `graph.json` 标记为已更新。
- **`build-sc2-catalog-graph.py`**——从顶层 TXT 参考导出、非活动导出、配置的主 Mod 与递归解析的本地组件依赖构建索引。日常刷新用 `--sqlite-only`，跳过大型 JSON、GraphML 和对象摘要；需要完整图报告时不加参数。主模组定义标记为 `local_mod`，依赖定义标记为 `active_component_dependency`。构建在创建输出目录前检查活动依赖；缺失或损坏默认停止。
- 索引输入清单版本为3，包含实际 `Type="info"` 文件与依赖完整性状态。旧版或缺少清单的索引必须重建；清单不替代当前组件证据。缺失依赖问题逐项保留，不伪造补齐结果。`project.resolve_dependencies_recursive=false`也属于受限主组件调查：构建与查询必须显式允许部分调查，并标明递归被配置关闭。
- 部分调查需要显式 `--allow-incomplete-dependencies`：构建保存 `partial` 和缺失/损坏清单；每次查询再次带该参数并显示部分调查警告。它只允许读取现有数据，不能据此确认完整有效值、写回或通过依赖验收；`--allow-stale` 仅允许历史快照，不能代替部分依赖权限。inspection工具的JSON也包含依赖状态。
- 临时组件调查示例：`python tools/inspect-mod-dependencies.py --mod-dir "<组件>" --mods-dir "<Mods>" --json`；预检对应 `python tools/test-suite.py --mod-dir "<组件>" --mods-dir "<Mods>" --include-dependencies`。非标准布局必须给出依赖根，不猜父目录。
- 顶层 `DataEditorXML/*.txt` 在图中标记为 `reference_export`；只有递归确认的组件依赖标记为 `active_component_dependency`。参考导出中的对象不能证明运行时已加载。
- **`sc2-reference-query.py`**——按需检索官方与合作组件原始样例及英文/中文本地化。先用 `components` 看组件列表，再用 `find` 指定 `--component`、`--area gamedata|enus|zhcn`、`--family` 和 `--limit`。输出相对路径与行号。顶层 TXT 有部分内容与样例 XML 完全重复，通常先查询 catalog 图，再针对具体实现查样例；样例不参与活动依赖判定，也不要求重建图数据库。
- **`refresh-sc2-reference.py`**——提供三个来源类别目录后，默认逐文件核对路径、大小与 SHA-256；加 `--apply` 才更新快照，先在暂存目录验证，并保留旧版备份。工作区目标路径由工具自身位置推导；来源目录作为单次参数传入。
- **`check-doc-links.py`**——校验本地 Markdown 链接目标，并排除生成目录和发布目录。

> Catalog 数据库是导航快照，可能包含非活动来源。数据库中存在 provider 不等于运行时已经启用；重要结论仍需核对当前 XML、依赖声明与来源路径。

---

## 3. 部署与游戏测试错误提取

- **`deploy-mod.py`**（以及 `deploy-mod.ps1`）——在 `workspace_copy` 模式下把 `.SC2Mod` 组件文件夹复制到 `agent-config.json` 的 `paths.mods_dir`（可用 `--mods-dir` 覆盖），不改写源或目标的 `Lib*.galaxy`。自动部署保留 `project.primary_mod` 相对于 Mods 的子目录；显式 `--source` 则按源文件夹名部署。目标必须留在 Mods 目录内；除完全相等的 no-op 外，源与目标不得互相包含（dry-run同样检查）；已配置的目标目录缺失时不回退其他安装。始终先使用 `--dry-run`；嵌套或普通原位源与目标相同时安全退出。复制后需在 SC2 编辑器中保存组件以重新生成编译库；当前 `in_place` 模式无需部署。
- **`extract-playtest-bugreport.py`**（以及 `extract-playtest-bugreport.ps1`）——从 SC2 `GameLogs` 中提取警告与脚本错误，生成清晰的分诊报告 `bugreport.txt`。

静态工具通过只代表 `static validation passed`。没有 SC2 编辑器和实际场景证据时，不得表述为 `Editor accepted` 或 `packaged runtime passed`。

`test-suite.py` 的 `mod/all` 范围还运行 `sc2-trigger-query.py check`，检查主目标 GUI 定义和实际活动依赖，不需要参考索引。可传 `--campaigns-dir` / `--mods-dir`；catalog 排除选项不会裁剪触发器依赖。确认没有可检查 GUI 定义时输出 `not_applicable`，缺失登记或依赖证据仍失败。触发器名称检索同时匹配内部、中文与英文名称；索引 v2 需从原外部根重新构建。完整用法见 [触发器查询](../wiki/reference/trigger-knowledge.md)。



## 索引与部署发布

索引SQLite与JSON各自嵌入build_id，并与各自manifest绑定。所有路径的索引都按记录的工作区、主组件、依赖根和递归范围检查输入增删、信息文件及可选哈希；显式主组件构建不要求把它登记成活动项目。查询显示实际范围。build_id不一致、缺失或v3身份损坏不能由`--allow-stale`放行。旧版索引仅能显式历史检查，原部分状态仍独立要求`--allow-incomplete-dependencies`。

构建完整输出暂存在同级目录，核对输入未改变后切换。`--sqlite-only`保留旧JSON及报告，全文构建保留非本次工具输出；失败保持旧索引与manifest配对。

部署先暂存与逐文件核验，再切换。`--clean`生成纯源副本，普通部署先复制现有目标再覆盖源，保留目标额外文件；源在复制过程中变化则停止。成功后保留一份同级工具拥有上一版，轮换只清理带正确所有权标记的工具备份，拒绝人工碰撞与symlink/junction。切换失败回退；恢复失败保留暂存、目标、上一版等相关路径并逐项报告，禁止自动清理这些取证目录。锁清理问题不会掩盖主错误。
