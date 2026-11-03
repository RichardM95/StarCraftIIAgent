# SC2 技能入口固定案例验收

作者：扯蛋虾米。使用同一组 16 个中文请求，人工核对全局入口、项目路由和专业技能的实际文本。改前文件指纹与快照保存在本轮运行目录。文档加载数按全局入口、项目入口、首个专业技能计，两版均为 3。

16 项均有明确路由，关键路由错误为零。该结果表示规则覆盖，通过实操检查正常工具路径，模型选择命中率尚未测量。

| 案例 | 请求 | 首选技能 | 改前问题 | 改后检查 |
|---|---|---|---|---|
| 01 | 查询这张地图撤离触发器的成功分支 | sc2-map-triggers | high-level GUI workflow below XML details | 明确目标、首动作及交接 |
| 02 | 只有玩家1首次进入已有EvacZone才完成目标 | sc2-map-triggers | high-level GUI workflow below XML details | 明确目标、首动作及交接 |
| 03 | 替换成功分支并调整动作顺序 | sc2-map-triggers | high-level GUI workflow below XML details | 明确目标、首动作及交接 |
| 04 | 地图初始化时调用活动模组导出的GUI动作 | sc2-map-triggers | high-level GUI workflow below XML details | 明确目标、首动作及交接 |
| 05 | 将触发器移动分类并保留ID | sc2-map-triggers | high-level GUI workflow below XML details | 明确目标、首动作及交接 |
| 06 | 把已有救援单位向东移动两格 | sc2-terrain-editing | workflow requires reading mode distinctions | 明确目标、首动作及交接 |
| 07 | 创建名为EvacZone的矩形区域 | sc2-terrain-editing | workflow requires reading mode distinctions | 明确目标、首动作及交接 |
| 08 | 在已有工作副本续画道路 | sc2-terrain-editing | workflow requires reading mode distinctions | 明确目标、首动作及交接 |
| 09 | 检查桥梁是否实际可通行 | sc2-terrain-editing | workflow requires reading mode distinctions | 明确目标、首动作及交接 |
| 10 | 调查可复用的真实地形组件再制作副本 | sc2-terrain-editing | workflow requires reading mode distinctions | 明确目标、首动作及交接 |
| 11 | 新建撤离区并实现首次进入逻辑 | sc2-terrain-editing | mixed handoff not explicit | 明确目标、首动作及交接 |
| 12 | 摆放救援单位并实现靠近后的营救目标 | sc2-terrain-editing | mixed handoff not explicit | 明确目标、首动作及交接 |
| 13 | 修复救援单位已经摆好但任务无法完成 | sc2-map-triggers | mixed handoff not explicit | 明确目标、首动作及交接 |
| 14 | 先移动撤离区再重新绑定进入事件 | sc2-terrain-editing | mixed handoff not explicit | 明确目标、首动作及交接 |
| 15 | 修复既有手写Galaxy函数 | sc2-galaxy-scripting | workflow requires reading mode distinctions | 明确目标、首动作及交接 |
| 16 | 将Custom AI进攻波迁移成普通GUI触发器 | sc2-attack-wave-scaling | workflow requires reading mode distinctions | 明确目标、首动作及交接 |

三条实操均使用独立工作副本和现有共享实现。GUI 分支候选通过离线检查后经 Service 提交、回滚，并核对还原哈希。地形移动既有点位对象，验证新副本、undo/redo。混合流程创建 SkillHandoffZone，拒绝旧上下文，重新读取同一副本并核对 GUI ValueId 与实际区域 ID 一致。结果达到 `static validation passed`。

本机三个技能入口已同步。已有 sc2-editor 连接配置与完整注册预期不同，完整本机重注册受保护规则拒绝。技能文件与托管指纹已更新，MCP 配置文件哈希保持一致。隔离配置的注册、重复注册、冲突保护及卸载测试通过。

详细案例见 [固定输入](sc2-routing-cases.json)。本机运行记录与安装指纹由执行验收的工作区保存。此前 B98370 编辑器与实机记录按原归档范围使用。

全局发现先识别用户明确指定或当前目录所属的独立开发工作区，再按 Hub 映射和全局回退定位。本机 Hub 的 SC2ModAgent 缺少新版 sc2-local.py、sc2-terrain.py 和高层作者实现，相关入口因此要求先查能力并报告缺口。独立 StarCraftIIAgent 工作区的三条实操已验证。
