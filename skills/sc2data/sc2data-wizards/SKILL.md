---
name: sc2data-wizards
description: SC2 Data Editor — Wizards for automating complex or repetitive data creation/modification in XML. Use when creating .BlizWiz XML files to define templates for generating catalog entries (units, abilities, effects, actors, etc.) with user inputs, conditions, validations, and macros. Covers wizard elements (input, entry, condition, validate, macro), string evaluation (tokens, catalog references, arithmetic), and file placement. Always reference the Data Wizard Documentation for syntax. Do not use for direct data editing (use other sc2data-* skills) or Galaxy scripting.
---

## Loading Boundary

- **This sub-skill owns:** .BlizWiz XML wizard templates — input/entry/condition/validate/macro elements, string evaluation, and file placement
- **Parent root skill (`sc2-catalog-xml`) owns:** project conventions, schema/syntax rules, source-of-truth, naming prefixes
- **Sibling sub-skills own:** `sc2data-units-abilities` (direct unit/ability data editing), `sc2data-effects-weapons` (direct effect/weapon editing), `sc2data-actors-visuals` (direct actor editing)

# SC2 Data Editor – Wizards

## Prerequisite

Load [`sc2-catalog-xml`](../../sc2-catalog-xml/SKILL.md) first for project-wide Catalog XML schema rules (child value elements not raw attributes, ASCII-only, no `AbilAutoCmd`, no `CBehaviorBuff.InitEffect`, no comment-only catalogs), parent inheritance pitfalls, effective-value evidence workflow, localization anchors, and Editor round-trip safety. This sub-skill owns deep schema reference only; project conventions live in the router skill.

Wizards are XML-based templates (`.BlizWiz` files) that automate the creation and modification of catalog entries in the SC2 Data Editor. They provide a dialog interface for user inputs, generate multiple related entries, enforce rules, and standardize complex data workflows. Wizards are loaded from user folders, maps, or mods, and can be run from the Data Editor menu.

## Key References

| Resource | URL |
|---|---|
| Data Wizard Documentation | https://sc2mapster.wiki.gg/wiki/Data_Wizard_Documentation |
| Wizard Tutorial | https://sc2mapster.wiki.gg/wiki/Data/Wizard_Tutorial |
| SC2Mapster wiki | https://sc2mapster.wiki.gg/ |
| ShadowDragon Base.SC2Data (example wizards) | https://github.com/ShadowDragonSC2/Base.SC2Data/tree/main/EditorWizards |

## XML Error Check and Fix Workflow

When editing `.BlizWiz` XML, always run this loop until diagnostics are clean:

1. Validate XML using Red Hat XML diagnostics (Problems panel).
2. If a schema is available for the file, follow schema diagnostics first.
3. If no dedicated wizard schema is available, validate structure against Data Wizard Documentation and known working examples in `EditorWizards`.
4. Fix invalid elements/attributes/tokens and re-validate.
5. Repeat until no XML diagnostics remain.

If a user asks to fix wizard XML errors, perform this end-to-end workflow rather than only describing it.

---

> **File placement:** Wizards use `.BlizWiz` extension. Place in `EditorWizards/` folder in user game directory, or inside map/mod archive. Reload automatically on file changes.

## Wizard File Structure

File: `MyWizard.BliZWiz`

Root element is `<wizardfile>`, containing one or more `<wizard>` elements:

```xml
<?xml version="1.0" encoding="utf-8"?>
<wizardfile>
    <wizard id="MyWizard">
        <name>My Custom Wizard</name>
        <description>Creates a unit with associated actor and effect.</description>
        <category>Data/Custom</category>
        <objecttypes create="Unit;Actor;Effect"/>
        <!-- inputs, entries, conditions, etc. -->
    </wizard>
</wizardfile>
```

## Core Elements

### Wizard Element

Defines the wizard itself:

- `<name>`: Display name in menu.
- `<description>`: Detailed description.
- `<category>`: Menu path (e.g., "Data/Custom").
- `<objecttypes>`: Supported types for create/load/view (e.g., `create="Unit;Actor"`).
- `<instructions>`: Optional dialog instructions (per page).
- `<hidden>`: Hide from menu (for embedded wizards).

### Input Element

User inputs for the dialog:

- `id`: Unique identifier.
- `type`: Control type (e.g., `WizardText`, `WizardMenu`, `WizardRadio`, or any catalog type like `int32`, `CStringLink`).
- `<name>`: Label.
- `<tooltip>`: Help text.
- `<default value="...">`: Initial value.
- `<item>`: For menus/radios (with `value` and `text`).
- `<condition>`: Visibility conditions.
- Layout: `page`, `column`, etc.

Example:

```xml
<input id="UnitName" type="string">
    <name>Unit Name</name>
    <default value="MyUnit"/>
</input>
```

### Entry Element

Catalog entries to create/modify:

- `catalog`: Type (e.g., "Unit").
- `type`: Entry type (e.g., "CUnit").
- `<id>`: Entry identifier (evaluated).
- `<parentid>`: Parent entry.
- `<field>`: Fields to set (with `<value>`, `<index>`, etc.).
- `<token>`: Tokens to set.
- `<condition>`: When to process.

Example:

```xml
<entry catalog="Unit" type="CUnit">
    <id>^UnitName^</id>
    <field id="LifeMax">
        <value>^HealthValue^</value>
    </field>
</entry>
```

### Condition Element

Boolean logic for UI/data flow:

- `input`: Input to check.
- `value`: Required value.
- `match`: Comparison (equal, begin, end, contain).
- `operator`: Numeric ops (greater, less, etc.).
- `logic`: and/or/not.
- Nested conditions.

Example:

```xml
<condition input="HasShield" value="1"/>
```

### Validate Element

Enforce rules:

- `type`: error/confirm/warning.
- `<condition>`: When to validate.
- `<text>`: Message.

Example:

```xml
<validate type="error">
    <condition input="UnitName" empty="0"/>
    <text>Unit name cannot be empty.</text>
</validate>
```

### Macro Element

Reusable expressions:

- `id`: Identifier.
- `replaceSrc/replaceDst`: Text replacement.
- `truncate`: Max length.

Example:

```xml
<macro id="UnitId">MyMod_^UnitName^</macro>
```

## String Evaluation

Evaluated strings use `^tokens^`:

- `^InputId^`: Input value.
- `^MacroId^`: Macro value.
- `ENTRYINDEX`, `VALUEINDEX`, `ITEMINDEX`: Indices.
- Catalog refs: `ref=TYPE,ENTRYID,FIELDPATH` or `ref=TYPE,ENTRYID,FIELDPATH#` for count.
- Arithmetic: `^Value1^ + ^Value2^`.

Example: `<value>^BaseHP^ * 2 + 10</value>`

## Common Patterns

- **Embedded Wizards**: Use `type="Wizard:OtherWizardId"` for sub-dialogs.
- **Arrays**: Use `<count>` and `^VALUEINDEX^` for multiple fields.
- **Loading Existing**: Use `loadvalue` and `^LOADID^` for editing.
- **Macros for Reuse**: Factor common IDs or calculations.

Always test wizards by running them in the Data Editor and checking generated XML against catalogsData.xsd.