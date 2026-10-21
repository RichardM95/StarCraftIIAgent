# 项目问题模板

此文件是通用模板，不记录活动问题。需要跨次追踪时按模板写入项目 docs/issues.md，路径用 tools/project-paths.py 查询。

## Issue Template

### ISSUE-001: 问题标题

- **Status:** reported
- **Map / Context:**
- **Reproduction:**
- **Observed:**
- **Expected:**
- **Root Cause:**
- **Fix:**
- **Validation:**
- **Editor Validation:**
- **Runtime Validation:**

`Validation` 记录静态检查的对象、命令/范围与结果。`Editor Validation` 从 `Editor accepted` 起必填，记录受影响组件、重载/编译/保存操作及警告结果；`Runtime Validation` 从 `packaged runtime passed` 起必填，记录运行版本/目标、复现操作与实际结果。未执行的阶段留空并保持相应状态，不用计划步骤代替验收证据。
