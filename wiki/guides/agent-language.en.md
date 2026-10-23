# Interface language and personal preferences

[中文](agent-language.md)
<!-- translation-source: wiki/guides/agent-language.md; sha256: 5fc61cb5d06858b3e7fce4935452843cec8b5fec5b7d2f6ea9995391ab03ecdd -->

The usage layer supports Simplified Chinese and English, with separate linked pages. Deep API references, raw game data and third-party files retain their original language; the agent explains them in the chosen language and identifies the source language. Skills retain one name and authoritative rule source.

## Conversation language

Choose: explicit user language instruction → fixed personal preference (zh-CN or en) → the current user's natural language → environment default. A saved auto does not fix conversation language. English inside code, paths, IDs or quotations does not switch the conversation. “Use English for this reply” is temporary; save a preference only when requested.

When preferences are needed, run `python tools/agent-language.py --json` read-only. The saved preference field distinguishes a fixed choice from an environment fallback. Report invalid preferences with their path and repair command; an explicit language bypasses corruption. Pass the effective `--ui-language` to other tools.

## CLI selection and saving

CLI precedence: `--ui-language` → `SC2AGENT_UI_LANGUAGE` → personal preference → automatic detection. Explicit auto uses the first populated LC_ALL, LC_MESSAGES, LANGUAGE or LANG, then the Windows user display language, then system locale. All Chinese variants map to zh-CN; unsupported languages fall back to en.

```powershell
python tools/agent-language.py
python tools/agent-language.py --set en
python tools/agent-language.py --set zh-CN
python tools/agent-language.py --set auto
python tools/sc2-catalog-query.py --ui-language en --no-auto-rebuild stats
python tools/sc2-catalog-query.py --ui-language zh-CN --locale enUS --no-auto-rebuild stats
```

No arguments or --json only display language, source, saved preference and preference path; they create nothing. Only --set saves. Default: `%LOCALAPPDATA%/StarCraftIIAgent/preferences.json`; without LOCALAPPDATA on other systems: `~/.config/StarCraftIIAgent/preferences.json`. Override with `SC2AGENT_PREFERENCES_FILE` for isolated tests or portable use. Preferences are personal, outside project config and version control. Saving preserves unrelated valid JSON fields; --set explicitly repairs corrupt files.

## Data compatibility

Translate instructions and replaceable example placeholders into the page’s language, such as `Unit:<unit-id>` in English. Keep real object IDs, Library IDs, actual paths, command parameters and exact lifecycle labels unchanged.

UI language changes owned human help, summaries and prompts. JSON/XML fields, canonical diagnostics, states, exit codes and raw data remain stable. Raw runtime/system errors retain their original text beside a localized human summary; machine output has no language banner. Native worker protocols are unchanged.

SC2 `--locale enUS|zhCN` selects data language independently. Switching UI language changes neither localization files nor project configuration; preferences/UI language are excluded from Catalog inventories and do not trigger rebuilding. Child CLIs receive the effective UI language and UTF-8; legacy English assertions explicitly select en.

Example: “Explain Unit:Marine in English for this reply” temporarily selects English and --ui-language en. A later Chinese request selects Chinese unless a fixed preference applies. “Always use English from now on” authorizes --set en. None of these examples is acceptance evidence.
