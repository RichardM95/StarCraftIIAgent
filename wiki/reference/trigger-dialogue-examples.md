# 游戏内对白、Conversation 与对话框案例

这是 [触发器知识入口](trigger-knowledge.md) 的按需参考。先区分三个对象：Transmission 是任务中的语音/头像/字幕消息；Conversation data 是含角色、台词与摄像机绑定的剧情数据；Dialog 是交互控件。名字含 Conversation 的触发器不一定调用 Conversation 系统。

新增 20 个精选官方案例，连同原有七类共 27 个案例。来源定位、文件指纹、本地调用图、变量、资源引用与完整引用闭包统计保存在 [案例记录](trigger-cases.json)。以下说明来自根事件/动作和可达 GUI 调用的核查，不把名称命中当作机制证明。官方原例并非可直接移植的最小模板；当前七类模板的静态状态不延伸到这些新案例，也没有新的 Editor/游戏验收证据。

## 查询方式

```text
python tools/sc2-trigger-query.py --reference examples transmissions --summary
python tools/sc2-trigger-query.py --reference examples conversations --case conversation-data --summary
python tools/sc2-trigger-query.py --reference examples dialogs --case dialog-add-button --max-nodes 50
python tools/sc2-trigger-query.py --reference examples cinematics --case cinematic-skip-key --summary
```

`--case` 接受下表 case_id 或元素 ID；不指定则返回该机制所有精选案例。未命中明确报错。默认最多展示 200 个闭包节点、200 项资源及 200 个本地图节点，完整检查不受展示上限影响；`--max-nodes 0` 展示全部。复杂剧情建议先看摘要，再按精确引用查看调用。

检查目标兼容性时，在上述命令中加入 `--target "<目标.SC2Map>" --mods-dir "<Mods>" --campaigns-dir "<Campaigns>"`，放在子命令之前。显式 `--reference` 保留不兼容原因；它不赋予目标任何库。库集合以当前目标解析结果为准。

以下表中的来源为外部 Campaigns 根的相对组件定位：

| 简写 | 组件位置 |
|---|---|
| H | `liberty.sc2campaign/base.sc2maps/maps/campaign/thanson02.sc2map` |
| V | `liberty.sc2campaign/base.sc2maps/maps/campaign/tvalerian02a.sc2map` |
| S | `liberty.sc2campaign/base.sc2maps/maps/campaign/tstory01.sc2map` |
| A | `liberty.sc2campaign/base.sc2maps/maps/campaign/tarcade.sc2map` |
| Z | `swarm.sc2campaign/base.sc2maps/maps/campaign/swarm/zstorychar.sc2map` |

每个入口位于该组件的 Triggers，Library 为空。函数、参数和资源的间接来源另由查询显示。表中“闭包库”只是参考所需集合，不能证明目标已经加载。

## Transmission：语音、头像、字幕与队列

| case_id | 来源 / Type / Id | 已核查行为 | 迁移重点 |
|---|---|---|---|
| queued-line | H / Trigger / FEB457C3 | ActionQueueAdd 排队，经 Camp 音量包装与 Lbty 提示音发送战役 Transmission | 收件玩家、队列、声音、字幕和头像；闭包需要 Camp/Lbty/Ntve |
| damage-alert | H / Trigger / 651BD0DC | 单位受伤事件、条件和状态变量筛选敌人介绍，再排队发送对白 | 换单位类型与状态条件，检查重复触发与相关提示；Camp/Lbty/Ntve |
| day-night-warning | H / Trigger / 54EBCB95 | 根据任务状态分支选择昼夜预警对白并入队 | 警告的调用时机、昼夜状态、两分支资源；名称里的 30 秒不等于本触发器自带计时事件 |
| stop-dialogue | S / FunctionDef / 6747CDBF | TransmissionClearAll、ConversationDataStop，并向游戏区域发送 actor 消息 | “全部清除”的影响范围、Conversation ID、actor 重置和后续状态；不要只复制停止音频 |
| portrait-create | S / FunctionDef / 3D41585C | 由参数创建 briefing portrait，设置屏幕外行为、保存并返回句柄 | 模型、玩家、布局、缓存规则与销毁时机；它本身不发送台词 |

前三例使用战役封装，不能把它们说成只有 Ntve 的简单对白。只需要单句时，先查询目标的发送原语，再选择目标实际支持的声音/头像/文字输入；不要为迁移方便伪造 Camp 或 Lbty 定义。

## Conversation：连续对白、角色绑定与镜头

| case_id | 来源 / Type / Id | 已核查行为 | 迁移重点 |
|---|---|---|---|
| sequential-lines | V / Trigger / B7578668 | 区域进入与条件控制多条排队 Transmission；使用 TransmissionWait 和 TransmissionLastSent | InitOff 的启用入口、区域、声音次序、玩家和队列；这是 Transmission 串联，非 ConversationDataRun |
| character-callbacks | Z / Trigger / D0BDE235 | 通过 Swarm story utility 登记角色的 pre/post/camera 回调 | 角色标识、回调函数、剧情状态与镜头；闭包还需要 281DEC45、SwaC、Ntve |
| conversation-data | S / Trigger / 531F9080 | 在可跳过段落中登记角色单位及摄像机，运行 Conversation data | Conversation Catalog 条目、地图角色单位、相机映射、入口与清理；只确认 Ntve 不会补齐剧情资源 |
| conversation-camera | S / FunctionDef / 9A3FDB96 | 按当前台词、声音时长和房间/角色辅助函数选择镜头 | 相机模型、实际 Camera ID、当前 Conversation 上下文与角色状态；不是通用随机镜头模板 |

多句对白应保存自己的 Transmission/Conversation 上下文。涉及等待时，在等待前保存事件单位、玩家与句柄；避免后续事件或其他对白覆盖 LastSent/LastCreated。音频长度、字幕时长、等待模式和可跳过行为分别核对定义与游戏结果。

## Dialog：创建、控件、点击、布局与文字效果

| case_id | 来源 / Type / Id | 已核查行为 | 迁移重点 |
|---|---|---|---|
| dialog-create | S / FunctionDef / DD616E37 | 创建前判断既有窗口，保存 DialogLastCreated，通过辅助函数添加按钮 | 对话框变量、按钮数组、文字、玩家、布局；官方调试 UI，仅提取对象管理模式 |
| dialog-add-button | S / FunctionDef / A13A2608 | DialogControlCreate 后设置文字与大小 | 父 dialog、文本及大小；调用者紧接着保存 LastCreated 控件，它不是返回句柄的函数 |
| dialog-button-response | S / Trigger / 95B3EC65 | DialogControl 事件，比较 EventDialogControl 与已保存的相机按钮句柄并分支 | 保存控件、事件玩家和分支映射；替换相机调试行为，不能原样带入剧情选择 |
| dialog-hide | S / FunctionDef / E083003A | 隐藏既有 room-cheat dialog | 玩家可见性和再次打开策略；隐藏不等于销毁 |
| dialog-close-event | S / Trigger / D33A6E05 | 筛选关闭按钮事件，隐藏 briefing dialog，恢复外围剧情 UI 状态 | 按钮、dialog、玩家及清理动作；它来自官方调试入口 |
| dialog-layout-update | S / FunctionDef / 8F17FF90 | 更新按钮位置/状态，以及 dialog 位置和尺寸 | 实际布局变量、锚点、偏移、控件和玩家；不保留调试摄像机假设 |
| dialog-typewriter | A / FunctionDef / C8BD04E5 | Camp 网格包装创建控件，配置文字逐字显示、时长、样式与透明度，管理显示/销毁 | 文字、样式、时长、句柄及玩家；闭包需要 Camp/Ntve |

交互选择的最小编排是：创建窗口 → 创建并保存各按钮 → 显示给指定玩家 → 控件事件按保存的句柄过滤 → 保存事件玩家 → 执行分支 → 隐藏或销毁并清理状态。普通点击事件与“选择结果已同步”的业务状态分别检查；原例是单人调试 UI，不作为合作模式同步的验收证据。

## Cinematic：进入、跳过与退出恢复

| case_id | 来源 / Type / Id | 已核查行为 | 迁移重点 |
|---|---|---|---|
| cinematic-setup | V / Trigger / 11268265 | 淡入淡出、过场设置、保存摄像机与单位选择，并进入场景流程 | 玩家、可玩区域、暂停与 UI 状态、相机和场景 worker |
| cinematic-cleanup | V / Trigger / 3BEC60F6 | 清理场景对象与效果，停止震动、恢复摄像机/游戏状态，继续任务 | 恢复进入前状态、临时单位/行为、选择及继续触发器；不要只切回 UI |
| cinematic-skip-key | A / Trigger / 225D2E39 | 按键事件停止多个过场 worker，并转移到结束状态 | 跳过键/玩家、停止列表、临时对象与公共清理；名称不代表所有入口自动可跳过 |
| cinematic-skippable | A / Trigger / A97413B1 | TriggerSkippableBegin 后编排控件显隐/透明度和头像 actor 消息 | 控件与 portrait actor、动画消息、正常完成/跳过的共用清理 |

进入前记录状态，正常结束和跳过都调用同一清理流程。对白停止、音乐恢复、镜头/选择恢复、单位暂停、玩家控制、临时对象和触发器状态分别核对；重复结束应避免重复创建、推进目标或保存进度。

## 完整性清单与目前范围

| 需求 | 当前资料 | 仍需目标验证 |
|---|---|---|
| 单句/多句、语音头像字幕、消息队列 | Transmission 和顺序对白原例 | 声音/字幕对应关系、音量、玩家与互斥行为 |
| 地图事件触发、重复抑制、任务状态分支 | damage-alert、day-night-warning、sequential-lines | 实际单位/区域、冷却与状态复位 |
| 剧情数据、角色回调、镜头 | Conversation 原例 | Catalog/声音/模型资源、地图对象绑定与回调时机 |
| 按钮选择、关闭、重开、布局、逐字文字 | Dialog 原例 | 窗口生命周期、文字长度、分辨率与输入设备 |
| 跳过、打断、结束恢复 | stop-dialogue、Cinematic 原例 | 所有完成路径的一致清理，读档与重复调用 |
| 超时默认选择、下拉/列表输入、分支合流 | 由目标可用 Timer/Dialog 定义组合；尚无本页精选官方原例 | 超时与点击竞态、默认值、重复提交与恢复流程 |
| 合作玩家独立 UI、旁观者、全局选择同步 | 普通原生定义可参考；原例未证明多人业务语义 | 玩家作用域、共享状态、同步与掉线行为 |
| 无配音字幕、已有音频替换、语言切换 | 按目标资源组合；当前不是经过验证的新模板 | 文字锚点与实际语言资源，不属于整项目翻译 |
| 读档/重开、字幕选项、快进、资源缺失 | 需要项目测试场景 | 保存/恢复句柄与状态、设置影响、缺失资源降级 |

后三类扩展不能仅凭原生函数存在就标记已实现。迁移仍按“目标 → 依赖 → 完整定义 → 案例 → GUI → 静态 → Editor → 打包运行”执行；新的最小 GUI 模板应另行实现、静态检查并记录实际验收范围。
