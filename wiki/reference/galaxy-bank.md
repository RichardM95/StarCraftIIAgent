# Galaxy Bank Reference

Concise reference for SC2 bank natives.

## Major limitation

GUI bank triggers are needed to read and write the actual SC2 bank

## Core Native Functions

| Function | Purpose |
|---|---|
| `BankLoad(name, player)` | Open or create a bank file |
| `BankSave(bank)` | Write in-memory values to disk |
| `BankSectionExists(bank, section)` | Check whether a section exists |
| `BankKeyExists(bank, section, key)` | Check whether a key exists |
| `BankValueSetFromInt/Fixed/String/Text(...)` | Store a typed value |
| `BankValueGetAsInt/Fixed/String/Text(...)` | Read a typed value |
| `BankSectionRemove(bank, section)` | Delete a whole section |
| `BankKeyRemove(bank, section, key)` | Delete a single key |
| `BankSectionCount/Name(...)` | Iterate sections |
| `BankKeyCount/Name(...)` | Iterate keys inside a section |

## Generic SC2 Facts

- Banks are local XML files stored per player.
- Missing keys read back as zero or empty values unless you guard with `BankKeyExists`.
- `BankSave` is required; writes are not persisted automatically.

## Minimal Generic Example

```galaxy
bank b = BankLoad("ExampleBank", 1);

if (!BankKeyExists(b, "Progress", "SeenIntro")) {
    BankValueSetFromInt(b, "Progress", "SeenIntro", 0);
    BankSave(b);
}
```

## When Direct Bank Natives Still Matter

They are still useful when:

- reading legacy maps or older docs
- understanding Blizzard campaign examples
- editing GUI bank triggers outside the main script block

They are not the primary persistence API for current or feature work.
