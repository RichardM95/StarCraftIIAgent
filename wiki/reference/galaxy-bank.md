# Bank 接口参考边界

Bank 的项目名、玩家、键及读取/保存顺序来自当前源码；工作流见 [Bank 技能](../../skills/sc2-bank-system/SKILL.md)。

## GUI 定义与 Galaxy 签名

[B 函数索引](triggers-native/b.md)提供提取到的 GUI 定义及参数，包括 BankPreload、BankLoad、BankLastCreated、BankSave、BankKeyExists、BankValueGetAsInt 和 BankValueSetFromInt。例如 GUI BankLoad 是带 name、player 的动作，读取其结果另有 BankLastCreated；不能把该 GUI 表直接改写成返回 bank 的同名 Galaxy 调用。

编写 GUI 时通过 `tools/sc2-trigger-query.py` 查询目标加载的定义、参数与默认值。维护 Galaxy 时再核对实际 native 声明或编辑器生成调用，保留大小写和完整参数。这里不维护第二份未经编译验证的函数签名表。

旧文档的 `BankValueGetInt`、`BankValueSetInt` 与单参数 `BankPreLoad` 示例已删除，不能据其构造新脚本。GUI 优先是本工作区的编写策略；没有证据证明直接 native 无法读写真实 Bank，不将此前“只能 GUI”说法作为引擎限制。

## 验证

键缺失与保存的零/空值应分开判断；写值后核对保存动作及后续重载。变量看似清零不证明磁盘 Bank 被删除，按[调查流程](../implementation/bank-system.md)区分加载、应用与转场问题。实际存放目录以当前玩家环境和真实文件为准。
