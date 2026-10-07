# 外部路径与机器本地配置

保持仓库内容可移植。不要提交绝对路径、账户名或机器专属的《星际争霸 II》位置。

默认项目布局定义在 `agent-config.json`。路径应尽量相对于工作区根目录；当前配置将本工作区映射到 `../StarCraft II`、其 `Mods` 目录和战役地图目录。配置只指定主模组；本地依赖模组通过每个组件的 ComponentList 和 info 组件递归发现。

## 单次路径覆盖

需要单次覆盖的工具接受显式命令行路径或可选环境变量：

- `SC2_MODS_PATH`：本机《星际争霸 II》`Mods` 目录。
- `SC2_PRIMARY_MOD`：覆盖主组件名称。
- `SC2_GAMELOGS_PATH`：本机游戏测试日志目录。

机器专属的绝对值应放在环境变量中，不要写入已提交的 XML、Galaxy 脚本或设置文件。

## 解析顺序

校验与部署源的发现顺序为：

1. 显式 `--mod-dir` / `--source`
2. `agent-config.json`
3. 环境变量后备
4. 同级目录布局自动发现

`python tools/test-suite.py` 会打印配置文件和解析后的实际目标；找不到目标时会失败。依赖扫描默认值来自 `validation.include_dependencies` 和 `validation.exclude_mods`；单次只校验主模组可使用 `--primary-only`。

完整部署参数请运行 `python tools/deploy-mod.py --help`。多电脑配置参阅[多电脑配置指南](../guides/multi-pc-setup.md)。
