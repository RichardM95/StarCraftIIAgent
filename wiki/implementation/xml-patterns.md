# Confirmed XML Patterns Hub

This documentation section contains battle-tested StarCraft II Data Editor XML patterns, catalog rules, production setups, and editor save behaviors.

---

## 📚 XML Pattern Sub-Pages

- **[Catalog Rules & SC2 Schema](xml-patterns/catalog-rules.md):** Formal XML schema rules, inheritance mechanics, array operations (`index`, `removed`), and default value behaviors.
- **[Core Units, Weapons & Abilities](xml-patterns/core.md):** Unit creation checklists, weapon chains, damage effects, persistent effects, buffs, requirements, and validators.
- **[Production, Upgrades & Economy](xml-patterns/production.md):** `CAbilTrain`, `CAbilWarpTrain`, `CAbilMorph`, command-card cost display, and multi-tier upgrade links.
- **[Editor Round-Tripping & Actors](xml-patterns/editor-roundtrip-and-actors.md):** SC2 Editor save normalization, dedicated catalog promotion, actor event bindings, and model/sound linkage.

---

## ⚡ Quick Checklist for New Custom Units

1. **`UnitData.xml`:** Create custom `CUnit` with unique ID, flags, weapon links, abilities, and card layout.
2. **`AbilData.xml` / `WeaponData.xml` / `EffectData.xml`:** Clone or build dedicated ability/weapon/effect chains.
3. **`ActorData.xml` / `ModelData.xml` / `SoundData.xml`:** Create explicit unit and action actors linked to your custom effects/events.
4. **`LocalizedData/`:** Add player-facing strings to `GameStrings.txt` and editor metadata to `ObjectStrings.txt`.
5. **Verification:** Run `python tools/test-suite.py` before opening the Editor.
