# CASC 官方依赖缓存

[English](official-casc-cache.en.md)

入口为 [sc2-official-cache.py](../../tools/sc2-official-cache.py)。CASC 只在显式 `probe` / `sync` 中打开；依赖、GUI、Catalog 和预检只消费已发布官方缓存，不加载 CascLib、不自动提取 CASC 或联网。本地打包组件通过 StormLib 只读访问，见[格式转换与归档读取](../../tools/README.md#打包组件与格式转换)。命令不改写项目配置、游戏或模组。

## 诊断与同步

安装目录默认取当前配置，DLL 必须显式传入。另一个安装使用 `--sc2-install-dir`，并为其目标指定实际 `--mods-dir`。

```text
python tools/sc2-official-cache.py probe --casc-dll "<CascLib.dll>"
python tools/sc2-official-cache.py sync --target "<Components>" --casc-dll "<CascLib.dll>"
python tools/sc2-official-cache.py sync --target "<Components>" --casc-dll "<CascLib.dll>" --apply
```

`probe` 输出安装布局、唯一活动构建、DLL 位数/指纹、接口、字符集尝试及 XML 样本的诊断 JSON。`read_verified` 要求存储打开、元数据和定义文件完整读取并可解析，不表示依赖完整。原生调用在独立子进程中执行，单次请求默认超时 60 秒，可用 `--timeout` 调整；异常、超时和崩溃成为诊断，句柄由子进程关闭/回收。

`sync` 默认仅在内存中预览，不创建缓存。先解析组件依赖；已知 Core/bootstrap 等发布前提不满足时停止在元数据阶段，返回 `partial`，不读取整批 GameData、本地化载荷。`extraction_phase` 区分 `metadata` / `payload`，数量仅统计成功读到的文件，未尝试的语言不推断为可用或缺失。必要定义或引用文件缺失时也返回 `partial`；未显式允许部分结果时，`--apply` 拒绝发布。可选语言文件不可读时记入 `unavailable_files`，不补造文字。JSON 的 `applied` 才表示实际发布。

`--allow-partial` 显式继续提取已发现组件的载荷；配合 `--apply` 才发布部分研究缓存。默认目录为完整缓存的同级 `<构建键>-partial/`；普通研究查询可以自动发现它，自定义路径仍禁止覆盖不同完整性等级的缓存。退出码仍为 1，表示依赖未完整确认，并不等同于发布失败，应同时检查 `applied`。`file_states` 区分 `readable`、`unavailable`、`not_attempted`；缺失引用保留在组件 `assessment.problems` 中，不作为不可读的现存文件伪报。组件 `assessment.closure` 与整批 `loading_status` 分别说明文件闭包和目标加载证据。

默认目录为套件旁 `StarCraftIIAgent-data/reference/casc/<安装标识>/<构建键>/`，`--official-cache` 可指定根目录。保留 Mods/Campaigns 逻辑结构，路径统一小写，文件保留原始字节，清单记录实际 CASC 名称、安装/构建、DLL 指纹、文件哈希、语言可用性和登记证据。内容限于组件/依赖元数据、GUI 登记及库、Galaxy 定义、GameData XML 与 zhCN/enUS 本地化；地图、模型、贴图、声音和过场不在范围内。

发布前核对路径边界、构建身份、文件哈希、XML、库登记和 GameData 引用闭包，复用暂存/目录切换机制。失败保留当前缓存；已有目录必须是同安装/构建的缓存。禁止把缓存设在套件、游戏或两者的祖先目录。不跨安装或构建混用缓存。

## 加载证据与边界

优先读取真实 ComponentList 定位的 info 文件；没有清单时只使用确实存在的 DocumentInfo。不修造官方组件清单。已有但损坏的本地组件继续报错；只有本地不存在且缓存中精确匹配的引用才使用官方来源。纯网络引用、缺失自定义依赖、名称相似的组件不自动映射。

Core 是 SC2 的隐式基础层，使用 `sc2_core_base` 规则登记在组件依赖之前；依据为用户确认的 SC2 基础契约及 [Core Always First 原始研究](https://github.com/sc2-arcade-watcher/sc2-file-format-docs/blob/main/archive-system.md#core-always-first)。规则只应用于当前实现已核对的引擎，不需要每次重复证明启动调用链；仍要求匹配的安装/构建、Core 文件及真实 LibraryList/NativeLib。规则不伪造 DocumentInfo 或反汇编调用点，二进制 bootstrap profile 是可选的另一类证据。

21 项内置表最初由 locale 研究定位，但 [通用路径校验流程](https://github.com/sc2-arcade-watcher/sc2-file-format-docs/blob/main/archive-system.md#modpath-validation-algorithm) 也会使用该链、递归子依赖、验证 Base.SC2Data 并注册依赖输出。已核验的官方内置单人组件因此使用 `engine_dependency_chain`，保留原始表来源与规则依据；不能因表名含 locale 就将这些关系一律降为研究。多人 stacking 的额外关系不属于这条确认规则，保持原有限制。自定义和无法映射的网络依赖也不套用该规则。

新缓存清单版本为 3，组件评估版本为 3，分别记录文件可用性、依赖解析、Catalog 来源范围和基础层状态。旧缓存及旧评估只读重验，在内存中重新计算；只有当前规则、原始文件、引用闭包全部满足时才解除旧的部分状态，未知诊断仍保留。旧 `complete` 不豁免验证，未知评估版本拒绝使用。不从缓存或外部 JSON 导入可信引擎规则。

基础 DLL ABI 按 [CascLib 原始接口](https://github.com/ladislav-zezula/CascLib/blob/master/src/CascLib.h) 核对；只用本地存储、枚举、读取和严格数据检查，不用扩展参数结构、在线打开或加密内容零填充选项。错误码 2 只作为具体调用诊断，不能据此判定游戏损坏。

## 声明、递归与顺序

`ComponentList` 指定的 info 文件是声明依据，真实 `DocumentInfo` 的依赖按原始顺序递归；已有元数据损坏时不回退。每条边保留 `ordinal`、`raw`、`evidence` 与 `relation`，分别记录声明、官方内置链、locale 和 bootstrap 关系。Heros 声明 Void 战役的关系已确认，上游未知项不改变这条直接声明。

`traversal_order` 是依赖先于当前组件的去重后序遍历，循环作为错误报告。全部关系和来源确认后，`loading_order` 记录 Core 最先、依赖在前、当前组件最后的组件优先级；这不声称实现 XML 内部字段合并，`file_merge_order` 独立保持未确认，同级字段冲突继续显示歧义。Catalog 按遍历记录组织来源，保留本地优先和同级冲突，不以组件文件名排序推断覆盖。Includes 相对包含文件目录解析，按声明顺序递归，重复去重、循环及缺失/越界均失败。

缓存仍逐个核对全部文件。目标的 `official_problems` 仅汇总涉及组件及必要 Core 研究来源的加载未知；其他组件的加载未知保留在缓存评估中。在已核对的 SC2 安装中，Core 是必要基础来源；未知安装不借用其他安装的 Core。文件损坏和必需载荷不可读仍是硬错误。

## 共用查询与新鲜度

`init-project.py`、`inspect-mod-dependencies.py`、`validate-agent-config.py`、`sc2-trigger-query.py`、`build-sc2-catalog-graph.py`、`sc2-catalog-query.py`、`test-suite.py` 均支持 `--official-cache`。未传时只读定位目标 Mods 所属安装的匹配构建；缓存缺失继续报告依赖缺口，显式缓存不合法则失败。

```text
python tools/inspect-mod-dependencies.py --official-cache "<缓存根>"
python tools/sc2-trigger-query.py --official-cache "<缓存根>" libraries
python tools/sc2-trigger-query.py --official-cache "<缓存根>" check
python tools/build-sc2-catalog-graph.py --official-cache "<缓存根>" --locale zhCN --sqlite-only
python tools/sc2-catalog-query.py --official-cache "<同一缓存根>" stats
python tools/test-suite.py --scope mod --official-cache "<缓存根>"
```

GUI 保留库归属、参数、冲突和加载链检查，输出 `origin` / `casc` 来源。缓存中存在不等于目标已加载。参考索引不成为活动依赖。

## 官方研究查询

```text
python tools/sc2-official-cache.py sync --casc-dll "<CascLib.dll>" --allow-partial --apply
python tools/sc2-trigger-query.py find TriggerAddEvent --limit 5
python tools/sc2-trigger-query.py show Ntve:FunctionDef:<ID>
python tools/build-sc2-catalog-graph.py --official-research --out "<研究索引>" --sqlite-only
python tools/sc2-catalog-query.py --db "<研究索引>/catalog.sqlite" stats
```

按精确安装与构建优先定位完整缓存，其次定位同级部分缓存；完整缓存存在但损坏时停止，不回退遮盖。普通 Catalog 默认项目刷新传递 `--official-research`，GUI 的 `find/show/libraries/examples` 也开放已验证的官方研究来源。只有官方加载关系未确认时才开放研究输出；损坏文件、缺失自定义依赖、无法映射的网络引用和关闭递归仍受原有许可或硬错误边界约束。查询不提取、不联网。

已匹配且通过验证的 Core 加入隐式基础依赖边；Ntve 按真实库登记进入活动范围。未确认的组件或非适用构建仍保留研究归属，不将库存在直接等同于目标兼容。Catalog 将这些来源归入 `reference_export` 并保留 CASC 路径和 `loading_status`。配置验收、部署预检和触发器 `check` 继续要求完整证据。历史部分索引不能直接免许可读取；默认项目须从当前来源重建，显式历史索引保留原来的许可边界。

Catalog 保留 `local_mod`、`active_component_dependency`、`reference_export` 分类和本地覆盖优先级，官方定义附加 CASC 清单、构建和路径。本地化由构建时 `--locale enUS|zhCN` 选择，默认 enUS，不跨语言补值，节点保留来源。默认项目查询可按需刷新 SQLite，并复用原语言或用查询的 `--locale` 覆盖；显式索引、`--no-auto-rebuild` 和 `--allow-stale` 保持只读。刷新只读取现有官方缓存，不自动开启通用部分许可；失败保留旧索引。完整行为见[工具指南](../../tools/README.md#索引与部署发布)。

缓存验证与 Catalog 共用登记入口和递归引用闭包判定。`GameData.xml` 的附加数据空间登记不代表所有标准分类表，参见[编辑器数据空间说明](https://s2editor-guides.readthedocs.io/New_Tutorials/04_Data_Editor/data-spaces/)。研究模式收录库存中实际存在、可解析的 Catalog XML，并明确标为未确认加载；标准表候选名称不能证明其活动加载。附加登记引用缺失或越界是硬错误，未知根元素保留为未分类文件。对具有已核对标准来源规则的构建，标准表和附加入口闭包取并集；缺少附加入口不再否定标准表。非空未登记文件继续未确认；仅标准来源规则已确认时，未登记的空 Catalog 可作为无实体占位文件保留，不阻断活动数据范围。只有原始清单明确没有 GameData 且库存也无相关 XML 时，才确认没有 Catalog。本地手写模组扫描范围不变，TXT 仍只是参考。一次验证复用 XML 解析结果，文件仍逐个核对哈希；输入清单按缓存根合并，不建立跨命令的信任缓存。

统一预检对当前配置源（包括 `workspace_copy`）运行配置验收；其他显式目标运行目标依赖检查。Mods、Campaigns 和缓存覆盖传到各相关检查。其他目标默认仅校验主组件源码，但依赖解析保持递归，不继承当前项目的扫描开关、排除项或关闭递归设置。Catalog 保存实际采用的递归范围。配置验收的 `--mods-dir` / `--campaigns-dir` 仅覆盖本次依赖核对，不写配置。

Catalog 输入清单现为版本 8，旧索引需重建；原归档身份与成员证据、研究模式、加载规则及证据指纹、缓存清单、库存、活动构建信息、语言选择及实际 Campaigns 根目录进入新鲜度检查。构建支持 `--campaigns-dir`，查询默认复用记录的目录，另传目录须与索引选择相同；另传缓存也须匹配。XML 解析失败中止索引发布，不以跳过文件获得成功。本地化保留全部来源，参考文本不能遮住活动来源，同级冲突显示为 `ambiguous`；查看方式见[工具指南](../../tools/README.md#索引与部署发布)。历史读取许可与部分依赖调查许可仍然独立。官方缓存核对哈希/XML/登记，不套用手写模组的编码和 Galaxy 风格限制。统一预检默认仍只检查主模组；显式扫描依赖也不会对官方缓存执行手写代码 linter。

## 本机证据范围

SC2 `5.0.17.98370`、构建 `bb10ee62e9cf3678dfa74233d5657757`，引擎 SHA-256 `c68202849f8e64ed20d15bea0fb89f2c5b94028d075d9848e124a8264d130222`。原工具箱 x64 CascLib 可用 ANSI 接口只读访问；错误码 2 不能单独证明客户端损坏。

[引擎证据读取器](../../tools/sc2_engine_dependencies.py) 核对内置链表、配置登记及标准来源收集区间。GameData 表在 raw `0x3b99740`，110 条、24 字节步长；初始化循环明确处理 109 个 XML，之后还有 Assets.txt。标准 XML 登记被逐组件文件来源收集消费，规则绑定整文件、表、注册循环及调用区间的哈希。结合[原作者组件工作流](https://sc2mapster.github.io/mkdocs/setup/#41-basesc2datagamedata)中标准分类文件不需列入附加 GameData.xml 的说明，静态确认标准来源范围。规则不以表顺序推断 XML 字段合并顺序。

标准清单覆盖工具箱 54 类候选遗漏的 Cursor、DSP、Light、SoundMixSnapshot、Soundtrack 和 VoiceOver 等非空表。原始文件不改写，GameData.xml 的自定义空间仍按实际 Includes 递归；缺少引用、路径越界、非空未知 XML、损坏库或错误构建继续失败。官方纯数据组件只有保留的 CASC 枚举、空库登记结果和已确认组件关系共同支持“没有 GUI 注册”时，才免于元数据缺失误报；普通本地目录不能借此跳过登记检查。
