# Shared local tools, MCP and skills

[中文](shared-tools.md)

Existing tools own established workflows. Local commands and MCP share the added implementation; skills select tools, review candidates and define acceptance. See the [routing skill](../../skills/sc2-shared-tools/SKILL.md), [capability map](../../integrations/CAPABILITIES.json) and [skill merge record](../../integrations/SKILL-MERGE.json).

## Install and diagnose

Use Python 3.12 or newer. The installer creates two isolated environments and uses locked dependencies; an explicit package index is supported.

```powershell
python tools/sc2-integration.py --ui-language en install --index-url https://pypi.org/simple
python tools/sc2-integration.py --ui-language en configure
python tools/sc2-integration.py --ui-language en diagnose
python tools/sc2-integration.py --ui-language en register
```

`configure` discovers Harness or accepts `--harness-exe` and `--harness-cli`. Settings live in `%LOCALAPPDATA%/StarCraftIIAgent/integrations.json`; `SC2_AGENT_INTEGRATION_CONFIG` overrides that location. Harness owns credentials. The diagnostic checks file presence without copying or reading credential contents.

`register` adds the global `sc2-editor`, `deepseek-supervisor` and thin skill entry, preserving other settings and backing up the configuration. Identical registration is repeatable; different content under an existing name is a conflict. `unregister` removes only entries still matching the registration record and retains code, environments and runtime evidence. A client reconnect is required; registration alone does not prove the current chat loaded the tools.

## Capability ownership

| Task | Default entry |
|---|---|
| Effective Catalog values, GUI triggers, string anchors | Existing Catalog, trigger and localization tools |
| Terrain and unit migration | Existing terrain and migration tools, with their own evidence boundaries |
| Official skins, models and asset chains | Official-assets skill and shared implementation |
| Map shell, regional environment, editor warnings | Shared diagnostics and candidate tools |
| Candidate review, commit and recovery | One shared transaction entry throughout the change |
| DeepSeek SC2 sub-tasks | Connected MCP, otherwise a managed CLI process |
| Keystone-specific mechanics | Not exposed as generic workspace operations |

Prefer connected MCP for supplementary capabilities; when unavailable use the same implementation through CLI. A business rejection requires diagnosis rather than a transport change. Query uncertain task/transaction submissions before retrying.

## Local calls

```powershell
python tools/sc2-local.py --ui-language en capabilities
python tools/sc2-local.py --ui-language en tools
python tools/sc2-local.py --ui-language en call sc2_project_open --arguments-file open.json
```

`open.json` identifies an explicit target and never silently selects another project's LoyalWOL:

```json
{"path":"<absolute-components-path>","writable":false,"search_roots":["<absolute-sc2-installation>"]}
```

Use the returned project_id for `sc2_official_assets_search`, `sc2_validate_map_shell`, `sc2_validate_data_warnings` and other investigations. `tools --operation <operation>` emits one current parameter schema. Use JSON files for multiline or shell-sensitive input.

CLI and MCP share business functions and parameter validation and return `ok/result`. CLI failures return `ok:false/error`; exit codes are 0 for success, 1 for business rejection and 2 for invalid requests. A CLI process owns and waits for its long jobs and can run in a managed exec session; MCP exposes job IDs for polling. Business results and acceptance rules are shared while delivery timing may differ.

Global runtime indexes and process slots live under the suite's `.runtime/integrations/`, avoiding Windows packaged-app AppData write redirection. Project candidates, reports, transactions and DeepSeek tasks live under `runtime/integrations/` in project data resolved by `sc2_paths`. Independent test maps inside the workspace use a target-fingerprinted project directory in suite data. Explicit CLI `--state` or the testing override `SC2_AGENT_RUNTIME_ROOT` isolates state without migrating historical records.

## DeepSeek

```powershell
python tools/deepseek-task.py --ui-language en diagnose
python tools/deepseek-task.py --ui-language en capabilities
python tools/deepseek-task.py --ui-language en models
python tools/deepseek-task.py --ui-language en run --packet task.json
python tools/deepseek-task.py --ui-language en status <task-id>
python tools/deepseek-task.py --ui-language en result <task-id>
python tools/deepseek-task.py --ui-language en cancel <task-id>
```

Packets specify a stable request_id, explicit workspace, input_files, allowed_files, goal, constraints, acceptance and `profile:"sc2"`. Models are selected from saved Harness provider settings, with at most four tasks across entry points and a 1200-second task timeout. CLI and MCP share the project task index, request deduplication, cancellation and process-slot locks. Exiting does not automatically resubmit work.

The primary agent establishes root cause, target and acceptance. Automatic delegation covers bounded sub-tasks within authorized SC2 work; other domains require an explicit request. Workers modify isolated candidates only. The file bridge reads selected data or plans candidates but cannot commit source changes. Actual diffs, conflicts, bridge events and candidate hashes require independent review.

Prefer importing SC2 source changes through `sc2_changes_prepare`. Other explicitly allowed files can use `integrate --review-note` or `integrate_task`. Generated Galaxy, publish paths, changed sources and competing integration are rejected. Deletion candidates require a separate plan and are not automatically integrated.

Historical capability evaluations are versioned references. A local diagnostic does not establish Harness login, model availability or map acceptance; real tasks and application evidence are checked separately.

## Acceptance and maintenance

Shared Dispatcher/Manager code owns parameters, protections and results for both transports. Global skills locate this workspace without changing existing Hub ownership. Run affected tests when changing implementation, plus the existing tools/docs scopes for tooling and documentation.

Shared transactions and worker integration protect generated MapScript/Lib Galaxy and publish edits. Report static validation, Editor save/reopen, packaged runtime and visual results according to evidence. Without Editor or game evidence, the highest applicable conclusion is `static validation passed`.

## Custom and local models

Use `models` to list saved route/model IDs. This changes the supervisor default without editing the Harness Models page:

```powershell
python tools/sc2-integration.py --ui-language en configure --provider <provider-id> --model <model-id>
```

Task JSON `provider` and `model` override defaults. Submission persists the effective selection so continuation cannot silently switch when defaults change. The SDK reads the corresponding `llm-pi-ai` definition from the saved desktop provider patch, including its configured protocol. Use `--provider-config` for another profile and `--credentials-file` for another credential store. Credential values are not read by the integration; endpoints stay out of repository files and model task packets. Only custom models advertising reasoning receive an effort parameter.

The integration lock pins NumPy 2.5.4 and retains the original upstream lock as provenance. Run `python tools/sc2-integration.py --ui-language en smoke` for a real connection check; `--with-deepseek` submits an isolated fixture task and consumes the selected model's allowance.

The launcher uses the normal interpreter with `-E -S` and the selected environment's site-packages, preserving dependency isolation while avoiding Windows venv-redirector directory restrictions. CLI, MCP and the file bridge share this launcher.

<!-- translation-source: wiki/guides/shared-tools.md; sha256: f2056af5001a8ea409066c30272a38555bcb76fc3a3d354adde8814b49460c1f -->
