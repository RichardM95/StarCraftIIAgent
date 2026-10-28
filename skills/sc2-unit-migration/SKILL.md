---
name: sc2-unit-migration
description: Migrate SC2 mod data between components, including local-layer merges without official dependency payloads and selective custom-unit chains with typed references, resources, conflict previews and verified publication.
---

# SC2 Unit Migration

Use the workspace [migration guide](../../wiki/guides/unit-migration.en.md) and `python tools/sc2-migrate.py --help` for the current interface. Follow the existing project source-mode and language rules.

## Decisions before analysis

- Establish whether roots mean new IDs or also official-ID variants, which official baseline applies, and whether target dependencies may change. The current command implements new IDs against each source's official active dependencies and keeps target dependencies fixed.
- Distinguish playable roots from auxiliary unit forms. Classification evidence is a proposal; uncertain records need an explicit unit selection.
- Multiple sources with one unit ID require a source choice. Never substitute a similarly named object across source contexts.
- Set the destination prefix explicitly for a real project. Persist the generated mapping rather than inventing a different name on a later run.

## Explicit local-layer merge

Choose the ownership rule first: a local source file can contain overrides on official IDs. For nonofficial content, compare IDs with complete source-specific official baselines; exclude official roots and retain official overrides only with custom-unit chain evidence. Use unit-chain extraction for a new transfer. For cleanup of a published local-layer merge, use the guide's `prune` workflow and review every official exception's root and field before applying.

Use unfiltered `tools/sc2-merge-mod-layers.py plan` only when the user explicitly includes local overrides on official IDs. Pass sources in low-to-high priority order. Confirm an unresolved collision policy before writing; later sources select complete original Catalog entries, resource files and text values. Preserve IDs, parents, tokens and array operations. Only local Catalogs, assets and localized text are transferred; scripts, trigger libraries and UI files are listed for separate wiring.

This mode can intentionally retain missing official references when the user chooses fixed target dependencies. Validate source and staged XML, record the reference gap, and use the verified staged-publication/backup workflow. Do not describe this source-layer copy as complete playable-unit migration. The dependency/dynamic-link export stops below apply to unit-chain extraction, not an explicitly authorized raw-layer transfer.

## Workflow

1. Analyze with explicit source and target paths. Read the dependency completeness, official-ID exclusions, candidates and per-unit issues. Analysis does not switch the active project.
2. If official evidence is missing, use the existing explicit CASC snapshot workflow. Bind per-source snapshots with `--source-cache`; a missing ID in a partial baseline is not proof of custom ownership.
3. Resolve the selection JSON and rerun `plan`. Trace production/upgrades and external script/UI hooks separately. Exact script-ID hits show a possible mechanism dependency, not proof that copying generated Galaxy would solve it.
4. Export only selected chains without blocking issues. Review the complete ID mapping, renamed actor events, text references, resources and fixed target dependency contract.
5. Preview the package against its bound target. Apply only within the user's authorized write scope; `apply` is still a preview unless `--apply` is supplied. Existing different objects, texts or resources require resolution, not silent replacement.
6. Validate the actual component, then obtain Editor and packaged-runtime evidence following the existing acceptance workflow. A successful transaction is not runtime acceptance.

## Stop conditions

Incomplete official baseline, unknown merge order, unresolved dynamic links, external mechanisms, missing resources or target conflicts block executable export. Reports remain useful and preserve evidence. Do not remove problematic references merely to make the report green.

Imported catalog objects use a project prefix and source namespace; official objects reused in the target retain their IDs. Source overrides on official IDs may be needed inside a selected chain and must be isolated from the target's original object. Root-only official-ID exclusion must not discard those mechanics.
