# 共享本地工具、MCP 与 Skill

[English](shared-tools.en.md)

现有工具负责成熟工作流；新增能力由本地命令和 MCP 共享实现，Skill 负责路由、复核和验收。[技能入口](../../skills/sc2-shared-tools/SKILL.md)、[能力对应表](../../integrations/CAPABILITIES.json)、[技能合并记录](../../integrations/SKILL-MERGE.json)分别描述调用策略与来源。

## 安装与诊断

使用 Python 3.12 或更新版本。安装器为两个包分别建立环境，优先使用锁定依赖；可显式选择包索引。

```powershell
python tools/sc2-integration.py --ui-language zh-CN install --index-url https://pypi.org/simple
python tools/sc2-integration.py --ui-language zh-CN configure
python tools/sc2-integration.py --ui-language zh-CN diagnose
python tools/sc2-integration.py --ui-language zh-CN register
```

`configure` 自动发现 Harness，也接受 `--harness-exe` 和 `--harness-cli`。离线安装可传 `--offline --wheelhouse <wheel目录>`。

用户设置保存在 `%LOCALAPPDATA%/StarCraftIIAgent/integrations.json`；`SC2_AGENT_INTEGRATION_CONFIG` 可指定其他文件。凭据由 Harness 读取，工具只检查文件是否存在，不复制内容。

`register` 增量添加全局 `sc2-editor`、`deepseek-supervisor` 和薄技能入口，保留其他配置并保存备份。相同配置可重复注册；不同内容的同名服务/技能会报冲突。`unregister` 只移除仍与注册记录相符的条目，保留代码、环境与运行证据。注册成功后需由客户端重新连接，不能据此声称当前聊天已加载。

## 能力归属

| 任务 | 默认入口 |
|---|---|
| Catalog 有效值、GUI 触发器、字符串锚点 | 现有 Catalog、触发器和本地化工具 |
| 地形与单位迁移 | 现有地形和迁移工具，按各自能力证据执行 |
| 官方皮肤、模型和素材链 | 官方资源技能与共享实现 |
| 地图外壳、地区环境、编辑器警告 | 共享诊断与候选工具 |
| 候选差异、提交、恢复 | 同一共享事务入口完成整个修改 |
| DeepSeek SC2 子任务 | 已连接 MCP；否则受管理的 CLI 进程 |
| 钥石专用机制 | 不作为当前工作区通用接口开放 |

新增能力优先调用已连接 MCP；连接不可用时使用同一实现的 CLI。业务拒绝不能通过切换入口绕过。提交状态不确定时先查询已有任务或事务，禁止盲目重复提交。

## 本地调用

```powershell
python tools/sc2-local.py --ui-language zh-CN capabilities
python tools/sc2-local.py --ui-language zh-CN tools
python tools/sc2-local.py --ui-language zh-CN call sc2_project_open --arguments-file open.json
```

`open.json` 指定明确目标，不默认选择另一个项目的 LoyalWOL：

```json
{"path":"<Components绝对路径>","writable":false,"search_roots":["<SC2安装绝对路径>"]}
```

随后使用实际返回的 project_id，通过 `sc2_official_assets_search`、`sc2_validate_map_shell`、`sc2_validate_data_warnings` 等接口调查。`tools --operation <operation>` 输出指定操作的参数 schema。复杂、多行或含 shell 特殊字符的输入使用 JSON 文件。

CLI 和 MCP 共用业务函数与参数校验，返回 `ok/result`；CLI 错误返回 `ok:false/error`，退出码 0 表示成功、1 表示业务拒绝、2 表示请求无效。CLI 的长任务由该命令进程持有并等待完成，可使用智能体 exec 会话；MCP 通过任务 ID 查询。数据结果与验收规则共用，交付时序可以不同。

默认全局运行索引和进程槽位保存在套件 `.runtime/integrations/`，避免 Windows 打包应用的 AppData 写入重定向；项目候选、报告、事务和 DeepSeek 任务保存到按 `sc2_paths` 定位的项目资料 `runtime/integrations/`。工作区内独立测试地图使用套件数据目录下按目标指纹区分的项目目录。显式 CLI `--state` 或测试环境变量 `SC2_AGENT_RUNTIME_ROOT` 提供隔离状态，不迁移历史记录。

## DeepSeek

```powershell
python tools/deepseek-task.py --ui-language zh-CN diagnose
python tools/deepseek-task.py --ui-language zh-CN capabilities
python tools/deepseek-task.py --ui-language zh-CN models
python tools/deepseek-task.py --ui-language zh-CN run --packet task.json
python tools/deepseek-task.py --ui-language zh-CN status <task-id>
python tools/deepseek-task.py --ui-language zh-CN result <task-id>
python tools/deepseek-task.py --ui-language zh-CN cancel <task-id>
```

任务包使用稳定 request_id、明确 workspace、input_files、allowed_files、goal、constraints、acceptance 和 `profile:"sc2"`。模型通过 Harness 已保存的 provider 配置选择；所有入口合计最多 4 个任务、单任务 1200 秒。CLI 与 MCP 共享项目任务索引、请求去重、取消机制和进程槽位锁；进程退出不自动重派。

主智能体定位根因、选择目标并定义验收；自动委派只限已授权 SC2 工作中的明确子任务，其他领域需要用户明确要求。Worker 仅修改隔离候选，其文件桥只能读取选定数据或规划候选，不能提交源修改。实际修改、源冲突、桥接事件及候选哈希均需独立复核。

SC2 源修改优先通过 `sc2_changes_prepare` 导入统一事务；其他明确允许的文件可使用 `integrate --review-note` 或 `integrate_task`。生成 Galaxy、publish 路径、源文件变化和竞争整合都会被拒绝。删除候选需要单独规划，不由监督器自动整合。

历史能力测评只作为带版本的参考。本机诊断成功不证明 Harness 登录、模型可用或地图验收；必须分别检查真实任务与应用证据。

## 验收与维护

CLI 和 MCP 的参数、保护规则与结果由共享 Dispatcher/Manager 维护。全局技能只定位本工作区，不改变已有 Hub 归属。更新实现时运行相应测试；工具与文档检查使用现有 tools、docs scope。

生成 MapScript/Lib Galaxy 与 publish 编辑在统一事务及 Worker 整合层受保护。静态检查、编辑器保存重开、打包运行及视觉结果按证据分别报告。未取得编辑器或游戏证据时，适用结论最高为 `static validation passed`。

## 自定义与本地模型

用 `models` 查看已保存的路由和模型 ID。以下设置只改变监督器默认选择，不修改 Harness 的模型页面：

```powershell
python tools/sc2-integration.py --ui-language zh-CN configure --provider <provider-id> --model <model-id>
```

任务 JSON 中的 `provider`、`model` 可覆盖默认值，提交时会固化实际选择，后续继续任务不会因默认值变化而换模型。SDK 从 Harness 的 desktop provider patch 读取对应的 `llm-pi-ai` 定义，支持模型页面配置的协议；用 `--provider-config` 指定其他配置文件，用 `--credentials-file` 指定其他凭据文件。实现不读取凭据值，不把地址写入仓库或模型任务包。只有声明支持 reasoning 的自定义模型才接收 effort 参数。

NumPy 在整合锁中固定为 2.5.4；原包锁文件作为来源保留。真实连接自检可运行 `python tools/sc2-integration.py --ui-language zh-CN smoke`；加 `--with-deepseek` 会派发一个独立测试任务并消耗所选模型额度。

启动器使用正常解释器的 `-E -S` 模式加载所选环境的 site-packages，既保留依赖隔离，也避免 Windows venv 启动器的目录限制；CLI、MCP 和文件桥使用同一个启动函数。
