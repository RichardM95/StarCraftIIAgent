# 触发器查询、依赖与案例

本页是 GUI 触发器开发的查询入口。原始定义、官方案例与目标可用性分别保留来源；参考命中不等于目标已经加载。

按需参考：[游戏内对白与对话框的 20 个新案例](trigger-dialogue-examples.md)、[用户与智能体的对话示例](trigger-agent-dialogue-examples.md)。游戏案例现覆盖 11 类机制、27 个精选入口；原七类 GUI 模板的验证范围保持独立。

## 开发流程

1. 确认实际编辑的地图或模组；配置项目使用 `project.source_mode` 指定的源。
2. 运行 `libraries`，确认依赖链完整以及每个库的加载来源。
3. 使用 `find` / `show` 查询目标可用定义，核对参数、预设及子动作。
4. 使用 `examples` 选择兼容案例，迁移其本地变量与对象需求。
5. 编写 GUI，并运行 `check`；最后交由 Editor 和游戏验证。

缺失依赖证据时，使用显式 `--reference` 继续只读研究，补齐证据后再确认可用性。

## 查询工具

`tools/sc2-trigger-query.py` 的通用选项放在子命令之前。源路径是用户指定的外部资料目录，以下占位符不代表活动项目。

```text
python tools/sc2-trigger-query.py build --reference-root "<官方 Mods>" --reference-root "<官方 Campaigns>"
python tools/sc2-trigger-query.py --reference find TriggerAddEvent
python tools/sc2-trigger-query.py --reference show Ntve:FunctionDef:6D565EB4
python tools/sc2-trigger-query.py --reference examples waves --summary
python tools/sc2-trigger-query.py --reference examples dialogs --case dialog-add-button --summary
python tools/sc2-trigger-query.py --reference check --templates
python tools/sc2-trigger-query.py --target "<地图.SC2Map>" --mods-dir "<目标 Mods>" --campaigns-dir "<目标 Campaigns>" libraries
python tools/sc2-trigger-query.py --target "<地图.SC2Map>" --mods-dir "<目标 Mods>" --campaigns-dir "<目标 Campaigns>" check
```

项目已配置时可省略目标和 Mods 路径；Campaigns 使用显式路径或配置的安装目录下 `Campaigns`。非标准布局明确传路径。`show` 接受 `Library:Type:Id`；地图本地库写 `local`。参考定义有多个来源时传 `--source "<索引中的源文件>"`。它也支持精确查询 Param、ParamDef、PresetValue、SubFuncType 等元素。

对白机制使用 `transmissions`、`conversations`、`dialogs`、`cinematics`。`examples --case` 按 case_id 或精确元素 ID 选取案例；不指定时展示该机制全部精选入口。节点上限同时约束本地图的展示，完整兼容性仍使用未截断记录。

输出为 JSON，包括原始 XML、定义的参数顺序、参数默认值、源定位、指纹和兼容性。`name` 保留首选名称，`names` 分别保存 identifier、zhCN、enUS；`find` 匹配全部名称，同一定义只返回一次。`examples` 完整检查引用闭包，默认只保留最多 200 个展示节点及资源值并标记截断；`--max-nodes 0` 展示全部，`--summary` 只累计汇总。展示上限不截断依赖检查。案例分类以 [精选记录](trigger-cases.json) 的人工结构核查为准。

索引使用标准库 SQLite，默认跟随现有项目/参考运行目录，文件名为 `triggers.sqlite`；`--db` 可明确指定。索引检查输入增删、大小和修改时间；`--verify-input-hashes` 补充哈希检查。输入包含依赖声明、库登记、GUI 定义、TriggerStrings、GameStrings 和配套 MapScript。索引过期须重建，不允许旧结果证明当前可用性。

## 两类加载证据

- `ComponentList.SC2Components` 定位的 info 文件声明组件依赖。原始解包组件没有清单时，可以读取确实存在的 `DocumentInfo`，但不能绕过已有且损坏的清单。
- `LibraryList.xml` 登记组件内的库文件。只有组件加载关系得到确认，登记的库才进入目标集合；登记序号不是库的实际 ID。
- `.SC2Lib` / `.TriggerLib` 的 `Standard Id`、`Triggers` 内的 `Library Id` 是定义归属证据。跨库引用按 Library、Type、Id 解析，地图本地引用保留文档作用域。

2026-10-07 对用户提供的 SC2GameData 提取库进行了核对：`challenges`、`frontiers`、`voidprologue`、`alliedcommanders` 保留依赖声明；`core/liberty/swarm/void.sc2mod` 保留库登记和定义，但缺少组件清单及 DocumentInfo/DocumentHeader。已检查的 Liberty、Swarm、Void 的 StandardInfo 没有 Dependencies。这些缺口不证明原游戏没有依赖。

目前工具不会从文件夹名称推断官方依赖关系，也不会自动注入 Core。明确声明且能解析的 Core 提供 Ntve；否则含 Ntve 的目标引用不能通过确认。未解析的网络依赖、缺失元数据/库文件和有歧义的定义都使目标状态成为 `unconfirmed`。

## GUI 结构与迁移

函数定义中的 Parameter 顺序用于展示签名。调用中的 Param 通过 `ParameterDef` 绑定，XML sibling 顺序可以不同。已核对官方 `sc2tutorial` 的 `Terran MakeBarracks CreateObjective`：参数引用排列与 Ntve ObjectiveCreate 的签名顺序不同，但归属对应。检查参数归属、覆盖与重复，不能仅比较顺序。

默认值是定义事实；构造调用仍显式提供每个参数。`SubFunctionType` 必须属于父调用的函数定义。检查会追踪函数体、变量初始值、参数默认值和间接 GUI 引用；默认值模板只检查引用，不把它当作调用者自动执行的代码。Label 分组信息不当作可执行依赖。可变参数以原始 `ParamFlagMultiple` 为准；难度字面值采用官方 `ValueId` 结构。

移植本地片段前，为声明和引用重新分配 ID，并同步 TriggerStrings 与 GameStrings。`tools/sc2_triggers.py` 的纯函数 `remap_local_ids(raw, strings, occupied)` 返回新 XML 和新字符串映射，接受地图本地片段；`occupied` 应包含目标全部已有元素及字符串锚点 ID。导入模组 Library 时还需显式设置归属，不能直接使用地图本地引用。

## 验证范围

定义查询先解析目标已加载的根定义，再检查活动定义的间接引用。参考定义与活动来源的文件指纹不同会报告来源差异，即使 Library/Type/Id 相同也不直接确认兼容。相同指纹的组件副本可匹配，但仍需目标实际加载。只有案例迁移允许精选 `local_graph` 中、已核查的来源地图本地节点；未核查的节点或外部库都必须由目标解析。兼容性输出前重新核对目标输入。

`test-suite.py --scope mod` 和完整验收现已包含 GUI 触发器依赖检查，不依赖参考索引。`--mods-dir`、`--campaigns-dir` 可明确指定依赖根；catalog 的 `--primary-only` / `--exclude-mod` 不裁剪触发器需要的活动依赖。明确没有可检查 GUI 定义时输出 `not_applicable`，元数据不足或登记文件缺失仍失败。地图通过查询工具的显式 `--target` 单独检查。工具与文档范围无需活动项目。

当前触发器索引版本为 2，旧版必须用原来的外部资料根重新执行 `build`。名称索引与单次查询缓存都受输入新鲜度约束，没有长期兼容性缓存。

耗时、Python 分配峰值、解析次数和结果对照见 [查询性能记录](trigger-query-performance.md)。名称能力增加带来的开销如实记录，单次采样不作为稳定性能结论。

参考案例显示 `reference_only`，兼容性检查只确认其库引用闭包。地图对象、Catalog 链接、初始化前提与本地 ID 仍需迁移。涉及 Custom Script 的原始代码不由此工具完成 Galaxy 编译或运行验证。

[七类模板](trigger-templates/README.md) 是 GUI 片段，不是可运行地图。`check --templates` 针对索引中记录的原生源校验结构；同时指定目标时还检查目标库兼容性。它不会声称地图资源或运行行为通过。

工具通过只报告 `static validation passed`。Editor 重载/保存与游戏场景证据分别对应 `Editor accepted` 和 `packaged runtime passed`。

## 编辑器行为的证据范围

工作区此前关于“GUI 调用才能保留模组库”“事件声明必须紧邻 Trigger”的说明没有配套编辑器版本、最小复现文件或保存前后对照，因此目前按保守交接实践执行，不据此断言所有版本的链接器或代码生成器行为。事件的 GUI 结构与精确引用以官方 Triggers/NativeLib 为来源。

后续在独立测试地图中分别比较 GUI action 与等价 Custom Script 调用、相邻与远置事件声明；记录编辑器版本、依赖、输入指纹、保存后 Triggers 和生成代码中的库调用/事件注册，以及游戏内结果。由 [模板验收记录](trigger-templates/acceptance.md) 保存证据；缺少这些证据时规则仍为待验证。
