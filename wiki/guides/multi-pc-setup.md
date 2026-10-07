# 多电脑配置与同步指南

用于在多台台式机、笔记本或开发环境之间协作开发自定义战役。

---

## 1. 绝对路径与相对路径

- **仓库资源保持相对路径：** 不要在 XML layout 模板、catalog include 或 Galaxy 脚本中硬编码用户主目录（`C:\Users\<Name>\...`）。
- **项目路径配置：** `agent-config.json` 优先使用相对工作区的路径。单机可以使用跨盘符绝对路径，但换到另一台电脑后必须重新运行 `tools/init-project.py` 生成配置。
- **SC2 环境变量：** 机器专属目录可使用可选环境变量：
  - `SC2_MODS_PATH`：本机《星际争霸 II》`Mods` 目录，例如 `C:\Program Files (x86)\StarCraft II\Mods`。
  - `SC2_GAMELOGS_PATH`：本机游戏测试 `GameLogs` 目录。

---

## 2. Git 卫生与换行符

- 确认 `.gitattributes` 为 XML、Galaxy、Layout 和 Bank 文件规定标准 LF 换行。
- 不要提交 `publish/` 或生成的 `sc2-catalog-graph-out/` 目录。
- 推送提交前始终运行 `python tools/test-suite.py`，确保跨机器一致性。

---

## 3. SC2 编辑器依赖

- 将仓库同步到第二台电脑后，确认 SC2 编辑器能够找到项目的 `.SC2Mod` 组件目录。
- 在第二台电脑上运行 `python tools/init-project.py "<主模组.SC2Mod 路径>"`，重新生成本机路径配置并验证递归依赖。
- 如果工作区中的源模组与 SC2 `Mods` 目录不同，先运行 `python tools/deploy-mod.py --dry-run` 核对目标，再执行实际部署。源与目标相同时不需要复制。
