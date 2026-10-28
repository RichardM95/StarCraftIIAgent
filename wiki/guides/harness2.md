# Harness2 项目内安装

[English](harness2.en.md)

[官方仓库](https://github.com/google-research/harness2)提供递归改进 agent harness 的命令行研究框架。源码位于 `integrations/harness2/`，固定版本、许可证和来源校验信息见[安装来源](../../integrations/harness2.agent.json)。官方代码及生成的 harness 不覆盖本工作区的 AGENTS、Skill 或项目配置。

## 运行

### 新机器重建环境

Git 只分发源码和依赖清单，不包含已安装的 Python/WSL、`.venv-linux`、`.runtime`、登录信息或实验结果。先准备 Linux 或可访问克隆目录的 WSL（默认发行版名为 `Ubuntu-22.04`），以及 `uv`。在 **Linux/WSL 终端**切换到克隆目录的 `integrations/harness2/`，运行：

```bash
uv venv --python 3.12 .venv-linux
uv pip install --python .venv-linux/bin/python -r requirements.agent.lock
uv pip install --python .venv-linux/bin/python --no-deps -e .
```

这会重新获取本机运行时和依赖，需要下载源可访问。随后返回工作区根目录运行下列 demo/test。真实 SC2 优化另需已通过 ChatGPT 登录的本机 Codex CLI，执行 `codex-configure` 和 `codex-probe`；后者会真实调用所选模型。全局薄入口或 MCP 注册不是运行此研究框架的前提。

官方要求 Linux；Windows 使用已安装的 `Ubuntu-22.04` WSL，其他发行版通过 `--distro` 选择。隔离环境固定在 `integrations/harness2/.venv-linux/`；已有安装也可能把 Python 3.12 运行时保存在 `.runtime/harness2/python-linux/`。不依赖激活虚拟环境，也不要求复用维护者的运行时路径。

在工作区运行：

```powershell
python tools/harness2.py --ui-language zh-CN demo --k 2
python tools/harness2.py --ui-language zh-CN test
python tools/harness2.py --ui-language zh-CN run --help
python tools/harness2.py --ui-language zh-CN setup lab --dry-run
```

`demo` 使用确定性编辑器和实际 Python 子进程，执行 parallel 与 sequential 两种递归，不使用模型或凭据。默认结果位于 `.runtime/harness2/demo/demo.json`；`--output` 可指定 Linux 路径。重复使用同一路径会沿用已有状态；独立实验应更换输出目录。

入口支持 `demo`、`run`、`setup`、`check`、`judge`、`report`、`bridge` 和 `test`，命令后参数传给上游。`--distro` 可选择其他已安装 WSL 发行版，但运行时仍须可访问本工作区。界面语言控制本地入口帮助，上游原始输出保持原样。

## 模型与基准

本次安装包含核心包及官方 `render` 依赖。JobBench、LAB 和 WorkBuddy 数据、Node/Bun 执行器、Google Cloud CLI、Docker 与可选模型桥接依赖按实际选择另外安装；先检查 `setup <bench> --dry-run`。模型基准的前提见[官方安装说明](https://github.com/google-research/harness2/blob/main/docs/SETUP.md)。WSL 必须能够访问相应下载源和模型端点。

用户模型设置写入 `integrations/harness2/.env`，该文件已忽略；不要写入源码或来源清单。官方提供 Vertex 配置，也支持为 Codex 执行器指定 Responses API 端点。现有 DeepSeek Harness 的 Anthropic Messages 路由不能据此直接当作 Responses API 使用。

SC2 适配器另外支持本机 Codex CLI 的 ChatGPT 登录。模型默认继承用户 Codex 配置；当前已选 `gpt-6.1-sol`。它使用 Codex 官方托管连接，不需要新建 Responses API key，也不复制认证文件或 DeepSeek Harness 凭据。现有 MCP 配置保持完整。

## 真实 Codex 与 SC2 技能优化

```powershell
python tools/harness2.py --ui-language zh-CN codex-configure
python tools/harness2.py --ui-language zh-CN codex-probe
python tools/harness2.py --ui-language zh-CN sc2-optimize
python tools/harness2.py --ui-language zh-CN sc2-finalize "<实验目录>"
python tools/harness2.py --ui-language zh-CN sc2-apply "<实验目录>"
python tools/harness2.py --ui-language zh-CN sc2-restore "<实验目录>"
```

本机配置保存在忽略的 `.runtime/harness2/codex.json`，实验位于 `.runtime/harness2/sc2-runs/`。`codex-configure` 读取当前 CLI 模型选择并确认 ChatGPT 登录；更换 CLI 默认模型后重新配置，使用新实验目录。不同模型的实验不混合恢复。

Windows Codex 负责真实模型连接，WSL 运行 Harness2 调度。SC2 适配器固定使用 `read-only` 沙箱、`on-request` 审批、结构化输出；不加载用户工具配置，禁用 shell、hooks、插件、连接器、浏览器和子智能体。模型只提交本地化操作或限定的 Skill 文本，本地代码检查后在隔离 Components 副本中调用已有审计工具。没有权限绕过参数，不自动提升权限；单次调用 600 秒，超时清理所属进程树。提交状态不明或已失败时保留记录，不自动重复提交。

无选择参数时保留原有 `sc2-localization` 流程，采用一次 parallel 递归：实际基线、候选执行、组合及经验记录。项目 AGENTS 与 Skill 元数据不可修改，不能增加脚本、hooks 或项目专用规则。验收覆盖世界悬停、命令卡提示、编辑器显示名称；验证实际文本、markup/占位符、目标和语言范围，以及其他文件和生成源码未变。工具提交前的提案状态为 `root cause confirmed`，宿主执行并复核后另行记录静态验收状态，两者不得混淆。

`sc2-finalize` 在候选选定后，另外用不同对象 ID 与语言完成基线/候选各一次真实模型调用；它不是只读状态查询。主智能体复核后修订的版本还要重新执行训练案例。只有训练与独立复核均为 3/3、完整保留约束及有效链接、技能字符数至少减少 10%，才允许 `sc2-apply` 合并。合并前核对原技能 SHA256，保留原始字节备份；源已变则停止。相同输入的已完成调用复用结果，合并不重新派发模型任务。`sc2-restore` 仅在当前技能仍匹配本次合并指纹时恢复。最终结论限定为这组案例的 `static validation passed`，不据此声称普遍提高成功率。

## 分批优化专业技能

[技能与分组清单](../../tools/harness2-skills.json)固定 24 个技能的 ID、源路径、验收类型和顺序。Galaxy 基础组三项先行，其余 Galaxy 按 ID 两项一组，之后是三组 SC2Data、三个领域技能，最后联合处理项目入口与工具验证。本地化技能保留并参加最终工具回归。

```powershell
python tools/harness2.py --ui-language zh-CN sc2-optimize --skill galaxy-language-fundamentals
python tools/harness2.py --ui-language zh-CN sc2-optimize --batch "<分组清单.json>"
python tools/harness2.py --ui-language zh-CN sc2-finalize "<分组实验目录>"
python tools/harness2.py --ui-language zh-CN sc2-apply "<分组实验目录>"
python tools/harness2.py --ui-language zh-CN sc2-restore "<分组实验目录>"
```

分组输入格式为 `{"skills":["技能ID","技能ID"]}`。分组实验保存在 `.runtime/harness2/skill-batches/`；`batch.json` 冻结模型配置、实现文件、AGENTS、原文件指纹及章节迁移表。改变实现、模型、案例或源文件后创建新实验；不能把旧结果沿用为新实现的验收。

宿主按围栏外的章节无损拆出参考文档，只重定位 Markdown 链接；API、字段、示例和技术限制保留原文。模型只允许改清单中的入口 Markdown，原始规则与参考文档由宿主保持不变。基线使用原入口并直接求解，不额外添加空读取调用；候选先看到入口和参考路径，再选择读取内容。宿主校验白名单后才提供所选资料，所有资料选择与求解调用均计入输入 token，包括原生执行器的固定输入开销。实验固定查阅推理预算为 `low`、优化与复核为 `medium`，基线和候选一致，模型仍为所配置的 `gpt-6.1-sol`。优化器仅接收入口相关章节和不可变参考索引，完整技术原文由宿主保留。并发最多两个，使用跨进程共享槽；每个调用最多 600 秒。

每个技能分别使用三个训练问题与三个独立问题，另验生成源码保护、GUI 优先、活动继承、语言与 locale、目标绑定及精确验收状态。领域验收再检查 Catalog 继承值、Actor 素材链和视觉证据、GUI 库可用性、全入口路由或工具检查范围。这些参考与路由任务不等同于 Editor 编译或游戏验收。

`adoption.json` 记录实际调用、逐技能结果和包含资料读取的总输入 token。每个技能须全部候选检查通过，并观察到原先失败的路由分支被修正，或匹配任务的平均输入 token 至少减少 10%；分组平均值不能替代单项门槛。无收益项保持原样。合并还要求主智能体复核完整差异，以候选指纹记录在 `review.json`，并通过组合文件的链接与工具引用检查。合并前核对全部待写源指纹，先保留精确字节备份和暂存结果，再写入。恢复会先核对整组文件，任何后续修改都会阻止整组恢复；仅删除本次创建且仍匹配指纹的参考文件。若写入中断，保留的 `applying` 记录同样可用于受保护恢复。

## 状态与维护

入口将基准结果保存到 `.runtime/harness2/runs/`；上游依赖在 `integrations/harness2/dependencies/` 的各自子目录。环境、凭据、缓存及结果均已忽略。实验产物应先检查差异和证据，再决定是否纳入工作区规则。

复装可在 Linux 中用 Python 3.12 创建 `.venv-linux`，安装 `integrations/harness2[render]`；离线 wheel 保存于本机 `temp/harness2-wheels/`。无需可选 `bridge` 依赖即可运行 demo。只运行 `check` 或 `--help` 不证明模型联通，demo 通过也不代表模型基准或 SC2 编辑器、游戏验收通过。
