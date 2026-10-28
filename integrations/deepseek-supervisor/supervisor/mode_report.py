"""Rebuild descriptive preset results from immutable case evidence."""
import argparse
from collections import Counter
import json
import statistics
from pathlib import Path

from .runtime import ROOT
from .mode_evaluate import MODES, CATEGORIES

LABELS = {'standard': '标准', 'minimal': '极简', 'ptc': 'PTC', 'cordis': '创造'}
CATEGORY_LABELS = dict(zip(CATEGORIES, ('代码定点修改', 'XML 精确修改', '事实提取', '多文件诊断', '短程记忆', '指令范围')))


def load_case(path, review=None):
    record = json.loads(path.read_text(encoding='utf-8'))
    events = [json.loads(line).get('params', {}).get('event', {})
              for line in (path.parent/'events.jsonl').read_text(encoding='utf-8').splitlines()]
    calls = [block for event in events if event.get('type') == 'assistant/message'
             for block in event['data']['message']['content'] if block.get('type') == 'tool-call']
    record['model_tool_calls'] = len(calls)
    record['model_tool_names'] = dict(Counter(c['name'] for c in calls))
    record['case_id'] = path.parent.name
    accepted = set((review or {}).get('accepted_rubric_failures', []))
    if accepted - {'wrong_fact:items', 'wrong_fix_or_collateral_code_change', 'exact_bytes_mismatch'}:
        raise ValueError('Review cannot waive runtime or scope failures')
    remaining = [f for f in record['failures'] if f not in accepted]
    record['reviewed_passed'] = not remaining
    record['answer_or_target_passed'] = not any(f != 'out_of_scope_file_change' for f in remaining)
    record['cache_only_extra_changes'] = bool(record['outside_changes']) and all(
        name.startswith('__pycache__/') for name in record['outside_changes'])
    record['result_path'] = str(path)
    return record


def summarize(records):
    return {
        'n': len(records),
        'final_artifact_passed': sum(r['passed'] for r in records),
        'reviewed_passed': sum(r['reviewed_passed'] for r in records),
        'answer_or_target_passed': sum(r['answer_or_target_passed'] for r in records),
        'final_outside_change_tasks': sum(bool(r['outside_changes']) for r in records),
        'cache_only_extra_change_tasks': sum(r['cache_only_extra_changes'] for r in records),
        'guard_denied_calls': sum(r['denied_calls'] for r in records),
        'runtime_exception_tasks': sum(r['error'] is not None for r in records),
        'tool_error_tasks': sum(bool(r['tool_errors']) for r in records),
        'median_seconds': round(statistics.median(r['seconds'] for r in records), 2),
        'median_model_tool_calls': statistics.median(r['model_tool_calls'] for r in records),
        'median_audited_tool_calls_including_nested': statistics.median(r['tool_calls'] for r in records),
        'median_total_tokens': statistics.median(r['usage']['totalTokens'] for r in records),
        'total_usage': {k: sum(r['usage'][k] for r in records)
                        for k in ('inputTokens', 'outputTokens', 'cacheReadTokens', 'totalTokens')},
        'failure_counts': dict(Counter(f for r in records for f in r['failures'])),
        'categories': {c: {'n': len(part), 'passed': sum(r['passed'] for r in part),
                           'answer_or_target_passed': sum(r['answer_or_target_passed'] for r in part)}
                       for c in CATEGORIES if (part := [r for r in records if r['category'] == c])},
    }


def main(name):
    batch = ROOT/'state/mode-evaluations'/name
    manifest = json.loads((batch/'manifest.json').read_text(encoding='utf-8'))
    review_path = batch/'supervisor-review.json'
    reviews = json.loads(review_path.read_text(encoding='utf-8')) if review_path.exists() else {}
    records = [load_case(p, reviews.get(p.parent.name)) for p in sorted(batch.glob('*/result.json'))]
    if len(records) != manifest['expected_tasks']:
        raise ValueError(f'Incomplete batch: {len(records)}/{manifest["expected_tasks"]}')
    models = manifest['models'].split(',')
    groups = {model: {mode: summarize([r for r in records if r['model'] == model and r['mode'] == mode])
                      for mode in MODES} for model in models}
    archive = {'schema_version': 1, 'batch': str(batch), 'manifest': manifest, 'groups': groups,
               'interpretation': 'Descriptive six-task comparison, three repetitions per task; not a calibrated production routing profile.',
               'whole_execution_scope_compliance': 'not fully measured',
               'external_filesystem_changes': 'not independently monitored',
               'supervisor_review': reviews,
               'cases': [{k: r[k] for k in ('case_id', 'mode', 'model', 'category', 'repeat', 'passed',
                           'answer_or_target_passed', 'reviewed_passed', 'failures', 'outside_changes', 'tool_calls',
                           'model_tool_calls', 'model_tool_names', 'denied_calls', 'result_path')} for r in records]}
    (ROOT/'reports/modes.json').write_text(json.dumps(archive, ensure_ascii=False, indent=2), encoding='utf-8')
    lines = [
        '# 官方 Harness 四种模式对照', '',
        '本轮比较的是标准、极简、PTC、创造四种 Agent 组合，不是推理强度。固定官方 Harness 0.2.0-rc.2、high，分别使用 Flash 与 Pro。', '',
        f'自动检查加逐例评分歧义复核后，{sum(r["answer_or_target_passed"] for r in records)}/{len(records)} 份答案或目标修改满足本轮短题要求；但 {sum(bool(r["outside_changes"]) for r in records)} 次执行留下额外文件，均为 Python 缓存。没有证据据此选出稳定的能力胜者；更值得关注的是验证动作的副作用和回包是否如实披露。', '',
        '每种模型 × 模式完成 6 类各 1 道题、每题 3 次独立会话重复，共 144 次。没有自动返工；单次会话内部自行纠错算在首次执行中。题目较短且重复相关，结果是描述性小样本，不能证明复杂项目的可靠性或总体智力排名。', '',
        '## 实际构成与接入验证', '',
        '| 模式 | 原生差别 | 本轮验证 |', '|---|---|---|',
        '| 标准 | 完整编程提示、文件工具、Shell、计划、压缩等 | 实际 preset 事件、请求头及文件/Shell 调用 |',
        '| 极简 | 简短提示，Windows 下只有持久 PowerShell；无自身压缩插件 | 请求头只有 pwsh；完成同题 |',
        '| PTC | 通过 run_code 程序组合工具调用 | 请求头只有 run_code，保留内部工具事件 |',
        '| 创造 | 标准类能力加 Cordis 检查及插件创作工具/技能 | 实际 preset 与工具注册；未评测真实插件开发 |', '',
        'SDK 本身不自动绑定桌面模式。本轮使用安装包原样 preset 声明，补齐桌面 host 服务，并在首轮前通过官方 preset API 绑定会话。不是将普通 SDK 改个模式名称；每个结果保留 selected_presets、presented_tools 与 effective_config。', '',
        '## 结果', '',
        '“原始严格通过”要求答案/目标文件符合隐藏标准、代码与 XML 字节完全匹配，且副本最终没有额外文件变化。“复核后通过”只纠正题面未明确要求而被隐藏标准拒绝的项目，理由逐例保留，不豁免越界与运行失败。“答案/目标正确”单独排除额外文件这一失败项。这些分数均不代表全程所有动作合规。', '',
        '| 模型 | 模式 | 原始严格通过 | 复核后通过 | 答案/目标正确 | 有额外文件变化 | 中位秒数 | 中位模型工具调用 | 中位总 tokens |',
        '|---|---|---:|---:|---:|---:|---:|---:|---:|',
    ]
    for model, modes in groups.items():
        for mode, g in modes.items():
            lines.append(f'| {model} | {LABELS[mode]} | {g["final_artifact_passed"]}/{g["n"]} | {g["reviewed_passed"]}/{g["n"]} | {g["answer_or_target_passed"]}/{g["n"]} | {g["final_outside_change_tasks"]} | {g["median_seconds"]} | {g["median_model_tool_calls"]} | {g["median_total_tokens"]} |')
    lines += ['', '耗时包括后台初始化；记忆题含六轮调用，因此总表只适合同题组粗略比较。tokens 为官方事件返回累计量，含缓存读取，不等于收费金额。模型工具调用与底层审计调用分开保存：PTC 的外层 run_code 加内层 read/edit 不能与一次 Shell 命令直接当作等量操作。', '',
              '### 原始严格分类通过数', '', '| 模型 / 模式 | ' + ' | '.join(CATEGORY_LABELS.values()) + ' |',
              '|---|' + '---:|'*len(CATEGORIES)]
    for model, modes in groups.items():
        for mode, g in modes.items():
            lines.append('| ' + model + ' / ' + LABELS[mode] + ' | ' + ' | '.join(f'{g["categories"][c]["passed"]}/3' for c in CATEGORIES) + ' |')
    lines += ['', '## 失败与工具故障', '']
    for r in records:
        if not r['passed']:
            lines.append(f'- `{r["case_id"]}`：{", ".join(r["failures"])}；额外变化：{", ".join(r["outside_changes"]) or "无"}。')
    lines += ['', f'正式批次有 {sum(r["error"] is not None for r in records)} 个运行异常任务，{sum(bool(r["tool_errors"]) for r in records)} 个任务出现过工具报错，审计共拦截 {sum(r["denied_calls"] for r in records)} 次调用。可恢复的工具报错与最终任务失败分别记录；全部工具错误原文保存在 result.json。', '',
              '## 评分和环境边界', '',
              '- 上线前的 pilot-modes-v1 至 v4 保留作接入诊断，不混进正式能力分数。v1 未绑定模式；v2/v3 发现缺失 host 服务及 Windows ACL `SetNamedSecurityInfoW / Win32 5` 错误；v5 四模式真实检索全部通过。',
              '- 本机原生 workspace-write ACL 初始化失败，故正式比较统一使用测试专用 danger-full-access，保留相同的任务范围约定和审计 guard。生产 profile 未改变。这个 guard 不是完整安全沙箱，原生 Shell 和 PTC 直接 Node API 不受完整路径拦截。',
              '- 文件变化计数仅覆盖一次性工作副本最终状态。不能据此宣称外部文件零变化，也不能排除临时写入后恢复。拦截次数不等于全部越界尝试；无拦截更不等于无违规。',
              '- Shell guard 拒绝 Remove-Item 等删除命令，部分模型想清理自己生成的缓存时被拒；PTC 的直接 Node 文件 API 可以绕过这层命令检查。因此同一审计策略并不构成等强访问隔离，较少残留文件不能直接解释为更守规矩。题面本身也要求不作额外 cleanup。',
              '- 记忆题为四轮短干扰后的事实回忆，没有触发长上下文压缩，也没有进程恢复。不能用它证明长期不忘事。之前受控 SDK 的压缩恢复测试另见 evaluation.md。',
              '- 本轮禁止联网、安装插件和递归分包。因此没有覆盖创造模式的专长，也没有覆盖复杂工程构建或自主长任务。',
              '- 报告真实性只对 supervisor-review.json 中列出的案例作人工证据核对；未逐条审阅所有成功回包，不提供未经验证的整体虚报率。', '',
              '## Codex 复核记录', '']
    if reviews:
        for case_id, review in reviews.items():
            lines.append(f'- `{case_id}`：{review["finding"]}')
    else:
        lines.append('尚无独立回包声明核对；不能将产物通过率当作报告可信度。')
    lines += ['', '## 日常分工与复现', '',
              '这批样本不足以升级任何模式为无监督执行者。日常继续使用已有受控 SDK＋增强插件及原能力档案，原生模式仅按探索性配置使用并检查实际产物。标准可作为常规交互的起点；极简提示少但把文件操作交给 Shell；PTC 适合值得组合调用的任务，简单题未必占优；创造用于 Harness/Cordis 扩展需求，不因名称推定更强。具体选择以本表表现和任务工具需求为准。', '',
              '复现（每次使用新批次名；不复用旧目录）：', '', '```powershell',
              '.\\.venv\\Scripts\\python.exe -X utf8 -m supervisor.mode_evaluate --name 新批次名 --repeats 3',
              '.\\.venv\\Scripts\\python.exe -X utf8 -m supervisor.mode_report --name 新批次名', '```', '',
              f'正式原始记录：`{batch}`。模式声明的安装来源和 SHA-256：`state/mode-inspection/manifest.json`；每批次 manifest 固定源码哈希；本批执行入口的逐字节副本为 `releases/mode_evaluate-native-v1.py`。当前入口另外增加已有批次拒绝检查，防止旧结果混进新清单。机器可读报告：`reports/modes.json`。本轮没有更改官方安装包、生产模型、生产权限或旧能力档案。']
    (ROOT/'reports/modes.md').write_text('\n'.join(lines)+'\n', encoding='utf-8')
    print(json.dumps({'tasks': len(records), 'groups': groups}, ensure_ascii=False))


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--name', required=True)
    main(parser.parse_args().name)
