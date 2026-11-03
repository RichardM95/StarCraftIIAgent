# 按行为编写与改造 GUI 触发器

共享 CLI/MCP 操作 `sc2_trigger_context`、`sc2_trigger_author` 连接[现有生成链](trigger-pipeline.md)与候选事务。作者声明见 [AUTHORS](../../AUTHORS.md)。当前目标为 B98370 Components 独立地图；源码、编辑器、运行验收分别记录。

## 工作流

1. `sc2_project_open(path, writable=true)` 打开明确的工作副本，取得 project_id。
2. `sc2_trigger_context` 读取相关节点、活动定义与区域，保存 fingerprint。引用从结果选择，名称仅用于搜索。
3. 提交行为请求和正反例，先用 `mode=preview`。修复 spec_path 上的错误后，以相同请求调用 `mode=candidate`。
4. 查看 behavior_summary、node_map、impacts、candidate_fingerprint、validation，通过 `sc2_changes_apply` 提交。详细差异保存在 diff_file，需要完整返回时传 include_diff=true。两种模式都验证隔离副本的实际候选字节：GUI 引用检查 → 离线生成 → 真实 Galaxy 静态前端。
5. 编辑器保存、重开并核对官方脚本后记 `Editor accepted`；独立归档显示场景总 PASS 与该构建专属标记后记 `packaged runtime passed`。静态通过只记 `static validation passed`。

CLI 使用 `python tools/sc2-local.py --ui-language zh-CN call <operation> --arguments-file <file>`，外层参数以 `tools` 清单为准。候选提交、源保护与回滚沿用原事务，不直接修改生成的 Galaxy。

## 局部上下文

`sc2_trigger_context` 接收 project_id，另可传 selection=`[Library,Type,Id]`、library、query、topic、depth（0..8）、limit（1..200）、mods_dir。无 selection 时列出本地声明；library 可限定库，空字符串代表地图本地；query 搜索活动定义/预设；选中 FunctionDef 可直接取得参数与分支结构。

返回执行顺序、父引用、分支角色、作用域、分类路径、禁用状态、变量类型、参数槽、字面量/预设/资源表达式、字符串锚点、直接引用者、区域、输入指纹。全局变量被某触发器使用，不会因此被标成该触发器的局部变量。定义直接返回精确参数槽、GUI 类型、预设 BaseType、返回类型、默认参数来源与子动作角色。案例 topic 取[案例库](../reference/trigger-knowledge.md)的机制名，移植时重新绑定资源与依赖。

展示截断不影响完整引用检查。fingerprint 覆盖 GUI、活动依赖、受控脚本、场景对象/区域及字符串；源或依赖变化后重新查询。不能根据已截断的展示结果判断“无人引用”。

## 请求规范 v1

顶层必需 version=1、稳定的 request_id、expected_fingerprint。可选 library（默认地图本地）、locale（默认 zhCN）、declarations、triggers、edits、acceptance。目标库必须存在，跨库迁移另行设计。

声明通过请求内唯一 key 互相引用，工具分配内部 ID。key 用 ASCII 标识符，name 用于编辑器显示。声明 kind 支持 category、variable、action、function。

| 声明 | 字段 |
|---|---|
| category | key、name，可选 category 父分类 |
| variable | key、type，可选 initial、category |
| action | key、parameters、locals、actions，可选 category |
| function | 同 action，另需 returns |

参数/局部声明有 key、type，局部可有 initial。type 是 GUI 类型名或 `{"preset":[Library,"Preset",Id]}`，按 TypeElement → BaseType 解释。GUI 句柄保留语义类型；底层映射为 int 并不允许把任意整数当作 objective。

触发器字段为 key、name、category、events、conditions、actions、locals、disabled。列表顺序就是执行顺序；conditions 为“且”。

| 行为 | JSON 形状 |
|---|---|
| 调用 | `{"call":精确定义引用,"arguments":参数字典或槽/值列表}` |
| 赋值 | `{"set":变量key或引用,"value":表达式}` |
| 分支 | `{"if":条件或条件列表,"then":[动作],"else":[动作]}` |
| 循环 | `{"while":条件或条件列表,"actions":[动作]}` |
| 返回 | `{"return":表达式}`，仅返回值函数 |

调用另可带 branches=`{官方角色名:[行为]}`、disabled。角色取自上下文。事件只能写在 events 中。省略实参仅在官方槽确有 Default 时复制默认树；每个调用与参数实例分别分配 ID，不共享可变实例。

表达式支持 JSON 原生布尔/整数/小数/字符串，以及：

```json
{"var":"evacObjective"}
{"parameter":"input"}
{"preset":["Ntve","PresetValue","00000559"]}
{"compare":"==","left":{"var":"evacCompleted"},"right":false}
{"arithmetic":"+","left":{"var":"count"},"right":1}
{"region":"EvacZone"}
{"literal":"玩家文字","type":"text"}
{"literal":"Marine","type":"gamelink","game_type":"Unit"}
```

这些行分别是独立表达式。比较支持 ==、!=、<、>、<=、>=，算术支持 +、-、*、/、%，运算符按官方预设绑定。调用可以嵌套。文本自动维护 GameStrings 锚点；游戏链接的 catalog 类型需与槽定义一致。命名区域必须唯一存在，写入官方 ValueType=region + ValueId 形状，生成 RegionFromId(id)。

arguments 字典键必须唯一匹配实际槽名称；同名时用 `[{"slot":[Library,"ParamDef",Id],"value":表达式}]`。AI 选择定义与槽，不分配 FunctionCall、Param 或声明的内部 ID。

## 例一：新建撤离功能

查询初始化事件、区域事件、触发单位、单位所属玩家、目标创建/最后创建目标/目标状态设置，以及对应预设。按本次结果绑定精确引用；完整可执行示例见[验收脚本](../../integrations/sc2-editor-mcp/tests/acceptance/gui_author.py)。

初始化创建目标后立即保存句柄到 evacObjective。区域事件指定实际 EvacZone，条件为 `UnitGetOwner(EventUnit()) == 1` 且 evacCompleted 为假。动作先赋值 evacCompleted=true，再用保存的句柄完成目标。不要在进入事件中再次查询最后创建目标。

请求片段（call 引用需从本次上下文选择）：

```json
{
  "key":"EvacFirstEntry",
  "events":[{"call":["Ntve","FunctionDef","00000041"],"arguments":{
    "u":{"preset":["Ntve","PresetValue","C84C7A78"]},
    "r":{"region":"EvacZone"},"state":{"preset":["Ntve","PresetValue","00000145"]}
  }}],
  "conditions":[
    {"compare":"==","left":{"call":["Ntve","FunctionDef","00000081"],"arguments":{
      "u":{"call":["Ntve","FunctionDef","00000092"]}}},"right":1},
    {"compare":"==","left":{"var":"evacCompleted"},"right":false}
  ],
  "actions":[
    {"set":"evacCompleted","value":true},
    {"call":["Ntve","FunctionDef","00000440"],"arguments":{
      "objective":{"var":"evacObjective"},"state":{"preset":["Ntve","PresetValue","00000559"]}}}
  ]
}
```

## 例二：改造旧分支并修复类型错误

先查询旧触发器，展开成功分支，保存父节点、角色和 fingerprint。提交 replace_branch，只替换选中 then。若把 unit 变量误传给 ObjectiveSetState.objective，preview 应定位到 `edits[0].behaviors[1].arguments.objective`，返回 expected=objective、actual=unit。将它换成已保存的目标变量引用，使用新 request_id 重试，再重排动作并移动分类。

| edits.op | 字段与边界 |
|---|---|
| insert | parent、role、behaviors、可选 index；index 相对该角色的列表，默认追加，0 表示首项前 |
| replace_branch | parent、role、behaviors；空列表清空该分支 |
| replace | target 为调用时传 behavior，为参数实例时传 expression；保留实例 ID/分支角色 |
| reorder | parent、role、order；必须完整包含该角色的现有节点且各一次 |
| move | target、parent、role、可选 index；同库跨分类只移动触发器，调用跨函数移动检查局部作用域 |
| delete | target；存在外部引用则阻断，非空分类不能删除 |

触发器角色为 events、conditions、actions；分类为 items；函数体为 actions；控制流用实际子动作角色。Root 引用为 `[Library,"Root",""]`。删除分支只回收其独占实例，外部引用不受展示截断影响。未知 XML 不在选中范围内时保留；无法解释被改写实例时阻断。

改造时始终按完整 `Library/Type/Id` 匹配归属，不同库可使用相同 ID。替换事件或条件会继承其原角色；函数定义只接受 actions。替换参数时，类型从实际参数槽、sameas 对应实参、函数返回类型或变量声明推导。跨函数移动也核对目标返回类型。未使用的局部变量可以删除；有实际读写引用时仍阻断。

insert、replace_branch 必须显式提供 behaviors，reorder 必须提供 order；只有显式 `behaviors=[]` 才表示清空分支。各操作拒绝无关字段，index 必须为整数，布尔值不作索引。replace 调用使用 behavior，replace 参数使用 expression，错误定位到对应请求字段。

替换保留原实例 ID，文本参数沿用该 ID 的 GameStrings 锚点。node_map 和 instances 只返回最终候选中仍存在的节点；同一请求先新建再替换的临时实例不留在映射中。无需新增实例的纯文本替换也可生成候选，不会虚报新增 ID 数。

同一请求中已删除的新建文本实例，不再输出其临时锚点；源文件中原有的未知或未使用锚点仍保留。

参数改造会复核同一调用的关联参数。比如同时把赋值目标从 bool 变量换成 int 变量、把值改成 42，两项替换可以按任一顺序提交；sameas 约束按整批修改后的实参检查。只改目标而保留不兼容的旧值时，诊断定位到引发变化的请求字段。game_type 目录约束在参数替换后仍生效，动作不能替换值表达式；已被本次请求删除的声明也不能再从旧源快照解析。

## 并发、回滚与验收

相同输入与 request_id 生成稳定候选和 ID 映射。同一 candidate 请求重试返回原事务，已应用时返回应用事务；request_id 携带不同内容会被拒绝。回滚使用应用事务 ID，回滚后重新创作使用新 request_id。候选篡改、编辑器保存或依赖变化会阻止旧候选提交。

候选摘要保留行为请求中的 acceptance，给出新增/修改节点与技术影响；详细 XML/文本差异按需读取。efficiency 记录行为输入体积、低层操作体积、工具分配 ID 数；工具调用数需在同一实际流程中测量，不能将清单覆盖数当作调用成功数。

impacts 提供源码推导的可读对照：新建声明和触发器给出 parent、变量 type/initial、事件/条件/动作等 roles；改造给出 before/after 节点摘要、role 和 id_policy。移动另给出 from_parent/to_parent。摘要中保留函数、实参、变量名与精确引用，便于审阅新增玩家条件、动作先后关系和分类变化；它不自动判断玩法是否符合需求。

每组摘要最多展示 40 个节点，count 或 before_count/after_count 保留完整数量，truncated 标记展示截断；单节点也有 summary_truncated。展示摘要不能替代完整差异、引用检查和候选静态验证。

node_map 使用原请求路径，赋值、if、while 等简写不会把诊断暴露为工具内部的参数槽路径。同一个嵌套表达式可能产生 Param 和 FunctionCall 两个实例：node_map 返回主要节点，instances 列出全部实例；allocated_internal_ids 统计实际新增实例，包含声明。

撤离验收依次让非玩家1进入、玩家1进入、离开后再进入，完成计数必须为 **0、1、1**，且初始化保存的目标完成、之后创建的干扰目标仍活动。分别保留官方生成脚本对照、归档哈希、GUI_EVAC_ALL_PASS 和本次 GUI_OFFLINE_EXEC_* 运行证据。此前通过的独立地图仅作为基线，不升级本次新副本的状态。

## B98370 独立验收范围

2026-11-02，用户确认新建场景的编辑器保存/重开测试和独立离线归档均通过。截图同时显示两种单位所属玩家检查、计数 0/1/1、保存句柄检查、干扰目标仍活动、总 PASS 和专属标记 GUI_OFFLINE_EXEC_548600028d8a。[新建验收记录](../../integrations/sc2-editor-mcp/tests/fixtures/trigger-pipeline/editor-98370-author.json)保存官方/离线脚本、输入与资源指纹、归档及截图哈希，状态为 `Editor accepted` 和 `packaged runtime passed`。

旧逻辑修复副本 GuiEvacRepair.SC2Map 也已由用户确认编辑器版和离线版均通过，状态为 `Editor accepted` 和 `packaged runtime passed`。其离线专属标记为 GUI_OFFLINE_EXEC_d59468099bdf，归档 SHA-256 为 3e21ef83e047e4e9535dafa7c0afe60dcb956d5b74af789feb99836f3b44ca63。[修复验收记录](../../integrations/sc2-editor-mcp/tests/fixtures/trigger-pipeline/editor-98370-author-repair.json)区分用户实机反馈与工具抓取的编辑器文件；当前作者实现重放原请求的候选指纹与被测候选一致。官方保存脚本与离线脚本已核对玩家条件、一次性标志、保存的目标句柄、动作顺序和区域事件注册；编辑器保存后动作 ID 和 Reviewed 分类归属保持正确。

首个离线归档的地图头还引用原战役依赖，虽 XML 声明已替换，游戏仍在加载阶段拒绝。准备流程现用已验证 H2CS8 编解码器同步地图头；打包器拒绝 DocumentInfo/DocumentHeader 不一致的地图。原始失败归档保留为对照。官方保存脚本还确认任意单位的区域注册直接传 null，具体单位表达式才使用 UnitRefFromUnit 转换。

效率通过同一撤离请求的自动化共享操作流程测量，起点均为已打开的隔离项目，终点均为源码应用与静态验证完成；它不等同于 AI 对话中的实际调用量。长驻 MCP 进程需重启才能加载新增操作，CLI 与新建 MCP 服务均使用相同 Python 实现。

| 同一撤离需求 | 高层行为接口 | 等效低层操作 |
|---|---:|---:|
| 共享操作调用次数 | 3 | 5 |
| JSON 输入字节数 | 11,022 | 116,250 |
| 调用方显式填写的新增内部 ID | 0 | 288 |

上述输入体积减少约 90.5%；定义和参数槽仍需从当前项目上下文选择精确引用。完整指标保存在验收记录的 efficiency 字段。
