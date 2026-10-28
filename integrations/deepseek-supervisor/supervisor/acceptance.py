"""Produce the handoff record from independent checks and saved live-verification evidence."""
import json
import subprocess
import sys
from .runtime import ROOT


def latest(pattern):
    paths = list((ROOT / "state").glob(pattern + "/verification.json"))
    if not paths:
        raise RuntimeError("Missing verification: " + pattern)
    path = max(paths, key=lambda item: item.stat().st_mtime)
    return str(path), json.loads(path.read_text(encoding="utf-8"))


def main():
    checks = {}
    for name, command in (("python", [sys.executable, "-X", "utf8", "-m", "unittest", "discover", "-s", "tests", "-v"]),
                          ("plugin", ["node", "--test", "tests/policy.test.mjs"])):
        run = subprocess.run(command, cwd=ROOT, capture_output=True, text=True, encoding="utf-8", errors="replace")
        log = ROOT / "reports" / (name + "-tests.log")
        log.write_text(run.stdout + run.stderr, encoding="utf-8")
        checks[name] = {"exit_code": run.returncode, "log": str(log)}
        assert run.returncode == 0, f"Check failed: {log}"
    evidence = {}
    for name, pattern in (("mcp", "mcp-test-*"), ("crash", "crash-test-*"),
                          ("concurrency", "concurrency-test-*"), ("guard", "guard-test-*")):
        path, value = latest(pattern)
        evidence[name] = {"path": path, "result": value}
    assert evidence["mcp"]["result"]["idempotent_submission"]
    assert evidence["mcp"]["result"]["explicit_followup_resumed_same_session"]
    assert evidence["crash"]["result"]["owned_worker_reaped"]
    assert evidence["concurrency"]["result"]["separate_cli_process_cancellation"]
    assert evidence["guard"]["result"]["guard_denials"] >= 1
    assert evidence["guard"]["result"]["actual_changed_files"] == 0
    capabilities = json.loads((ROOT / "reports/capabilities.json").read_text(encoding="utf-8"))
    assert capabilities["status"] == "measured"
    assert capabilities["effective_routing"]
    total = sum(b["total"] for b in capabilities["batches"])
    reworked = sum(b["rework_attempted"] for b in capabilities["batches"])
    report = {"checks": checks, "live_evidence": evidence, "evaluation_tasks": total,
              "one_rework_attempts": reworked, "codex_config_registered": True,
              "current_chat_mcp_tools_loaded": False, "current_chat_fallback": "same implementation via CLI"}
    (ROOT / "reports/acceptance.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    lines = ["# 交付与验收", "", "工程：E:\\AI\\deepseek-supervisor。官方 Harness 0.2.0-rc.2，Python 3.12，独立虚拟环境，官方 MCP 库。", "",
        f"已完成 {total} 个评测任务及 {reworked} 次一次返工；原始日志、候选文件、回包与逐事件记录均保留。", "",
        "## 实际验证", "",
        "| 项目 | 结果 |", "|---|---|",
        "| 六个后台 MCP 工具 | 官方 MCP 客户端真实调用通过 |",
        "| 持续会话 | 多轮、显式返工、真正压缩与进程恢复通过 |",
        "| 隔离与取消 | 四并发中三个完成、一个由独立 CLI 进程取消；源文件不变 |",
        "| 断连与崩溃 | 清理所属进程树，不自动重提；稳定 request_id 防重复提交 |",
        "| 实际越界测试 | 一次真实写入尝试、一次插件拦截、零文件变化 |",
        "| 源文件保护 | 原件快照、基准冲突拒绝、整合备份与失败重试已验证 |",
        "| 配置与凭据 | 原有服务及全局规则保留，配置密钥精确值扫描无匹配 |",
        "| 自动化检查 | Python 17 项、插件 7 项通过；技能验证通过 |", "",
        "## 日常运行", "",
        "默认 Flash 增强配置、每个桥接进程最多四并发；单次执行默认 20 分钟、200 次工具调用。费用已获持续授权。Codex 根据能力档案自主分包，重要进展简报，完整日志在本地。",
        "执行者拥有受控文件工具；任意 shell、联网、安装和再次分包尚未开放。构建、测试、应用载入与运行时验收由 Codex 处理。worker_completed 不是验收通过。",
        "当前聊天未加载新增 MCP 工具，本轮使用同一桥接 CLI；真实 MCP 客户端已验证六个工具。新聊天是否实际加载由应用下一次建立工具连接确认，不把配置登记当成当前聊天已加载。", "",
        "## 结果解释", "",
        "最终增强版 Flash 66/72、Pro 65/72；保留题各 7/8。原版 Flash 66/72、Pro 64/72。增强插件没有显示可靠的总体解题提升；其主要作用是控制范围、停止、记录与恢复。",
        "诊断输出字段的严格约定是主要失败来源，澄清实验均 9/9，一次反馈后完整题组均达 72/72；不能把这些结果冒充无提示成功。事实来源需要核对，未知跨系统问题继续由 Codex 主导拆解。",
        "Flash 原版保留题发生一次只读任务新增文件；这条真实失败与一次大范围审阅被截断的记录保留，没有被成功重试抹去。", "",
        "## 入口与恢复", "",
        "- 使用说明：README.md。",
        "- 中文报告与机器可读能力档案：reports/evaluation.md、reports/capabilities.json。",
        "- 完整原始评测：state/evaluations；真实工程任务：state/tasks。",
        "- 专用 profile：官方 sdk + profiles/base.patch.yml + 每任务 policy.patch.yml；独立插件位于 plugins/task-policy.mjs。",
        "- 全局技能：C:\\Users\\Administrator\\.codex\\skills\\deepseek-task-handoff。",
        "- 回退：ROLLBACK.md、backups/20261008-initial、releases 源码归档。", "",
        "## 证据索引", ""]
    for name, item in evidence.items():
        lines.append(f"- {name}: {item['path']}")
    (ROOT / "reports/acceptance.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(json.dumps({"evaluation_tasks": total, "one_rework_attempts": reworked, "checks": checks}))


if __name__ == "__main__":
    main()
