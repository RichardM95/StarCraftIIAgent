# 地形模块制图工具与编辑器实验

[English](sc2-terrain-editing.en.md)

技能入口：[sc2-terrain-editing](../../skills/sc2-terrain-editing/SKILL.md)。作者声明沿用 [AUTHORS](../../AUTHORS.md)。当前目标是从参考地图副本完成基础制图：高度、纹理、悬崖坡道、水体，单位／装饰物／区域的增删移动，以及菌毯、道路、植被、光照和视野绘制。完整复刻编辑器的高级菜单和全部属性属于可选扩展。能力与缺口以 `capabilities` 输出为唯一清单，区分工具实现、诊断预览、编辑器验证和游戏验证。

## 改图与场景组织

需要可直接发送的制图请求时，使用[地形模块 26 个场景与两组多轮对话](terrain-conversations.md)。它按模块图层区分需求、当前实现缺口与验收，不要求每次自行组织工具参数。

扩建关卡、细化空旷场景或连接桥梁／隧道时，按需读取[改图与场景组织](../../skills/sc2-terrain-editing/references/map-adaptation.md)：从用户最新保存版继续，先确定通路与功能空间，再放主体建筑和岩体，最后安排设施、植被与地表细节。单位摆放默认沿用当地材质，道路服务连续通路；数量很多的小碎物不能替代空间围合。任务对象行为、官方语音和触发器目录参考[地图GUI改编](../../skills/sc2-map-triggers/references/map-adaptation.md)。案例数值不是其他地图的固定模板，GUI编译通过也不代表地形或游戏行为通过。

## 查询与学习

```powershell
python tools/sc2-terrain.py --ui-language zh-CN capabilities
python tools/sc2-terrain.py --ui-language zh-CN capabilities --basic-only --pending-only
python tools/sc2-terrain.py --ui-language zh-CN scan "<参考Maps目录>" --audit --output temp/terrain-corpus.json
python tools/sc2-terrain.py --ui-language zh-CN inspect "<地图.SC2Map>"
python tools/sc2-terrain.py --ui-language zh-CN dependencies "<地图.SC2Map>" --mods-dir "<实际Mods目录>"
python tools/sc2-terrain.py --ui-language zh-CN render "<地图.SC2Map>" --layers height,cliffs,water,point,regions,grid --output temp/terrain-preview.svg
```

本次提供的强化战役素材有 99 张 Components 地图，其中 90 张有地形。地图包含自定义依赖，不能当作完全未经修改的官方原版。参考根目录由调用者明确传入，工具不会因此切换当前所选项目。地图、对象类型和资源是否真正可用，应从实际地图依赖链查询；部分依赖调查不等于已解决运行条件。

`audit` 的无修改往返验证覆盖已支持格式，不代表新笔刷已经实现。SVG 是高度与图层的诊断预览，不能替代原生材质、镜头效果和实机寻路。

## 在独立副本上修改

先用 `inspect`、`select` 核对坐标、对象 ID、纹理槽和水体配置，再按技能的[操作契约](../../skills/sc2-terrain-editing/references/operations.md)准备 JSON。创建明确的工作区输出父目录，先预览再应用：

```powershell
python tools/sc2-terrain.py --ui-language zh-CN plan "<源地图.SC2Map>" --operations "<操作.json>" --output temp/terrain-plan.json
python tools/sc2-terrain.py --ui-language zh-CN apply temp/terrain-plan.json --output temp/TerrainWork.SC2Map
python tools/sc2-terrain.py --ui-language zh-CN apply temp/terrain-plan.json --output temp/TerrainWork.SC2Map --apply
python tools/sc2-terrain.py --ui-language zh-CN audit temp/TerrainWork.SC2Map
python tools/sc2-terrain.py --ui-language zh-CN undo temp/TerrainWork.SC2Map --apply
python tools/sc2-terrain.py --ui-language zh-CN redo temp/TerrainWork.SC2Map --apply
```

计划绑定完整源内容哈希和预期修改，源变化后需要新计划。对已有工作副本继续修改时，以该副本生成新计划并应用回同一工具拥有的副本；不覆盖无历史归属的其他地图。历史快照保存在相邻的 `.terrain-work` 目录，事务发布还会保留被替换的地图备份。

编辑器保存会改变多个组件，旧撤销历史随之失效。保留编辑器保存后的地图，再以新路径开始下一份工作副本。文件或历史不一致时停止覆盖，检查现有日志与备份。原始战役地图、当前项目配置和 `publish/` 不作为实验写入目标。

## 补齐基础操作与按需扩展

`active_requirement` 标记当前基础制图需求；原有完整模块清单保留为扩展候选。用 `--basic-only --pending-only` 定位尚缺少写入能力的基础操作；地图扩缩、全部属性复刻和高级寻路不作为当前完成门槛。缺少写入能力的请求需明确说明，并通过受控实验查证，不能用教程或预览代替实际修改。

单位和装饰物添加目前复用地图内同类模板；移动和删除使用明确选择器，删除带触发器引用的对象会被拒绝。区域支持创建圆、矩形、菱形及移动、合并副本、删除。属性字段可用 `object-schema --kind unit` 等查询正式 XSD。道路支持整组复制、移动、移除，以及复用原生两端点样式新建直路。植被支持基于已有标记的散布和移除；新实例优先排列，泽鲁斯对照已确认可见效果。其他标记／纹理组合需以实际可见的样例为依据。菌毯、视野阻挡和区域 1／2 光照已具备限定范围的编辑器验证。具体边界以清单和证据页为准。

基础单位、装饰物和矩形区域的增删移动已通过编辑器保存重开验证。摆放或移动时需根据入口、阵型和构件走向设置朝向：`face_towards` 可面向目标点，`attributes.Rotation` 可指定弧度角，均可原地转向。预览标出朝向轴；模型实际前向仍需编辑器检查。

`pathing` 已实现整单元不可通行绘制和清除，MarSara 对照已通过编辑器保存重开检查。`doodad-blockers` 按明确、已核实的静态占地矩形自动补画阻挡，随所选装饰物后续的移动、旋转、缩放、删除同步，并保留原有及重叠阻挡。`keep_clear` 可保护预留通道。归属信息保存在相邻工具历史中；不要仅复制地图而丢弃它。占地未知时拒绝写入，不能按模型外框猜测。人工指定试验矩形的移动／旋转／旧位置恢复已通过编辑器 C／D 对照验证，不代表已识别模型真实占地。整单元栅格会向外保守取整，细分路径、任意 Catalog 占地解析仍未实现。原生可移动／可破坏对象保持原生阻挡；地面／空中通行、建筑放置和视线需分别处理，详见[摆放与寻路规则](../../skills/sc2-terrain-editing/references/operations.md#placement-and-pathing)。

绝对高度装饰物的水平移动、复制和 XY 对齐默认保留离地偏移，避免换到高地后仍留在原 Z 而埋入地下。显式 XYZ 坐标默认保留给定 Z；可用 `grounding: snap` 贴地或 `keep-z` 固定高度。MarSara 石头接地修正已通过保存重开验证，当前默认移动流程也能重现相同对象和路径数据。地形采样限单位缩放、零偏移，不解析桥面或其他模型表面；混合悬崖采样会被拒绝。

```powershell
python tools/sc2-terrain.py --ui-language zh-CN experiment "<参考.SC2Map>" --feature cliff.raise --rect 40 40 44 44 --output temp/cliff-probe
python tools/sc2-terrain.py --ui-language zh-CN experiment-baseline temp/cliff-probe
python tools/sc2-terrain.py --ui-language zh-CN experiment-compare temp/cliff-probe --output temp/cliff-diff.json
```

创建实验后，按生成的 `steps.txt` 操作：先空保存并关闭，再捕获规范化基线；随后只做一个功能操作，记录参数，保存、关闭并重新打开核对，最后关闭地图供工具读取。经授权且界面输入确实生效时可由智能体操作，否则仅请用户完成无法代办的步骤。需要相应游戏行为时再做实机验证。

若文件无法读取，先记录具体组件及错误。`experiment-compare --allow-unreadable` 仅允许只读部分比较，输出每个不可读组件，不能作为完整联动证据。格式升级、全局重新量化和编辑器规范化也要与局部功能变化区分。

## 验收与维护

专项回归为 `python -m unittest discover -s tools/tests -p test_sc2_terrain.py`。工具与规则接入变更另运行 `python tools/test-suite.py --scope tools` 和 `--scope docs`。技能使用 skill-creator 的 `quick_validate.py` 检查。

遵循[反馈流程](../implementation/testing-feedback-workflow.md)：静态检查最多报告 `static validation passed`；实际打开、保存和重开成功才可对对应产物报告 `Editor accepted`；打包实机步骤与结果齐全后才报告 `packaged runtime passed`。手工实验通过与工具生成结果通过分开记录，基础制图按当前需求验收，不以可选的完整编辑器对齐阻塞交付。高度、纹理、悬崖样式复用和独立水面高度的具体已验收范围见[编辑器证据](../../skills/sc2-terrain-editing/references/editor-evidence.md)。
