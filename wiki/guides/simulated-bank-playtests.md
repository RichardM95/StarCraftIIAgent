# 模拟 Bank 游戏测试与夹具配置

本指南用于使用模拟玩家 Bank 状态、解锁树和持久化选择测试战役任务。

---

## 为什么要使用 Bank 夹具测试？

战役任务经常会根据之前的选择表现出不同逻辑，例如已选择的科技升级、已完成任务或阵营选择。只用空白 Bank 测试，容易遗漏升级门槛、条件目标和难度修饰符中的问题。

---

## 配置 Bank 测试夹具

1. **定位 Bank 文件：**
   - Windows：`Documents\StarCraft II\Banks\<BankName>.SC2Bank`，或对应的 OneDrive 目录。
   - macOS：`~/Library/Application Support/Blizzard/StarCraft II/Banks/<BankName>.SC2Bank`。
2. **备份活动 Bank：** 测试前重命名或复制当前玩家 Bank。
3. **放入测试夹具：**
   - 创建代表特定进度阶段的 XML 测试夹具，例如战役中期、全部升级或新游戏。
   - 将夹具 XML 以 `<BankName>.SC2Bank` 名称放入活动 Banks 目录。

---

## 测试验证步骤

1. 在 SC2 编辑器中通过 **Test Document**（`Ctrl+F9`）启动目标任务地图。
2. 确认单位升级、科技解锁和历史选择与 Bank 夹具一致。
3. 完成任务或触发胜利流程。
4. 确认 Bank 文件已写入新的任务完成键。
5. 记录所用夹具、地图、玩家/阵营、难度以及预期/实际结果；不要把一次夹具测试结果推广到未测试的 Bank 状态。
