# Editor Round-Trip and Actor XML Patterns

## Editor Round-Trip Checklist

Use after local XML work and before calling an implementation done. See also [unit-extraction-from-inactive-xml.md](../../reference/unit-extraction-from-inactive-xml.md) for inactive-source extraction.

### Before Editor save

1. Trace the full dependency graph from unit through abilities, weapons, effects, behaviors, validators, requirements, movers, turrets, actors, models, sounds, buttons, and localization.
2. Verify every referenced custom or inactive-source ID exists in the active dependency chain or project mod catalogs.
3. Add `ObjectStrings.txt` `Name` plus `EditorPrefix` or `EditorSuffix` for every new catalog object.
4. Add `GameStrings.txt` entries only for player-facing text, anchored through real XML fields (`Name`, `Tooltip`, `Description`, button faces, upgrade effect references).
5. Avoid inactive/co-op-only button faces and helper UI records unless the exact ID is present in active dependencies.
6. Patch the actual command-card layers and inherited button indices the campaign structure opens; hide inherited vanilla buttons with requirements or `removed="1"` where needed.
7. Use active campaign button faces for universal commands (Attack, Stop, Hold Position, Patrol, Rally).
8. Run a local XML parse on touched catalogs, then an ID-level audit for new references and localization coverage.

### After Editor save

1. Scan all files under the project's `.SC2Mod/Base.SC2Data/GameData/` folder for duplicate `(catalog type, id)` pairs across `GameData.xml` and typed side catalogs (`ModelData.xml`, `SoundData.xml`, `TurretData.xml`, `ValidatorData.xml`, `WeaponData.xml`, `ButtonData.xml`, etc.). Keep one canonical row per ID.
2. Treat Editor warnings, blank editor names, blank command-card icons/text, and preload churn as signals of an incomplete extraction graph — not cosmetic output.
3. Use whitespace-insensitive or XML ID-level diffs; raw line diffs after Editor save often exaggerate actual design change (especially `ActorData.xml` ordering).
4. Recheck child-unit indexed command-card overrides. The Editor can expand inherited indexed `LayoutButtons` fields into local child elements and preserve inherited requirements that do not belong on the custom unit. Confirm important buttons still point at the intended `AbilCmd`, row/column, and requirement after a save.
5. Strip copied or inherited actor UI hooks when the active dependency/UI context lacks the referenced file desc:
   - `CustomUnitStatusFrame value="Coop_UnitStatus_.../..."`
   - `CustomUnitStatusFrame value="HotS_UnitStatus/..."`
   - `CustomUnitStatusFrame value="LotV_UnitStatus/..."`
   - `StatusBarOn index="Custom" value="1"`
   - `UnitFlags index="SuppressDefaultStatusBar" value="1"`
   - If a local actor inherits a problematic status frame from its parent, prefer a direct safe parent such as `GenericUnitStandard` plus copied visual fields over keeping the inherited custom UI chain.

### Three-pass validation

1. **Local static pass:** importers/audits, XML parse, duplicate scan, localization audit, `tools/sc2-catalog-query.py` unresolved-reference check.
2. **Editor round-trip:** reopen/save as Components, collect full warning list, inspect diff as canonicalization signal.
3. **In-game pass:** smallest mission scenario that exercises production, replacement, command card, requirements, VFX/audio, upgrades, and campaign unlock state.

# Morph transition presentation actors

For project-owned visual-only morph transitions, prefer `CActorModel parent="ModelAdditionNoAnims"` hosted on `_Selectable` through inheritance. Create it on `AbilMorph.*.Start`, play the desired morph animation on `ActorCreation`, destroy it on morph finish, and include `ActorOrphan -> Destroy` as a fallback.

Avoid importing a visual overlay as `CActorUnit parent="GenericUnitBaseMorphTransition"` or as `CActorMissile`. Even when its `unitName` points at a dummy morph ID, creation from a custom unit's morph event can place it in the real unit scope and emit `More than one CActorUnit persisting in the same unit scope`. The Editor may preserve the XML exactly; the warning is a runtime scope problem, not a serialization problem.

For variant-specific morph visuals, verify the referenced `CModel` has an explicit `.m3` asset path in the active dependency chain. A reduced row copied from an inactive dependency may contain only radius/scale metadata because its original dependency supplied the asset elsewhere. That can produce an invisible morph or silently fall back to a generic vanilla model. Prefer a project-owned model ID with the explicit asset path, then point the transition actor at that ID.

## Indexed unit-actor construction events

`CActorUnit` rows that retarget the inherited `GenericUnitMinimal` event array must preserve the inherited index meanings:

- index `4`: `UnitConstruction.<unit>.Start` (creates the unit actor for construction/warp presentation);
- index `5`: `UnitConstruction.<unit>.Finish` (finishes the construction presentation).

Do not use a bare `UnitConstruction.<unit>` term at either index, and do not put `.Start` at index 5. The latter overwrites the inherited finish handler and can leave two persistent models or a fallback warp sphere. A `BuildModel` alone cannot correct a shifted event override. After an Editor round trip, audit all project `CActorUnit` rows for these exact suffixes because the Editor may rematerialize inherited indexed events.
