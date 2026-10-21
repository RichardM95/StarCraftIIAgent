---
name: sc2-bank-system
description: StarCraft II campaign Bank persistence, progress migration and save/transition diagnosis. Use when editing mission saves, unlocks, player choices or Bank loading, saving and schema compatibility.
---

# SC2 Bank System

## Project contract

Read the target Triggers and current [project data](../../docs/agents/project-data.md) for Bank name, player, sections, keys, exported GUI actions and backup/restore order. Preserve existing saves. New keys or schema versions belong to the selected project's design, not to a universal section template.

Prefer editable GUI actions for new persistence work. For existing Galaxy maintenance or explicit Galaxy requests, follow `sc2-galaxy-scripting` and verify exact native signatures. Generated scripts are read-only evidence.

## Read, apply and save

1. Confirm the destination map's preload declaration and actual library initialization; a mod dependency alone does not establish either.
2. Distinguish opening/loading a Bank, reading keys, and applying those values to runtime variables, unlocks and technology. Check key existence/type before interpreting a default zero or empty value.
3. Save after milestone writes, before the relevant unload/transition. A later backup or reload must not overwrite freshly earned progress. Match the project's synchronous/asynchronous action semantics.
4. During migration, preserve already earned unlocks and unrelated keys; backfill only absent/new fields. Reset or removal requires the intended project behavior.
5. Validate fresh Bank, existing Bank, ordinary save/load, victory transition and cross-map initialization separately. Record which scenario actually passed.

## Progress appears lost

Use the [Bank diagnostic](../../wiki/implementation/bank-system.md). Compare the disk file, loaded handle/player, in-memory variables and destination map application chain before changing data. An ordinary save can restore existing runtime state while a transition starts another map that must read/apply its own state.

## API lookup

The [B function index](../../wiki/reference/triggers-native/b.md) records GUI definitions, IDs and parameters. GUI action names are not automatically callable Galaxy signatures: query the target with `tools/sc2-trigger-query.py` and inspect Editor-generated code or actual native declarations for script use. Do not copy old `BankValueGetInt` / `BankValueSetInt` or single-argument `BankPreLoad` examples; they were removed because their signatures were not supported by the referenced definitions.

## References

- [Bank investigation and boundaries](../../wiki/implementation/bank-system.md)
- [Bank API reference boundaries](../../wiki/reference/galaxy-bank.md)
- [Map initialization wiring](../../wiki/implementation/per-map-setup.md)
- [Editor handoff](../../wiki/guides/editor-handoff.md)
