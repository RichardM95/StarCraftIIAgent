# GUI 写入与离线 Galaxy 工具链

作者：扯蛋虾米。

共享 CLI/MCP 新增 `sc2_trigger_write`、`sc2_trigger_generate`、`sc2_galaxy_check`、`sc2_trigger_package`。
使用 [共享工具](shared-tools.md) 的项目打开、候选审阅及提交入口。
已有项目源和生成 Galaxy 的保护规则仍适用。

## 安装

需要 Node 22+ 和 pnpm。首次安装下载锁定的依赖；此后生成和检查无需网络。

```powershell
python tools/sc2-galaxy-frontend.py --node "<node.exe>" --pnpm "<pnpm.cmd>"
```

工具将本机 Node 位置保存在忽略的 `.runtime/galaxy-frontend.json`。
`SC2_GALAXY_NODE` 可覆盖此选择。依赖已缓存时安装可加 `--offline`。
前端来源及固定提交见 [来源说明](../../integrations/galaxy-frontend/UPSTREAM.md)。

## 接口

所有参数的当前 schema 从 `python tools/sc2-local.py --ui-language zh-CN tools --operation <操作>` 查询。
通过 `call <操作> --arguments-file <JSON文件>` 调用；MCP 使用同一业务函数。

- `sc2_trigger_write(project_id, operations, expected_sha256?, locale="zhCN", mods_dir?)`：返回事务候选；通过 `sc2_changes_inspect/apply` 审阅及提交。
- `sc2_trigger_generate(project_id, mods_dir?, runtime_probe=false)`：生成隔离构建，返回 `build_id`、manifest 路径与覆盖状态；运行验收时启用 runtime_probe，加入本次构建专属消息标记。
- `sc2_galaxy_check(project_id, build_id?, entry?, mods_dir?)`：build_id 与项目相对 Galaxy entry 二选一；核对输入指纹和文件清单，运行解析、符号绑定和类型检查，构建诊断附 GUI 来源定位。
- `sc2_trigger_package(project_id, build_id, installation?)`：静态检查带运行标记的构建，自动装入全新 MPQ，回读验证全部成员；可生成官方启动器命令，不启动游戏。要求明确的 Components 地图外壳。

写入仅支持已存在且登记的 `Triggers`。`operations` 是 upsert 列表，每项使用
`type`、八位十六进制 `id`、可选 `library`、`name`、`owner`、`index` 和 `children`。
可选 `strings` 是玩家文本锚点到内容的映射，同步写入所选 locale 的 GameStrings。
`owner` 以 `type/id` 指定当前库中的声明容器；调用与参数通过所属节点的 children 引用。
`children` 每项使用 `tag`、`attributes`、`text`、递归 `children` 表达实际 XML 节点。
参数绑定必须使用真实 `ParameterDef` ID；不能以显示名称代替引用。

```json
{
  "project_id": "<已打开项目ID>",
  "expected_sha256": "<Triggers SHA-256>",
  "operations": [{
    "type": "Category", "id": "AC010001", "name": "Mission Logic",
    "children": []
  }]
}
```

分类、触发器、函数、全局变量默认登记到所在库的 Root；局部变量、函数参数需要指定 owner。
`index` 是 owner XML 子节点中的插入位置。重复 upsert 相同内容不产生差异。
节点重归属需显式维护原 owner，不隐式删除其他登记；依赖检查拒绝冲突结构。

## 支持范围与失败边界

支持标量变量、GUI 自定义动作/函数、显式参数、常见字面值与已解析预设、原生调用、
Custom Script、初始化事件、条件、跨库函数、IfThenElse、While、RepeatForever、And/Or、
SetVariable、Return、Comparison 与基本算术。控制流依据来源样例识别，不执行任意模板。
未知控制流、数组/结构体、未支持的字面值、RunOnMapInit 调度和未知可执行字段明确失败。
官方 `FlagNative` 的声明本身不能证明引擎提供对应函数；静态前端还需解析真实 Galaxy 声明。

依赖必须完整。按实际加载声明选择定义；参考摘录不证明游戏内加载。
未修改节点字节保留；修改 owner 排序时该 owner 的 XML 会重新序列化。
不自动删除未知节点。写入不会将未知逻辑转换成 Custom Script。

生成产物位于项目运行目录的 `galaxy-builds/<build_id>/`，含生成源码、输入指纹、
受控虚拟脚本集合、GUI 来源映射和检查结果。源变化或新增脚本要求重新构建。
生成成功只表示受支持闭包已转换；必须另行运行检查。

原生调用按精确 GUI 定义引用绑定当前受控脚本中的声明。仅当前入口的递归 include 范围可提供绑定，
缺失、歧义、参数顺序或类型不匹配会返回函数名、声明候选、实际参数和 GUI 调用位置。
声明索引按脚本内容缓存，输入变化后重建。`mapping_inventory` 记录声明数量、活动文件、
有一致声明依据的类型别名及未解析定义，`used_mappings` 单独记录本次调用使用的映射、来源哈希和兼容模板。
未使用的缺口保留在清单中，不阻断其他调用。

预设声明沿 `TypeElement` 解析 `BaseType`，可用于全局/局部变量、函数参数和返回值。
事件注册显式传入所属触发器句柄，`ParamFlagReference` 的 unit 参数按实际声明转换为 unitref。
动作语句可丢弃原生返回值，表达式要求返回类型一致。带 GUI 函数体的原生兼容定义优先展开，
按精确参数引用替换，并复用常量及嵌套调用生成；尚未解释的模板字段明确阻断。

[类型与兼容调用验收脚本](../../integrations/sc2-editor-mcp/tests/acceptance/binding_correctness.py)
从已验收地图创建新副本，加入布尔预设事件条件、参数/返回/局部变量及旧版 PowerLevel 对照。
运行断言标记为 `GUI_MATRIX_PRESET_PASS`、`GUI_MATRIX_POWER_COMPAT_PASS` 和 `GUI_BINDING_ALL_PASS`，
离线测试还需核对本次构建的专属标记。本机 B98370 场景已达到 `Editor accepted` 和
`packaged runtime passed`，官方保存脚本与离线输出的 bool 类型、函数签名、事件条件和
`PowerLevel(1, Point(0, 0), "PowerSource")` 参数顺序已核对。
用户分别运行编辑器版本与独立离线归档，后者同时显示总 PASS 和 `GUI_OFFLINE_EXEC_f80b51534ef5`。
[官方保存样例与验收证据](../../integrations/sc2-editor-mcp/tests/fixtures/trigger-pipeline/editor-98370-binding.json)
保留迁移前 XML、双方脚本、输入/归档/截图哈希及来源。
unitref 转换和 control 别名当前具备静态回归证据，尚未加入本次游戏场景。

当前构建已登记的官方 CASC GUI 库复用配套 Galaxy，并按组件加载顺序初始化，
不把整套官方 GUI 定义当作项目手写逻辑重编。对六个已知官方头文件缺口，
仅从活动 NativeLib 的 FlagNative 定义补充静态类型上下文，记录源哈希和节点，不将声明装入运行包；
DataTableInstance 的 int 表示以同构建官方生成包装函数为依据。
这类签名证据仍不代替编辑器和运行验收。

## 验收证据

测试数据包含固定上游提交的 NativeLib 参考摘录与来源哈希。
这些摘录验证 XML 绑定与代码形状，本身不代表编辑器或运行验收。
专项测试覆盖写入保留/幂等、依赖失败、初始化生成、跨库返回值、真实前端错误与过期构建。

2026-11-02，用户在独立 GuiPipeline.SC2Map 完成 GUI 检查、Components 保存和 Ctrl+F9 测试，
并回复“一切正常”，确认显示 `GUI_PIPELINE_PASS_20261102`。
保存后的 XML 与 Galaxy 已只读核对：赋值 7、显示消息和初始化事件注册均保留。
本场景达到 `Editor accepted` 和 `packaged runtime passed`；运行观察来自用户反馈，
不是智能体直接观察。客户端日志对应 Base98370。
来源哈希、保存后的 XML/Galaxy 与适用范围见
[本机编辑器冒烟样例](../../integrations/sc2-editor-mcp/tests/fixtures/trigger-pipeline/editor-98370-smoke.json)。

编辑器保存时会省略文本 Param 的 Value，使用节点 ID 对应的 Param/Value 锚点；
生成器已支持此读回形式。离线与官方输出的本场景动作、参数和事件注册相同，
但离线构建保守保留 Liberty 库初始化，编辑器会裁剪本例未用库，尚不宣称库裁剪完全一致。
此处基础冒烟证据来自编辑器生成地图；离线直接运行的独立验收见文末。
复杂场景的验收范围见下方进阶矩阵；不随基础冒烟场景自动升级。
REA 未安装；只有出现无法解释的具体差异时再考虑定向逆向。

## 进阶验收地图

使用 [矩阵生成脚本](../../integrations/sc2-editor-mcp/tests/acceptance/gui_matrix.py)
从已经保存的独立 Components 地图外壳建立新副本；目标目录必须不存在且位于工作区。
它只编写 GUI XML 和字符串，不修改复制的生成 Galaxy，也不启动编辑器或游戏。

```text
python integrations/sc2-editor-mcp/tests/acceptance/gui_matrix.py --source "<已保存的地图.SC2Map>" --destination "<新目录/GuiMatrix.SC2Map>"
```

测试有限 While 循环、真假分支、禁用动作、自定义函数参数/回传/局部变量，以及同图 Library 的 GUI action。
计数器循环到 3，禁用动作不得改值；分支结果为 12，函数结果为 24，跨库结果为 29。
每项输出 GUI_MATRIX_<项目>_PASS/FAIL；所有条件都通过才输出 `GUI_MATRIX_ALL_PASS`。
跨库范围仅限同图 Library，不证明独立 Mod 部署、导出和链接通过。

矩阵 v1 的官方编辑器编译在跨库调用行失败，尚未达到 `Editor accepted`。
检查发现两处与已保存样例不同的布局：Library 位于地图 Root 之后，且库内 Root/Item 省略 Library 属性。
v2 按[已保存样例布局](../../integrations/sc2-editor-mcp/tests/fixtures/trigger-pipeline/embedded-library-shape.json)修正，
写入器补充显式归属并保持声明顺序；生成及候选入口对旧形状明确拒绝，避免仅由离线生成器接受而误报兼容。
v2 随后完成用户保存、编译和游戏测试，截图显示 LOOP、DISABLED、BRANCH、FUNCTION、CROSSLIB、ALL 六项 PASS。
保存后的代码已核对：跨库声明、函数定义、初始化和调用均存在，禁用赋值未生成。
本矩阵场景达到 `Editor accepted` 和 `packaged runtime passed`，证据与源哈希见
[本机编辑器进阶样例](../../integrations/sc2-editor-mcp/tests/fixtures/trigger-pipeline/editor-98370-matrix.json)。
两项布局修正是组合验收，尚未隔离各自因果，不据此断言所有版本的解析器或链接器行为。
独立 Mod 链接及离线产物的直接运行见下节；库裁剪等价性仍未确认。

在编辑器打开新副本并保存 Components，再 Ctrl+F9 测试。
只有取得实际保存与游戏反馈后才升级该场景的验收状态；离线编译成功仍只报告 `static validation passed`。

## 独立 Mod 链接验收

[拆分脚本](../../integrations/sc2-editor-mcp/tests/acceptance/mod_link.py)从已保存的矩阵地图建立新的
CodexGuiLinkAcceptance.SC2Mod 和 GuiModLink.SC2Map。测试 Library 使用 AC040001，地图通过
`file:Mods/CodexGuiLinkAcceptance.SC2Mod` 引用该 Mod，调用 GUI action 后检查共享变量为 29。
成功总标记为 `GUI_MODLINK_ALL_PASS`，失败为 `GUI_MODLINK_ALL_FAIL`。

脚本必须通过 `--mod-template` 提供编辑器实际保存过的专用 Components Mod 外壳。
它核对 DocumentHeader、组件登记、DocumentInfo/Triggers/GameText 版本旁车及已登记文本目录，
缺少原生文件时在创建候选前拒绝继续。通过检查不等于 Editor 接受，二进制内容不由工具重建。
复制后逐字节保留原生外壳与依赖登记，只接入本次 GUI 逻辑和文本。
`--mod-name` 可以为新的测试版本指定独立文件名，地图依赖随之同步。

脚本只创建工作区暂存副本，实际部署使用 deploy-mod.py 的显式源与目标，先 dry-run 再部署。
本轮测试部署目录存在时停止，避免覆盖已有用户 Mod。后续编辑器保存以部署的独立测试 Mod 为验收源，
不要用旧暂存副本覆盖其生成输出；主项目配置不随独立测试切换。

先在编辑器打开部署的测试 Mod，保存 Components，重新生成库。
关闭 Mod 后再打开 GuiModLink.SC2Map，保存并 Ctrl+F9 测试。
测试 Mod 不复用地图的二进制 DocumentHeader，也不预写生成 Galaxy。
首版纯 XML 外壳曾出现 GameText、DocumentInfo、Triggers 加载警告；“先打开再由编辑器补齐外壳”的假设未获接受，
因此改为显式要求原生 Mod 模板。各警告的独立内部成因尚未隔离，不把缺少文件的观察扩大为完整根因证明。
使用用户在本机构建并保存的原生 CodexGuiLinkShell.SC2Mod 后，测试已部署为
CodexGuiLinkAcceptanceV2.SC2Mod。2026-11-02 的用户游戏截图显示
`GUI_MODLINK_CALL_PASS`、`GUI_MODLINK_ALL_PASS` 及此前四项 PASS，
本次地图到独立 Mod 的单个 GUI action 和共享变量场景达到 `Editor accepted`、`packaged runtime passed`。
地图保存代码已核对 include LibAC040001、InitLib、AddFiveAndStore 调用及结果 29，
且地图本身没有该导出函数的定义。
源码哈希、输入 XML、地图生成脚本和证据范围见
[独立 Mod 链接样例](../../integrations/sc2-editor-mcp/tests/fixtures/trigger-pipeline/editor-98370-modlink.json)。
Mod 生成库原文件直接读取返回 Win32 5（访问被拒绝），不是 Win32 32（共享冲突）；原因仍未确认，未修改其权限。
用户随后复制两个生成文件到工作区，现已收录函数体、头文件、大小和 SHA-256 快照。
头文件声明共享 int 与单 int 参数动作，函数体执行 `CrossLibraryResult = Input + 5`；
官方 InitLib 有重复调用保护，先初始化外部库再初始化本库变量。本例无显式变量初值或库触发器。
快照来源是用户复制，未能独立读取原文件哈希；不据此声称原路径读取故障已经消除。
此处编辑器生成地图的运行验收不扩大为全部导出形式或版本兼容性；离线产物证据单独记录如下。

## 离线产物直接运行

生成流程从 Triggers 重建自定义库，收集手写脚本和有来源的官方脚本，跳过项目中的
MapScript.galaxy、LibXXXXXXXX.galaxy 及其 `_h` 输出；因此无需读取受限的自定义库编译文件。
显式 `sc2_galaxy_check(entry=...)` 仍检查指定源码，不绕过读取失败。

在 `sc2_trigger_generate` 传 `runtime_probe=true`，再调用 `sc2_trigger_package`。
构建会加入 `GUI_OFFLINE_EXEC_<本次令牌>` 初始化消息；标记仅存在于生成代码，不存在于 GUI XML。
打包器把通过检查的入口原字节写到新运行目录 `galaxy-runtime/<id>/assembly/MapScript.galaxy`，
仅装入运行所需的私有文件，通过已有真实 MPQ 后端创建新归档并回读全部成员哈希。
这是自动编译产物，原项目生成文件始终不写入；打包前后核对 GUI、依赖和脚本清单。
自定义 Mod 库在该入口中展开，测试覆盖其 GUI 定义重新生成后的调用与共享变量行为，
不将它描述成对编辑器库文件装载机制的完整复刻。

提供 installation 时返回 `RunOfflineTest.cmd`，按安装产品和构建规划官方启动器命令。
关闭旧测试游戏后直接运行该命令；不要先用编辑器保存或 Ctrl+F9，否则会重新生成脚本，失去本次离线证明。
需同时看到场景的总 PASS 和本次 `GUI_OFFLINE_EXEC_...`；只有普通 PASS 不能证明离线代码执行。
归档生成、回读及编译成功仍为 `static validation passed`。实际游戏结果到达后才能将该离线场景记为
`packaged runtime passed`；不额外授予该产物 `Editor accepted`。

GUI 元数据补出的六项原生签名仅供静态类型上下文使用：manifest 的 `compile_only_files`
列出这些文件；前端通过临时检查入口组合它们与原始生成入口，仍检查真实语法、符号和类型并保留 GUI 行号映射。
这些声明不进入运行入口或 MPQ，结果明确返回 `engine_abi_verified=false`。
旧版将这些声明装入运行包，在 B98370 被引擎以 UnitSetInfoButtonTooltip 原型不匹配拒绝；
该旧构建禁止重新打包，必须重新生成。GUI 定义的类型不能代替引擎原生接口验证。

2026-11-02，用户通过独立启动器直接运行修正版归档，截图同时显示六项场景 PASS 和
`GUI_OFFLINE_EXEC_69d74dc20471`。归档 19 个成员全部回读校验，入口与离线生成输出哈希一致，
原地图成员指纹复核未变。该独立场景达到 `packaged runtime passed`，
[离线运行证据](../../integrations/sc2-editor-mcp/tests/fixtures/trigger-pipeline/offline-98370-modlink.json)
收录构建、归档/入口/截图哈希、前端版本、输入清单、失败对照和验收范围。
此结论覆盖本例循环、禁用动作、分支、局部变量、函数返回值和重新生成的 Mod 动作/共享变量；
不证明所有原生接口兼容，也不证明对编辑器库裁剪或加载机制的完整复刻。
