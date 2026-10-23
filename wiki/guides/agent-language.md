# 使用语言与个人偏好

[English](agent-language.en.md)

智能体使用层支持简体中文与英文。中文页提供 English 链接，英文页提供中文链接。深层 API、原始游戏数据与第三方文件保留原文；智能体按使用者语言解释，引用时注明原文语言。技能不复制，名称与规则来源保持一致。

## 对话语言

按以下顺序选择：用户明确的语言指令 → 固定个人偏好（zh-CN 或 en）→ 当前用户的自然语言 → 环境默认语言。保存的 auto 不固定对话语言。代码、路径、对象 ID 和引用中的英文不触发语言切换；“本次用英文回答”仅临时改变当前对话，只有明确要求保存才运行设置命令。

智能体首次需要偏好时运行 `python tools/agent-language.py --json`，读取偏好文件中的 `ui_language` 判断是否固定。偏好无效时报告具体路径与修复方法；明确指定语言可以绕过损坏偏好。不能从工具的环境回退结果推断用户已固定语言。调用其他工具时显式传入当前选定的 `--ui-language`。

## 命令行与保存偏好

CLI 优先级为 `--ui-language` → `SC2AGENT_UI_LANGUAGE` → 个人偏好 → 自动识别。显式 auto 使用 LC_ALL、LC_MESSAGES、LANGUAGE、LANG 中首个设置值，其次 Windows 用户显示语言，最后系统 locale。中文环境均映射为 zh-CN，其余语言回退 en。

```powershell
python tools/agent-language.py
python tools/agent-language.py --set en
python tools/agent-language.py --set zh-CN
python tools/agent-language.py --set auto
python tools/sc2-catalog-query.py --ui-language en --no-auto-rebuild stats
python tools/sc2-catalog-query.py --ui-language zh-CN --locale enUS --no-auto-rebuild stats
```

无参数或 --json 只读显示有效语言、选择来源、保存的偏好及偏好路径，不创建文件。只有 --set 写入。默认位置为 `%LOCALAPPDATA%/StarCraftIIAgent/preferences.json`；非 Windows 无 LOCALAPPDATA 时使用 `~/.config/StarCraftIIAgent/preferences.json`。`SC2AGENT_PREFERENCES_FILE` 可指定独立文件，适合测试或便携环境。偏好属于个人，不写 agent-config.json，不提交到仓库。保存时保留其他有效 JSON 字段；损坏文件可用 --set 显式修复。

## 数据与兼容性

`--ui-language` 仅改变工具自有的人类帮助、摘要和提示。JSON/XML 字段、规范错误文本、状态、退出码和原始数据保持原格式；底层运行时或系统错误保留原文，并配本地化摘要。纯机器输出不会加入语言横幅。原生工作进程协议不变。

SC2 `--locale enUS|zhCN` 单独控制数据语言，与界面语言无关。不修改本地化文件或项目配置；个人偏好与界面语言不进入索引输入清单，也不因切换界面语言重建索引。工具对子进程传递有效界面语言并使用 UTF-8；测试中的旧英文断言固定为 en。

对话示例：用户说“Explain Unit:Marine in English for this reply”，智能体本次用英文并传 --ui-language en；之后用户说中文，若没有固定偏好则用中文。用户说“以后固定用英文”，才运行 --set en。示例不代表任何真实编辑器或游戏验收。
