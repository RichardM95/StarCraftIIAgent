# Issue tracking

[中文](issue-tracker.md)
<!-- translation-source: docs/agents/issue-tracker.md; sha256: 7074ab8fffceefa0ce6258dbb6cc7ff08dee002c460a03a377f2cfb737209d9a -->

Track cross-session issues in the active project data's docs/issues.md. Locate it with `python tools/project-paths.py`; use the [issue template (Chinese original)](../../wiki/implementation/bug-reports/latest.md) (English original). Complete small edits directly without mandatory bookkeeping.

Use exact stages: reported → root cause confirmed → source fixed → static validation passed → Editor accepted → packaged runtime passed. Record reproduction, cause, repair and validation evidence appropriate to the gate. Static results never substitute for Editor/game evidence.

Before numeric edits check local entry, parent, dependencies and intended override. For UI text identify the effective surface/key. Move durable contracts into project topics instead of a chronological ledger.

Extract game logs when requested/authorized, into runtime/reports/bugreport.txt; without a project pass --output. Original logs remain read-only. Default missing ledgers are skipped; explicit --ledger must exist. --target selects the actual component's data and is mutually exclusive with --ledger. Editing copies retain project ownership. Unified checks pass the actual target. Evidence gates are in [feedback](../../wiki/implementation/testing-feedback-workflow.en.md#required-outcome-wording).
