# 编辑器交接清单

智能体完成代码修改后、开始游戏测试前，使用本清单完成交接。智能体应在实现任务结束时给出与本次修改相关的步骤，不必重复整份编辑器说明。

---

## 问题生命周期门槛

编辑器交接是问题生命周期的第五个门槛：`reported` → `root cause confirmed` → `source fixed` → `static validation passed` → **`Editor accepted`** → `packaged runtime passed`。

静态测试全部通过，并不能让问题越过编辑器门槛。执行编辑器验证的人必须确认正确的模组/地图依赖配置、检查警告、保存为 Components，并记录测试场景与结果。

交接报告必须明确写出当前最高状态。例如：`static validation passed；等待 Editor accepted`。未实际执行游戏内验收时，不使用“彻底完成”或“已经完全修复”。

## 源文件与部署模式

先读取 `agent-config.json` 的 `project.source_mode`：

- `in_place`：配置的 `paths.mods_dir/<primary_mod>` 就是唯一权威源。直接编辑并验证该目录；`deploy-mod.py` 只报告安全的 no-op。不要创建另一份可编辑模组副本。
- `workspace_copy`：`project.source_mod` 指定的主模组副本是唯一权威源；路径相对工作区或为绝对路径，缺失时停止写入。先运行 `python tools/deploy-mod.py --dry-run` 核对方向，再部署到SC2目录；禁止反向从部署目录覆盖工作区源。

部署方式由初始化后的项目配置决定。自动部署保留 `project.primary_mod` 子目录；显式 `--source` 按文件夹名部署。先核对 dry-run 的完整目标路径。已配置源缺失时停止，不寻找同名旧副本。

---

## Galaxy 脚本修改后

1. 保存手写脚本源码。`workspace_copy` 模式先运行 `python tools/deploy-mod.py --dry-run` 核对方向，再复制组件；`in_place` 模式跳过部署。
2. 在 SC2 编辑器中打开 `<ModName>.SC2Mod`，确认触发器编辑器中的自定义脚本块或 `include` 引用指向预期源码。
3. 编译触发器，然后选择 **File → Save**，将模组保存为 **Components**。由编辑器重新生成 `Lib*.galaxy`；不要手工向编译库粘贴脚本。

---

## Mod XML 或触发器 GUI 修改后

1. 在 SC2 编辑器中打开 `<ModName>.SC2Mod`。
2. 检查编辑器输出面板中的 XML 警告；保存前解决 catalog 类型或 ID 问题。
3. 选择 **File → Save**，将模组保存为 **Components**。
4. 如果直接编辑了地图的 `Triggers` XML，请在编辑器中重新打开受影响的 `.SC2Map` 并保存为 **Components**，让 `MapScript.galaxy` 重新干净生成。

---

## 地图组件修改后

1. 在 SC2 编辑器中打开配置路径 `paths.campaign_maps_dir/<Category>/<MapName>.SC2Map/` 下的地图。
2. 确认 **Modules → Dependencies** 中包含 `<ModName>.SC2Mod`。
3. **绝不**在项目模组作为外部 override 激活时打开 Blizzard 地图。
4. 选择 **File → Save**，将地图保存为 **Components**。

---

## 游戏测试后

1. 提取运行时警告/错误：`python tools/extract-playtest-bugreport.py`。
2. 按[测试反馈工作流](../implementation/testing-feedback-workflow.md)进行分诊。
3. 在[活动问题账本](../implementation/bug-reports/latest.md)中记录并跟踪缺陷。
