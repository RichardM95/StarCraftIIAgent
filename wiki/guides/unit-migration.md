# 单位数据链迁移

[English](unit-migration.en.md)

入口为 `tools/sc2-migrate.py`。它按各来源的实际官方依赖筛选新增单位 ID，以可玩单位与建筑为迁移根，辅助形态按链带入。当前策略保持目标依赖不变；官方同 ID 修改只可作为所选单位的关联数据，不作为新增单位根。技能入口为 [sc2-unit-migration](../../skills/sc2-unit-migration/SKILL.md)。

## 分析与选择

```powershell
python tools/sc2-migrate.py plan --source "<来源.SC2Mod>" --source "<另一来源.SC2Mod>" --target "<目标.SC2Mod>" --prefix MyImported_ --output reports/migration --ui-language zh-CN
```

输出 `migration-plan.json`、`report.md` 和 `selection-template.json`。JSON 保存字段有效值、定义来源、Actor 反向关联、资源、文本、ID 映射提案与阻断原因。`analyze` 与 `plan` 使用同一分析器，均只读模组，不切换当前项目。报告目录不能位于来源或目标内。分析退出成功只表示报告生成，执行资格以各候选的 `issues` 与 `executable` 为准。共享字段证据只保存一次，通过 `object_evidence[来源路径][类型:ID]` 查看。

官方基线不完整时，已找到的官方 ID 可以排除，其余标为待确认。按[官方缓存流程](../reference/official-casc-cache.md)补证；使用 `--source-cache "Source.SC2Mod=<该来源缓存目录>"` 绑定不同来源快照，默认缓存继续用于其他来源与目标。不得以无关参考导出作为目标已启用的证据。

选择文件格式：

```json
{"units": {"CustomUnit": "Source.SC2Mod"}, "exclude": ["UnwantedUnit"]}
```

`units` 是按 ID 选择来源的覆盖表，来源可用组件名、报告中的稳定来源标识或绝对路径。没有冲突的可玩候选默认选择；辅助/不确定候选默认不选，可通过 `units` 显式选择；`exclude` 从根清单排除。排除根不会删除其他根实际需要的依赖。同名候选没有选择来源时不会进入可执行包；模板中的 `null` 必须填入来源或删除该项。

```powershell
python tools/sc2-migrate.py plan --source "<来源.SC2Mod>" --target "<目标.SC2Mod>" --prefix MyImported_ --selection reports/migration/selection.json --output reports/migration --ui-language zh-CN
python tools/sc2-migrate.py export --input reports/migration/migration-plan.json --output "<新的迁移包目录>" --ui-language zh-CN
```

## 资源与边界

普通分析读取 Components、MPQ 和已验证官方缓存，不自动打开 CASC。显式增加 `--read-casc-assets --casc-dll "<CascLib.dll>" --sc2-install-dir "<SC2安装目录>"` 才读取必要官方模型、贴图和声音，保留路径与哈希。来源无法读取的资源不能由目标同路径存在来证明等价。多语言文本、热键和语言资源保持独立，不跨语言补值。

所有复制对象使用前缀加来源命名空间；目标可证明等价的对象保留原 ID。继承字段在导出中显式化，父对象和原定义仍保留为证据。数组索引、删除、令牌、Actor 事件和文本内数据引用按语义处理；动态引用、未确认的合并、脚本和自定义 UI 机制需专项处理。种族与全局配置是目标环境接点，不据此展开整个阵营；不兼容时单独报告。单位数量/类型等身份引用优先使用目标已有 ID，不能据此自动复制整名单位。升级修改目标必须属于迁移链，否则列为专项处理。默认每个单位最多分析 2000 个对象；达到预算明确阻断，可用 `--max-objects` 调整后重跑。不同来源的同路径资源内容不同时阻断。缺失项不会通过删除引用来修复。

常见阻断：`asset_unverified` 需要核对来源资源；`external_mechanism_reference` 需要确认脚本/UI 接线；`unclassified_actor_reference` 需要识别 Actor 消息语义；`ambiguous_default_order` 表示默认定义的顺序可能改变结果；`object_budget_exceeded` 表示该链尚未展开完；`unit_source_choice_required` 需要选择同名来源。

## 导入与恢复

```powershell
python tools/sc2-migrate.py preview --package "<迁移包目录>" --ui-language zh-CN
python tools/sc2-migrate.py apply --package "<迁移包目录>" --ui-language zh-CN
python tools/sc2-migrate.py apply --package "<迁移包目录>" --apply --ui-language zh-CN
```

包绑定分析目标、来源指纹、文件清单、选择与映射。前两条只预览；最后一条才写入。不同目标须重新分析。目标变化、包被修改、同 ID 不同内容或资源冲突均阻断；现有对象不自动替换。暂存结果通过 Catalog XSD 后，复用组件发布保护切换目录。失败回滚，成功保留完整原目标及所有权记录；使用现有 `tools/sc2-archive.py restore` 预览和恢复备份。相同包重复导入核对回执与目标，不产生重复记录。

工具测试与真实模组验收分别报告。实际迁入后对目标运行组件校验、命令卡及字符串检查，再取得 `Editor accepted` 与 `packaged runtime passed` 证据；事务写入成功不能代替这些状态。

合并、关联与 M3 解析算法选择性改编自 SC2EditorTool，保留 [MIT 许可](../../tools/vendor/sc2editortool/LICENSE)与[归属说明](../../tools/vendor/sc2editortool/NOTICE)。

## 仅合并来源模组本地层

用户明确包含对官方 ID 的本地覆盖时，使用 `tools/sc2-merge-mod-layers.py plan`。本地文件不等于非官方新增内容；要求仅迁移非官方对象时，先按各来源官方基线筛选并提取单位关联链。来源依参数顺序从低到高优先；同 ID 采用最高优先级来源的完整条目，不拼接字段，不展开官方继承，也不添加依赖。保留父对象、令牌、数组删除与追加等原始定义。

```powershell
python tools/sc2-merge-mod-layers.py plan --source "<低优先级.SC2Mod>" --source "<高优先级.SC2Mod>" --target "<目标.SC2Mod>" --output reports/layer-merge --ui-language zh-CN
python tools/sc2-merge-mod-layers.py apply --input reports/layer-merge/layer-plan.json --ui-language zh-CN
python tools/sc2-merge-mod-layers.py apply --input reports/layer-merge/layer-plan.json --apply --ui-language zh-CN
```

工作目录必须新建且与源/目标分离。准备过程只写工作区副本；实际应用复核源、目标和副本指纹后发布，保留完整目标备份。素材按文件、本地化按同语言同文件的键处理优先级；`Assets/UI/` 图片仍是素材。触发器、Galaxy、UI 布局/样式和库登记单列，不从来源复制。原有目标的这些文件保持原样。

迁移前需明确是否接受目标现有依赖无法提供的官方引用。接受时保留并报告这些引用，不以复制官方层或删除字段来消除。此模式的交付状态为 `source fixed`，Catalog XML 检查单独记录；实际组件完整预检、Editor 和游戏验收仍分别执行。

## 清理已合并的官方覆盖

已应用的本地层方案可以用 `prune` 创建清理副本。传原方案与每个来源的完整官方缓存；新方案的目标仍是当前模组。所有非官方新增对象保留，官方已有 ID 仅在非官方单位的必要关联链上保留；原目标迁移前已有条目受保护。技能、武器、效果、行为、继承与必要 Actor 关联参与追踪；生产者反查、普通训练/建造产物、升级修改目标和单位身份条件单独记录，不据此展开原版单位；弹药库、变形及效果生成单位仍参与关联追踪。共享 Actor 的事件源只用于反查呈现关系，不把其他触发该 Actor 的技能反向视为依赖。删除数组槽位后的有效引用决定关联，不能重新遍历父对象而复活已删除的依赖。素材、本地化、脚本与依赖声明在该清理步骤中保持原文件。

```powershell
python tools/sc2-merge-mod-layers.py prune --input reports/layer-merge/layer-plan.json --source-cache "<来源完整路径>=<官方缓存>" --output reports/layer-pruned --ui-language zh-CN
python tools/sc2-merge-mod-layers.py apply --input reports/layer-pruned/layer-plan.json --ui-language zh-CN
python tools/sc2-merge-mod-layers.py apply --input reports/layer-pruned/layer-plan.json --apply --ui-language zh-CN
```

每个来源重复传 `--source-cache`。检查方案的 `removed`、`retained_official` 与字段原因；未完成官方基线阻止清理。应用复用指纹检查、事务发布和完整备份。动态引用和未知合并语义保留诊断，清理成功不能证明运行机制已完整移植。
