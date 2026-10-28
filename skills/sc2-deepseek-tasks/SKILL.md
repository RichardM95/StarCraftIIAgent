---
name: sc2-deepseek-tasks
description: Delegate bounded SC2 sub-tasks to Harness-configured models, including DeepSeek or local model services, then review actual candidates and independently validate before integration.
---

# SC2 model sub-tasks through Harness

Follow [shared-tool routing](../sc2-shared-tools/SKILL.md) and the [task guide](../../wiki/guides/shared-tools.md#deepseek). Automatic delegation is authorized only for bounded SC2 sub-tasks. Other domains require an explicit user request. The user can stop or narrow delegation at any time.

The primary agent owns uncertain root causes, architecture, target selection and acceptance. Delegate a concrete independent task after those boundaries are clear. Read current capability evidence; historical evaluations do not certify this Harness/model installation.

Use `models` (or MCP capabilities) to discover saved Harness provider/model IDs without exposing endpoints or keys. The default comes from local settings; a packet may override `provider` and `model`. Custom provider definitions are read from the saved Harness profile and materialized only outside the worker directory. Unsupported reasoning effort is omitted; historical evaluation does not transfer to a new route.

Write a JSON packet with a stable request_id, explicit workspace, input_files, allowed_files, goal, constraints, acceptance and `profile:"sc2"`. Include the target's relevant rules and only required files. New triggers retain GUI-first/source boundaries. Credential values never enter the packet. Avoid unrelated refactors.

Prefer connected `deepseek-supervisor` submit/status/result/cancel tools. Otherwise run `python tools/deepseek-task.py --ui-language <language> run --packet <file>` in a managed exec session; that command owns the worker until completion. Other CLI processes can query or cancel the same task. Do not detach unowned jobs. Reuse request_id to query a duplicate/uncertain submission; reconnecting does not authorize a new run. Use explicit followup only with unchanged scope.

The worker can inspect selected SC2 data through its restricted file bridge and create isolated repair candidates; it cannot apply, export or bypass native terrain/source boundaries. It cannot claim compiler, Editor or game execution merely from a text response.

Inspect task_result actual changes, allowed-file flags, baseline/candidate hashes, source conflicts and bridge events. Run independent checks on the candidate. For SC2 source changes prefer `sc2_changes_prepare` followed by the normal inspect/apply transaction; for other explicitly allowed files use reviewed `integrate`/`integrate_task`. Integration rejects generated Galaxy, publish paths, changed sources and competing writes. A worker_completed state is not acceptance. Do not blindly repeat a failed task or increase its scope.
