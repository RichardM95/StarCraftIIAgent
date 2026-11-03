---
name: sc2-map-triggers
description: Read, create and modify editable SC2 GUI events, conditions, actions, variables and mission objectives, including existing regions and map-to-mod calls. Use for mission behavior and GUI organization.
---

# SC2 GUI triggers

## Daily workflow

The explicit map or mod is the target. Follow the project entry's task routing, then open that target through the shared CLI/MCP. Query-only work uses a read-only project. Choose its actual configured editing source for authorized changes.

1. Read `sc2_trigger_context` with project_id and a bounded selection or query. Confirm the category, parent, role, execution order, active definitions, resources and fingerprint. Read existing initialization before adding another entry.
2. For queries, answer from that context. For new functionality, describe events, conditions, ordered actions and declarations using `sc2_trigger_author`. For modifications, select exact existing nodes and use insert, replace, replace_branch, reorder, move or delete.
3. Bind definitions, slots and presets by `Library/Type/Id`. Bind the actual named region uniquely. Use request-local names for new nodes. Preset declarations resolve `TypeElement` to the exact Preset's `BaseType`.
4. Preview the behavior differences and impacts. Verify positive and negative cases, scope and ID preservation. Candidate mode validates the actual bytes in isolation through GUI references, offline generation and Galaxy static checking. Review candidate_fingerprint, then use the existing changes transaction to apply or roll back. Refresh context after source, resource or dependency changes.
5. Record `static validation passed`, `Editor accepted` and `packaged runtime passed` only with their corresponding artifact and observations. Use the supplied target and locale for anchor restoration after capturing raw Editor differences.

The [behavior authoring contract](../../wiki/guides/trigger-author.md) owns the versioned spec, examples, edits and diagnostics. The [shared tools guide](../../wiki/guides/shared-tools.md) owns CLI invocation and state. Use current tool schemas for arguments.

## Resources and mixed tasks

For existing regions or placed units, inspect and bind them before planning changes. A missing or ambiguous region reports the requested name, target and actual candidates. Whole-map defaults are appropriate only when requested.

When terrain work creates or moves a region/object, continue on the handed-off working copy. Read fresh trigger context there and rebind its actual ID. The project entry owns the mixed-task order. For physical rescue interactions, sidequests and category organization, read [map adaptation](references/map-adaptation.md).

## Definitions and extensions

Context supplies available libraries and definition details. Use the [dependency query workflow](../../wiki/reference/trigger-knowledge.md) and its libraries/find/show/examples tools for additional lookup. Missing active dependencies block writing. Define exported GUI actions in the mod and call them through GUI actions in the map.

Check the low-level `sc2_trigger_write` contract when authoring lacks a required shape. Read [XML and wiring](references/xml-and-wiring.md) only for that work. Preserve unknown source and independent call/parameter instances. Generated MapScript.galaxy and Lib*.galaxy are read-only build evidence. New functionality uses GUI, with a small embedded Custom Script only where necessary. Explicit Galaxy requests and existing handwritten source route through sc2-galaxy-scripting.

For speech, Conversation data, dialogs and cinematics, load [reviewed dialogue mechanisms](../../wiki/reference/trigger-dialogue-examples.md). Battle-wave conversion uses sc2-attack-wave-scaling. Examples and historical library IDs require rebinding to the actual target.
