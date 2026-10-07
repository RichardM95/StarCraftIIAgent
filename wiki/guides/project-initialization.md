# 项目初始化配置

本指南只处理两种情况：

1. 首次安装智能体工作区。
2. 让智能体选择并使用一个已经存在的 `.SC2Mod` 项目。

项目路径统一保存在工作区根目录的 `agent-config.json`。工具优先保存相对路径；若智能体工作区与 SC2 位于不同磁盘，会自动保存必要的绝对路径并在验证时提示其为机器专用配置。不要把机器绝对路径写进技能、wiki 或 Galaxy/XML 文件。

---

## 推荐：通过一句话完成配置

选择 `StarCraftIIAgent` 作为智能体工作区后，只需在对话中提供主 Mod 的 **Components 文件夹完整路径**，例如：

```text
主 Mod 文件夹路径是：E:\Program Files (x86)\StarCraft II\Mods\MyCampaign.SC2Mod，请完成项目初始化。
```

智能体应直接运行：

```powershell
python tools/init-project.py "E:\Program Files (x86)\StarCraft II\Mods\MyCampaign.SC2Mod"
```

该命令一次完成：

1. 验证目标是包含 `ComponentList.SC2Components` 的 `.SC2Mod` Components 文件夹。
2. 从主 Mod 路径向上寻找 `Mods`，推导 StarCraft II 安装目录和 `Maps/Campaign`；主 Mod 位于 `Mods` 子目录时也可识别。
3. 读取主 Mod 的 info 组件并递归检查全部本地依赖 Mod，包括依赖的依赖。
4. 仅在路径和依赖检查通过后，原子写入 `agent-config.json`。

用户无需手工编辑 JSON，也无需列出依赖。若只预览结果而不写入配置，使用 `--dry-run`。非标准目录布局可由智能体按命令提示补充 `--mods-dir`、`--sc2-install-dir` 或 `--campaign-maps-dir`。

初始化只负责路径、主 Mod 和依赖图。Bank 名称、Library ID、脚本块和代码前缀无法仅凭文件夹路径可靠推断；智能体必须在初始化后核对 `AGENTS.md` 的“模组身份”，发现不一致时报告并依据项目证据更新，不能沿用或猜测旧项目身份。

---

## 可直接复制的对话示例

### 示例 1：标准布局下初始化现有项目

```text
主 Mod Components 文件夹路径是：
E:\Program Files (x86)\StarCraft II\Mods\MyCampaign.SC2Mod

请直接运行 tools/init-project.py 完成项目初始化，递归解析本地依赖，
然后运行 validate-agent-config.py。请报告最终解析出的 workspace、SC2、Mods、
campaign maps、primary mod 和依赖数量。不要让我手工编辑 agent-config.json。
```

预期行为：智能体直接运行初始化工具；成功后检查配置与依赖，不会通过枚举 `Mods/` 猜测活动依赖。

### 示例 2：先预览，再等待确认

```text
请对 D:\Games\StarCraft II\Mods\MyCampaign.SC2Mod 做项目初始化预览。
使用 tools/init-project.py --dry-run，只检查路径和递归依赖，不写入配置。
告诉我将要修改 agent-config.json 的哪些字段，以及是否有缺失依赖。
```

预期行为：`agent-config.json` 保持不变；智能体展示推导结果和依赖问题。

### 示例 3：切换主 Mod

```text
把当前默认项目切换为：
D:\Games\StarCraft II\Mods\NewCampaign.SC2Mod

请运行初始化工具更新配置，验证递归依赖，并核对新项目的模组身份。
重点检查 Library ID、Compiled Galaxy、Script Block、Bank 名称、
Galaxy 函数前缀和全局变量前缀。不要把旧项目的 libEpi_ 或 Bank 名称直接带过去。
```

预期行为：路径配置由工具更新；身份信息只根据新项目的库 XML、GUI Action Definition 和源码证据确认。

### 示例 4：非标准或跨盘符布局

```text
请初始化这个非标准布局：
- 主 Mod：D:\CampaignSource\MyCampaign.SC2Mod
- Mods 目录：D:\SC2Components\Mods
- SC2 安装目录：C:\Program Files (x86)\StarCraft II
- 战役地图目录：D:\SC2Components\Maps\Campaign

请根据 tools/init-project.py --help 使用 --mods-dir、--sc2-install-dir 和
--campaign-maps-dir。先验证目录关系与递归依赖，再写入配置；说明哪些路径必须保存为绝对路径。
```

预期行为：智能体不会强行套用同级目录布局；跨盘符路径可能保存为绝对路径并产生可移植性警告。

### 示例 5：只验证当前配置

```text
不要修改任何配置。请检查当前 agent-config.json 是否有效：
运行 validate-agent-config.py 和 inspect-mod-dependencies.py，
确认主 Mod、递归本地依赖、缺失项和 engine/network 引用。
```

### 示例 6：临时验证另一个 Mod

```text
保持当前默认项目不变，临时验证：
D:\Games\StarCraft II\Mods\Experimental.SC2Mod

运行 test-suite.py --mod-dir 指向该目录。
请明确报告实际 Target mod，并说明依赖校验范围。
```

预期行为：本次命令覆盖目标，但不会修改 `agent-config.json`。

### 示例 7：依赖缺失时请求诊断

```text
项目初始化报告缺失依赖。请不要使用 --allow-incomplete 绕过。
先运行 inspect-mod-dependencies.py，告诉我缺少哪个本地 .SC2Mod、
由哪个组件声明、声明来自哪个 info 文件，以及它是纯本地依赖还是 engine/network 引用。
```

只有用户明确接受不完整配置，并理解完整预检仍会失败时，才考虑 `--allow-incomplete`。

### 示例 8：尚未保存为 Components

```text
我只有 SC2 编辑器中的项目，没有 .SC2Mod Components 文件夹。
请给我最短的编辑器操作步骤，把 Mod 保存为 Components。
完成后告诉我应该把哪个目录的完整路径发给你进行初始化。
```

预期行为：智能体说明 **File → Save As → Components** 的用户操作，不会尝试把二进制 Mod 当作可编辑目录。

---

## 一、首次安装

### 1. 确认目录

推荐目录结构：

```text
<共同父目录>/
├── StarCraftIIAgent/
│   ├── agent-config.json
│   ├── AGENTS.md
│   ├── skills/
│   ├── tools/
│   └── wiki/
└── StarCraft II/
    ├── Mods/
    └── Maps/Campaign/
```

工作区和 StarCraft II 不必使用以上名称或位于同一磁盘；此结构只是默认配置最方便、配置最便于跨机器复用的布局。

### 2. 选择主 Mod 并自动配置

按本页顶部“一句话完成配置”的方式向智能体提供主 Mod 文件夹路径。以下 JSON 仅用于解释最终配置结构，通常不需要手工编辑。

所有相对路径都以 `agent-config.json` 所在的工作区根目录为基准。

```json
{
  "schema_version": 1,
  "paths": {
    "workspace_dir": ".",
    "sc2_install_dir": "../StarCraft II",
    "mods_dir": "../StarCraft II/Mods",
    "campaign_maps_dir": "../StarCraft II/Maps/Campaign"
  },
  "project": {
    "primary_mod": "MyCampaign.SC2Mod",
    "resolve_dependencies_recursive": true
  },
  "validation": {
    "include_dependencies": true,
    "exclude_mods": []
  }
}
```

字段说明：

| 字段 | 用途 |
|---|---|
| `workspace_dir` | 智能体工作区；通常保持 `.` |
| `sc2_install_dir` | StarCraft II 安装目录 |
| `mods_dir` | 存放 `.SC2Mod` 组件文件夹的目录 |
| `campaign_maps_dir` | 存放战役 `.SC2Map` 组件文件夹的目录；纯 Mod 初始化时尚不存在只会产生警告 |
| `primary_mod` | 相对于 `mods_dir` 的主模组组件目录，包含 `.SC2Mod` 后缀；允许位于 `Mods` 子目录 |
| `resolve_dependencies_recursive` | 是否从主 Mod 开始递归解析所有本地依赖 Mod；初始化时应保持 `true` |
| `validation.include_dependencies` | 预检是否静态验证本地活动依赖的 XML/Galaxy；建议保持 `true` |
| `validation.exclude_mods` | 有意暂缓验证的组件 Mod 文件夹名列表；必须显式记录，避免静默漏扫 |

依赖关系以组件文件中声明的内容为准，不以 `Mods` 目录里有哪些文件夹为准。

### 3. 验证安装

在工作区根目录运行：

```powershell
python tools/validate-agent-config.py
python tools/test-suite.py
```

配置验证应输出解析后的工作区、SC2、Mods 和地图目录，并以 `agent-config.json OK` 结束。预检套件必须显示实际的 `Target mod`、依赖验证目标数量与排除项；如果没有找到模组，它会失败，而不会以零扫描量通过。

如果此时还没有可用的 `.SC2Mod` 项目，请先完成下一节的项目选择，再运行完整预检。

---

## 二、选择已有项目

### 1. 找到组件模组

目标必须是一个已经保存为 Components 的目录，例如：

```text
<mods_dir>/MyCampaign.SC2Mod/
├── Base.SC2Data/
├── ComponentList.SC2Components
├── DocumentInfo
└── enUS.SC2Data/
```

压缩包、单个 `.SC2Mod` 二进制文件或 Editor 尚未保存为 Components 的项目不能直接用于当前文件级工具链。

### 2. 设置主模组

向智能体提供该目录的完整路径，由 `init-project.py` 设置 `project.primary_mod`。生成的配置类似：

```json
"project": {
  "primary_mod": "MyCampaign.SC2Mod",
  "resolve_dependencies_recursive": true
}
```

这里只需选择主 Mod；不要手工抄写直接依赖或传递依赖列表，也不要要求用户手工修改配置。

### 3. 递归识别依赖 Mod

运行：

```powershell
python tools/inspect-mod-dependencies.py
```

工具按以下规则递归解析：

1. 从主 Mod 的 `ComponentList.SC2Components` 找到 `Type="info"` 的组件路径。该文件通常叫 `DocumentInfo`，但以 ComponentList 的实际声明为准。
2. 从 info 组件的 `<Dependencies>` 中读取依赖引用。
3. 对能够解析到 `mods_dir` 下组件目录的 `.SC2Mod` 依赖，继续读取该依赖自己的 ComponentList 和 info 组件。
4. 重复以上过程，直到没有新的本地依赖。
5. 用已访问集合处理循环依赖；同一个共享依赖只展开一次。
6. 战役、内置 Mod 和无法映射为本地组件目录的 Battle.net 引用会标记为 `engine/network`，不会被误报为缺少本地文件。

示意结果：

```text
Main.SC2Mod [primary]
|-- SharedCore.SC2Mod
|   `-- CommonData.SC2Mod
`-- FactionPack.SC2Mod
    `-- CommonData.SC2Mod [shared; already expanded]
```

若纯本地 `file:Mods\*.SC2Mod` 依赖不存在，输出会标记为 `[MISSING]`，配置验证也会失败。可以用 `--json` 获取完整、可机器读取的依赖图。

目录存在只证明依赖文件可读取；Editor 实际加载顺序仍以依赖声明为准。

### 4. 同步项目身份

选择不同项目后，检查 `AGENTS.md` 的“模组身份”表，至少确认以下项目与所选模组一致：

- 战役和模组名称
- Library ID 与编译 Galaxy 文件名
- Script Block 名称
- Bank 名称
- Galaxy 函数和全局变量前缀

旧项目的 `libEpi_`、Bank 名称或数据 ID 前缀不能直接套用到另一个模组。

### 5. 验证选择结果

```powershell
python tools/validate-agent-config.py
python tools/inspect-mod-dependencies.py
python tools/validate-mod.py
python tools/audit-gamestrings-anchors.py
```

确认每条命令打印的目标都是刚选择的 `.SC2Mod`。最后运行完整预检：

```powershell
python tools/test-suite.py --verbose
```

若只想临时检查另一个模组而不更改默认项目，可使用：

```powershell
python tools/test-suite.py --mod-dir "<完整或工作区相对的模组路径>"
```

`--mod-dir` 只覆盖本次命令，不会修改 `agent-config.json`。

使用 `--primary-only` 可临时跳过依赖内容验证；使用可重复的 `--exclude-mod <Name.SC2Mod>` 可在本次运行追加排除项。默认策略仍来自 `agent-config.json`。

---

## 常见错误

| 现象 | 检查项 |
|---|---|
| `No .SC2Mod directory found` | `paths.mods_dir` 是否正确，`primary_mod` 是否包含准确的 `.SC2Mod` 文件夹名 |
| 配置验证提示目录不存在 | 相对路径是否从智能体工作区根目录计算 |
| 递归依赖显示 `[MISSING]` | 查看它由哪个 Mod 声明；安装对应 Components Mod，或在 Editor 中修正过期依赖 |
| `ComponentList has no Type='info'` | 项目是否为完整 Components 目录，ComponentList 是否损坏或尚未由 Editor 正确保存 |
| 验证了错误的项目 | 查看命令输出中的 `Path config` 和 `Target mod` |
| XML/Galaxy 通过但 Editor 报错 | 静态验证不等于 Editor 接受；确认活动依赖并执行 Editor 打开、保存与运行测试 |

## 完成标准

- `agent-config.json` 中的四个路径均能解析到现有目录。
- `primary_mod` 指向预期的 Components 模组目录。
- 递归依赖图中没有缺失的本地组件 Mod 或组件元数据错误。
- `validate-agent-config.py` 通过。
- `test-suite.py` 显示正确的目标；任何剩余失败均作为项目缺陷处理，而不是路径配置问题。
