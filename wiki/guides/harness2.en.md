# Project-local Harness2 installation

[中文](harness2.md)

The [official repository](https://github.com/google-research/harness2) provides a command-line research framework for recursive agent harness improvement. Sources live in `integrations/harness2/`; see the [installation provenance](../../integrations/harness2.agent.json) for the pinned revision, license and source archive checksum. Upstream instructions and generated harnesses do not override this workspace's AGENTS, Skills or project settings.

## Run

### Rebuild on a new machine

Git distributes source and dependency lists, without an installed Python/WSL, `.venv-linux`, `.runtime`, authentication or experiment output. Prepare Linux or WSL with access to the clone (default distribution name `Ubuntu-22.04`) and `uv`. In a **Linux/WSL terminal**, change to the clone's `integrations/harness2/` directory and run:

```bash
uv venv --python 3.12 .venv-linux
uv pip install --python .venv-linux/bin/python -r requirements.agent.lock
uv pip install --python .venv-linux/bin/python --no-deps -e .
```

This downloads the local runtime/dependencies and requires network access to their sources. Return to the workspace root for the demo/tests below. Real SC2 optimization additionally needs the installed Codex CLI authenticated with ChatGPT; run `codex-configure` and `codex-probe`. The probe makes a real model call. Global thin entries or MCP registration are not prerequisites for this research framework.

Upstream requires Linux. On Windows, use an installed `Ubuntu-22.04` WSL distribution or select another with `--distro`. The isolated environment is `integrations/harness2/.venv-linux/`; existing installations may store Python 3.12 in `.runtime/harness2/python-linux/`. Environment activation and reuse of the maintainer's runtime path are unnecessary.

From the workspace:

```powershell
python tools/harness2.py --ui-language en demo --k 2
python tools/harness2.py --ui-language en test
python tools/harness2.py --ui-language en run --help
python tools/harness2.py --ui-language en setup lab --dry-run
```

The demo uses deterministic editors and real Python subprocesses to exercise both parallel and sequential recursion, without models or credentials. Its default report is `.runtime/harness2/demo/demo.json`; `--output` accepts a Linux path. Reusing an output directory resumes existing state; use a different directory for an independent experiment.

Commands are `demo`, `run`, `setup`, `check`, `judge`, `report`, `bridge` and `test`. Following arguments pass through to upstream. `--distro` selects another installed WSL distribution, which must still have access to this workspace and runtime. The UI language controls wrapper help; upstream output is preserved.

## Models and benchmarks

This installation includes the core package and upstream `render` dependencies. Install JobBench, LAB or WorkBuddy data, Node/Bun executors, Google Cloud CLI, Docker and optional model bridge dependencies only for the chosen workflow; inspect `setup <bench> --dry-run` first. See the [official setup guide](https://github.com/google-research/harness2/blob/main/docs/SETUP.md) for model benchmark prerequisites. WSL needs network access to the required downloads and model endpoints.

Put user model settings in the ignored `integrations/harness2/.env`, never in source or provenance files. Upstream provides Vertex settings and supports a Responses API endpoint for the Codex executor. The existing DeepSeek Harness Anthropic Messages route cannot be assumed to provide that API.

The SC2 adapter additionally supports the installed Windows Codex CLI with its existing ChatGPT login. Its model follows the user's Codex configuration; the current selection is `gpt-6.1-sol`. It uses the Codex-managed connection without a new Responses API key, authentication-file copies or DeepSeek Harness credentials. Existing MCP configuration is preserved.

## Real Codex and SC2 Skill improvement

```powershell
python tools/harness2.py --ui-language en codex-configure
python tools/harness2.py --ui-language en codex-probe
python tools/harness2.py --ui-language en sc2-optimize
python tools/harness2.py --ui-language en sc2-finalize "<experiment-directory>"
python tools/harness2.py --ui-language en sc2-apply "<experiment-directory>"
python tools/harness2.py --ui-language en sc2-restore "<experiment-directory>"
```

Local settings use the ignored `.runtime/harness2/codex.json`; experiments use `.runtime/harness2/sc2-runs/`. `codex-configure` reads the CLI model selection and checks ChatGPT login. Reconfigure after changing the CLI default model and start a new experiment; do not resume an experiment under a different model.

Windows Codex owns real model connectivity while WSL runs Harness2 orchestration. The SC2 adapter fixes the sandbox to `read-only`, approvals to `on-request` and output to a structured schema. It skips user tool configuration and disables shell, hooks, plugins, connectors, browsers and subagents. The model submits localization operations or a narrowly allowed Skill body; trusted code checks them and invokes existing auditing tools only on isolated Components copies. It never uses permission-bypass flags or automatically elevates. Calls have a 600-second deadline and owned-process-tree cleanup. Unknown or failed submissions retain their state and are not automatically resubmitted.

Without selection options, the original `sc2-localization` flow remains available, with one parallel recursion involving real baseline, candidate and composed executions plus experience capture. Project AGENTS and Skill metadata are immutable; scripts, hooks and project-specific rules cannot be added. Acceptance covers world hover, command-card tooltips and editor display names, checking actual text, markup/placeholders, target/locale containment and unchanged unrelated/generated files. Pre-execution proposals report `root cause confirmed`; the host records static acceptance only after execution and verification. These phases must remain distinct.

After candidate selection, `sc2-finalize` performs two additional real model calls for baseline and candidate on held-out object IDs and locales; it is not a status query. Primary-agent revisions also require fresh training execution. `sc2-apply` requires 3/3 training and 3/3 held-out cases, preserved constraints and valid links, and at least 10% fewer Skill characters. Before merging it checks the original Skill SHA256 and retains its exact bytes; source changes stop the merge. Completed calls with identical inputs are reused; applying a candidate does not resubmit model tasks. `sc2-restore` restores only if the live Skill still matches the applied fingerprint. Conclusions remain scoped to `static validation passed` on these cases, without claims of generally improved success rates.

## Professional Skill batches

The [Skill registry](../../tools/harness2-skills.json) fixes the 24 IDs, source paths, acceptance profiles and group order. Start with the three Galaxy foundations, then the remaining Galaxy IDs in pairs, three SC2Data pairs, three domain Skills, and finally the joint project-entry/tool-validation group. Preserve localization and include it in final tool regression.

```powershell
python tools/harness2.py --ui-language en sc2-optimize --skill galaxy-language-fundamentals
python tools/harness2.py --ui-language en sc2-optimize --batch "<batch-manifest.json>"
python tools/harness2.py --ui-language en sc2-finalize "<batch-experiment-directory>"
python tools/harness2.py --ui-language en sc2-apply "<batch-experiment-directory>"
python tools/harness2.py --ui-language en sc2-restore "<batch-experiment-directory>"
```

Batch manifests use `{"skills":["skill-id","skill-id"]}`. Experiments live under `.runtime/harness2/skill-batches/`; `batch.json` freezes model settings, implementation files, AGENTS, original fingerprints and section migration mappings. Changed implementation, model, cases or sources require a new experiment; old results cannot validate changed inputs.

The host splits sections outside code fences without losing content, rebasing Markdown links while retaining APIs, fields, examples and caveats verbatim. Models may edit only declared entry Markdown; rules and migrated references remain immutable. Baselines solve directly with the original entry, without an artificial empty-read call. Candidates first receive their entry and available reference paths, then select reads; the host validates the whitelist before supplying selected content. Usage includes both selection and solving, including fixed native executor input overhead. Experiments fix lookup reasoning effort to `low` and optimization/review to `medium`, consistently for baseline and candidate, while retaining the configured `gpt-6.1-sol` model. Optimizers receive entry-related sections and an immutable reference index; the host preserves complete technical originals. Two cross-process slots enforce the shared concurrency limit, with a 600-second call deadline.

Each Skill has three training and three independent reference questions, plus checks for generated-source protection, GUI preference, active inheritance, UI language versus locale, target binding and precise acceptance stages. Domain profiles also check Catalog effective values, Actor asset chains and visual evidence, GUI library availability, complete task routing or validation scope. Reference and routing cases do not establish Editor compilation or gameplay acceptance.

`adoption.json` records actual calls, per-Skill outcomes and total input tokens including reference reads. Every adopted Skill must pass all candidate checks and either correct an observed failing routing branch or reduce mean matched-task input tokens by at least 10%; group averages do not replace individual gates. Unhelpful candidates retain their original Skills. Applying also requires primary-agent review of the complete diff, candidate fingerprints in `review.json`, and joint link/tool-reference validation. All target fingerprints are checked before writing, with exact backups and staged files retained first. Restore checks the entire group before changing anything; later modifications stop restoration. It removes only references created by this merge whose fingerprints still match. An interrupted write retains an `applying` record supporting the same guarded recovery.

## State and maintenance

The wrapper stores benchmark results in `.runtime/harness2/runs/`. Downloaded upstream dependencies use subdirectories of `integrations/harness2/dependencies/`. Environments, credentials, caches and results are ignored. Review experiment diffs and evidence before adopting changes to workspace rules.

To reinstall on Linux, create `.venv-linux` with Python 3.12 and install `integrations/harness2[render]`. Local offline wheels are retained under `temp/harness2-wheels/`. The demo does not require optional `bridge` dependencies. Help or preflight success does not prove model connectivity; demo success does not establish model benchmark success or SC2 Editor/game acceptance.

<!-- translation-source: wiki/guides/harness2.md; sha256: 6b157360744e9fbd501e50b61773c669b308d946f0ac9f30f000b7089c38f94e -->
