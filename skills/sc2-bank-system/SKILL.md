---
name: sc2-bank-system
description: StarCraft II bank (.SC2Bank) campaign persistence for the AeonOfIhanrii campaign. Use when designing or editing campaign progress saves, player choices, unlocks, difficulty tracking, or mission completion state. Covers schema versioning, section design, BankLoad/Save workflow, and native Galaxy bank function signatures.
---

# SC2 Bank System & Campaign Persistence

## When to Use

Load this skill when the task involves campaign persistence: writing or editing bank initialization, mission victory saves, unlock state, difficulty tracking, or any code that calls `BankLoad` / `BankSave` / `BankValueGet*` / `BankValueSet*`. Also load when designing the section/key schema for a new campaign or migrating an existing bank across releases.

## Persistence Design Principles

1. **Schema versioning:** Always include a `SchemaVersion` integer in the `Meta` section. If the schema evolves between releases, migration triggers can safely translate old saves without corrupting player progress.
2. **Deterministic sections:** Group data logically into dedicated sections:
   - `<Section name="Meta">`: `SchemaVersion`, `CampaignCompleted`, `Difficulty`, `LastPlayedMission`.
   - `<Section name="Missions">`: Per-mission completion state, bonus objectives, high scores.
   - `<Section name="Choices">`: Faction, commander, technology, or army loadout selections.
   - `<Section name="Upgrades">`: Global currency, tech unlocks, purchased research tiers.
3. **Safety & validation:** Verify key existence before reading. SC2 bank read functions return default empty values (`""` or `0`) if a key is absent — always guard with `BankKeyExists` before interpreting a value as meaningful.
4. **Preload & save windows:** Preload banks during map initialization (`BankPreLoad` / `BankLoad`). Save banks at milestone triggers or victory cinematics (`BankSave`).

## Bank File Location

- **Windows:** `Documents\StarCraft II\Banks\<BankName>.SC2Bank` (or `OneDrive\Documents\StarCraft II\Banks\` on OneDrive-redirected profiles).
- **Mac:** `~/Library/Application Support/Blizzard/StarCraft II/Banks/<BankName>.SC2Bank`.

Banks are local XML files stored per player — not synchronized across the network.

## Mod Identity (AeonOfIhanrii)

- Bank name constant: `"AeonOfIhanriiBank"`
- Galaxy function prefix: `libEpi_` (e.g. `libEpi_Bank_Init`, `libEpi_Bank_SaveMissionVictory`)
- Always preload the bank during early map initialization via the mod's GUI action, not via raw Custom Script in the map.

## Galaxy Bank Architecture Example

```galaxy
const string c_bankName = "MyCampaignBank";
const int c_currentBankSchema = 2;

bank gBank;

// Initialize a fresh bank with current schema defaults.
void libMy_Bank_InitDefaults(bank lp_bank) {
    BankValueSetInt(lp_bank, "Meta", "SchemaVersion", c_currentBankSchema);
    BankValueSetInt(lp_bank, "Meta", "CampaignCompleted", 0);
    BankValueSetInt(lp_bank, "Meta", "Difficulty", 1);
    BankValueSetString(lp_bank, "Meta", "LastPlayedMission", "");
}

// v1 -> v2 migration: introduced Difficulty and LastPlayedMission keys.
// Backfill them with safe defaults for saves made under the v1 schema.
void libMy_Bank_MigrateV1ToV2(bank lp_bank) {
    BankValueSetInt(lp_bank, "Meta", "Difficulty", 1);
    BankValueSetString(lp_bank, "Meta", "LastPlayedMission", "");
}

// Placeholder for the next schema gap. Uncomment and extend when
// c_currentBankSchema increments past 2 (rename keys, normalize enums,
// add new fields, etc.).
// void libMy_Bank_MigrateV2ToV3(bank lp_bank) {
//     // Example: shift Difficulty enum from 1..4 to 0..3, then add new key.
// }

void libMy_Bank_Init(int lp_player) {
    int lv_existingSchema;

    BankPreLoad(c_bankName);
    gBank = BankLoad(c_bankName, lp_player);

    if (!BankSectionExists(gBank, "Meta")) {
        libMy_Bank_InitDefaults(gBank);
        BankSave(gBank);
        return;
    }

    lv_existingSchema = BankValueGetInt(gBank, "Meta", "SchemaVersion");

    // Apply migration chain step by step. Each branch translates one schema gap;
    // they run sequentially so a v1 save reaches v2 before v3 logic (if any) runs.
    if (lv_existingSchema < 2) {
        libMy_Bank_MigrateV1ToV2(gBank);
    }
    // if (lv_existingSchema < 3) { libMy_Bank_MigrateV2ToV3(gBank); }

    if (lv_existingSchema < c_currentBankSchema) {
        BankValueSetInt(gBank, "Meta", "SchemaVersion", c_currentBankSchema);
        BankSave(gBank);
    }
}

void libMy_Bank_SaveMissionVictory(int lp_player, string lp_missionId) {
    BankValueSetInt(gBank, "Missions", lp_missionId + "_Completed", 1);
    BankSave(gBank);
}
```

## Core Native Functions

| Function | Purpose |
|---|---|
| `BankLoad(name, player)` | Open or create a bank file |
| `BankSave(bank)` | Write in-memory values to disk (writes are NOT auto-persisted) |
| `BankSectionExists(bank, section)` | Check whether a section exists |
| `BankKeyExists(bank, section, key)` | Check whether a key exists |
| `BankValueSetFromInt/Fixed/String/Text(...)` | Store a typed value |
| `BankValueGetAsInt/Fixed/String/Text(...)` | Read a typed value (returns default empty/zero if key absent) |
| `BankSectionRemove(bank, section)` | Delete a whole section |
| `BankKeyRemove(bank, section, key)` | Delete a single key |
| `BankSectionCount/Name(...)` | Iterate sections |
| `BankKeyCount/Name(...)` | Iterate keys inside a section |

## Hard Rules

- **`BankSave` is required** — writes are not persisted automatically. Forgetting `BankSave` after a `Set*` call silently drops the change on map unload.
- **Missing keys read as zero or empty** — never interpret `BankValueGetAsInt(...) == 0` as "player completed nothing" without first checking `BankKeyExists`. A missing key and a stored `0` are indistinguishable on read.
- **Prefer GUI bank triggers for new work.** Direct natives remain useful for reading legacy maps and understanding Blizzard examples. Embed a small Custom Script action only when the GUI cannot reasonably express that operation. Use `Epi_Main.galaxy` or `Base.SC2Data/Scripts/` for explicitly requested Galaxy work or maintenance of existing script logic; deploy only in `workspace_copy` mode, then save in the Editor to regenerate compiled libraries.
- **Never trust bank state across clients** — banks are local per player. Cross-player comparisons must exchange data via trigger sync or game state, not bank reads.

## Reference

- `wiki/implementation/bank-system.md` — full persistence architecture
- `wiki/reference/galaxy-bank.md` — native function signatures
- `wiki/implementation/galaxy-gotchas.md` — Galaxy syntax rules that apply to bank code
- `wiki/implementation/per-map-setup.md` — bank preload checklist per map

## Chinese Task Knowledge (Merged)

Distilled from `references/galaxy-and-triggers.md` (persistence portion) and `references/source-caveats.md`.

### Bank API Naming Caveat
- `wiki/implementation/bank-system.md`'s example uses `BankValueGetInt` / `BankValueSetInt` and a single-argument `BankPreLoad`. The native table in `wiki/reference/galaxy-bank.md` and `triggers-native/b.md` uses `BankValueGetAsInt` / `BankValueSetFromInt`, and `BankPreload(name, player)` takes two arguments. Do not copy the example verbatim — keep the architecture but use the correct native names.
- Cross-check GUI bank wiring and the actually generated script together. Do not treat the old project's "GUI-only bank API" conclusion as a general engine limit.

### Schema Migration Caveat
- When migrating old schema versions, preserve already-earned progress. Do not blindly apply a sample reset to completion state. The actual player, Bank name, preload stage, and file path come from the project and runtime environment — do not hardcode them.

### Source Caveats (from `source-caveats.md`)
- **Bank API conflict:** `bank-system.md` uses `GetInt`/`SetInt`/single-arg `BankPreLoad`; `galaxy-bank.md` and `triggers-native/b.md` use `GetAsInt`/`SetFromInt` and `BankPreload(name, player)`. Always consult the native definition and the actually generated script. Keep the architecture idea, do not copy the example.
