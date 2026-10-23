# Multiple computers and synchronization

[中文](multi-pc-setup.md)
<!-- translation-source: wiki/guides/multi-pc-setup.md; sha256: 6c167ed5fdbab6bf2d674b6b3e287870ab1f8c02ae6dc30426490efd5b331bd3 -->

Keep repository asset/include/script paths relative; never hard-code user home directories in XML layouts or Galaxy. agent-config.json paths resolve relative to the workspace where possible. Cross-drive absolute paths are machine-specific; rerun tools/init-project.py on each computer.

SC2_MODS_PATH optionally supplies a machine's Mods root only when no primary project is configured. SC2_GAMELOGS_PATH supplies GameLogs. Personal interface language is independently configured with [language preferences](agent-language.en.md); do not commit preferences.

Follow .gitattributes line endings for XML/Galaxy/Layout/Bank. Do not commit publish/ or generated indexes. Run relevant checks before pushing.

After synchronization, confirm the Editor can locate Components and run `python tools/init-project.py "<主模组.SC2Mod 路径>"` to resolve local paths/dependencies. For workspace_copy, preview `python tools/deploy-mod.py --dry-run`, then perform authorized deployment. Identical in-place source/target needs no copy.
