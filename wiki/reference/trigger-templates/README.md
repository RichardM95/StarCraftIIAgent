# 七类最小 GUI 模板

[Triggers](GuiPatterns.SC2Map/Triggers) 和配套 [TriggerStrings](GuiPatterns.SC2Map/enUS.SC2Data/LocalizedData/TriggerStrings.txt)、[GameStrings](GuiPatterns.SC2Map/enUS.SC2Data/LocalizedData/GameStrings.txt) 是可迁移的片段集合。目录后缀用于识别本地引用作用域，不包含地形等地图组件，不能直接当作完整地图运行。

[清单](manifest.json) 记录各机制的 Trigger ID、原生源指纹、所需库及静态状态。[官方案例](../trigger-cases.json) 给出每类来源的精确 ID、人工核查说明、本地引用关系和资源需求。模板是从这些机制提炼的原生 GUI 最小实现，不是原地图整段复制。

所有片段引用 Ntve；实际目标必须确认其基础库来源。`PlayerDifficulty`、AI 波次等函数是否可用由加载的实际定义决定，不根据地图属于哪个资料片判断。

| 机制 | 片段行为 | 移植前必须配置 | Editor 与游戏验收 |
|---|---|---|---|
| 初始化 | Map Initialization 事件显示 Chat 消息 | 消息与初始化入口；合并到目标既有初始化流程 | 重载/保存后检查事件生成；进入地图只显示一次 |
| 目标 | 创建目标并立即保存 LastCreated；独立 worker 完成目标 | 目标文字、目标句柄变量；先调用创建，再在完成条件成立时调用完成 | 检查变量与文字；确认完成指定目标而非其他目标 |
| 胜败 | 两个 eventless worker 分别结束玩家游戏 | 玩家、胜败条件；战役项目先执行自身进度保存和结果流程 | 分别触发胜利与失败，确认结果和进度；普通 GameOver 片段不包含官方战役封装 |
| 区域 | Any Unit 进入指定区域时显示消息 | TemplateRegion 当前为 Entire Map，替换目标区域，补玩家/单位过滤 | 核对区域引用；进入触发，离开不触发，过滤条件正确 |
| 计时器 | 初始化 timer 变量；worker 启动；到期事件显示消息 | 持续时间、重复选项；使用 GUI Run Trigger 调用 Start Timer | 检查事件使用同一 timer；开始前不触发，到期按配置触发 |
| 波次 | 使用已有单位组、设置目标点、发送 AI wave | AI 玩家，非空 TemplateWaveUnits，实际 TemplateWaveTarget；先完成 AI 启动 | 核对 AI 入口；指定单位向目标进攻；再次调用没有错误或重复任务 |
| 难度 | If/Then/Else 比较玩家难度并显示对应消息 | 玩家，难度值，两个分支动作；示例值为 3，名称须按目标定义核对 | 检查 if/then/else 子类型；两个难度分别进入预期分支 |

迁移时只选择所需机制及其本地引用闭包，重分配 ID 和字符串锚点；保留其变量初始值。事件调用元素按保守交接规则紧邻对应触发器。所有 worker 使用普通 GUI Run Trigger 接入目标编排，地图对模组的调用必须使用导出的 GUI Action Definition。

```text
python tools/sc2-trigger-query.py --reference check --templates
python tools/sc2-trigger-query.py --target "<目标.SC2Map>" --mods-dir "<Mods>" --campaigns-dir "<Campaigns>" check --templates
```

状态：`static validation passed`。依据为官方 NativeLib 源的完整引用闭包、参数归属、子动作、唯一声明和本地字符串检查。此状态不表示 `Editor accepted` 或 `packaged runtime passed`；上述场景仍需实际验证。

后续实际验收使用 [统一记录格式](acceptance.md)，记录模板与原生源指纹、编辑器版本、替换输入、保存前后对照及打包运行证据。
