# SC2 Trigger XML Workflow Gotchas

Validated workflow and schema pitfalls for external Trigger XML edits. Read this before touching a `Triggers` file directly.

## Workflow gotchas (critical — most validated empirically)

1. **Close the map in the editor BEFORE editing the Triggers file
   externally.** The editor's in-memory copy will overwrite external
   edits on next save. Back up `.bak` first.
2. **After external edits, reopen and TOGGLE ANY TRIGGER** (enable/
   disable, edit a comment) then save. This forces `MapScript.galaxy`
   codegen to re-emit `InitTriggers()` and wire up externally-added
   triggers. Without the poke, triggers exist in the tree and render
   correctly but never register events. Single most non-obvious failure.
3. **Use Chat for debug `UIDisplayMessage`** — preset `89CC0A21` (Chat).
   `Subtitle` (`875889C8`) is hidden during campaign-style gameplay.
4. **A Trigger with an Event but ZERO Actions crashes the editor on
   save** (validated against a mod file). Always include at least one
   Action — even a placeholder `<Action Type="Comment" Id="..."/>`
   pointing at a Comment element. Maps may be more lenient than mods;
   the safe rule is universal.
5. **Mod files are fussier than maps.** When generating net-new
   triggers, prototype in a map first, validate save+test, then migrate
   to the mod. Cross-library refs (`Library="<libId>"`) let mod-level
   constants stay in the mod while map-level triggers reference them.
6. **`<ScriptCode>` blocks bypass the editor's type checker.** Save will
   succeed even when the script references undefined symbols or
   out-of-bounds array indices. The Galaxy runtime then silently halts
   the executing trigger on the bad line. Diagnose by reading
   `MapScript.galaxy` directly — that's the post-codegen Galaxy source.
7. **ArraySize XML value vs runtime size:** `<ArraySize Dim="0" Value="N"/>`
   creates an array of size **N+1** (indices 0..N). Writing index N+1
   silently fails. For a 33-entry roster (indices 0..32), use
   `Value="32"` minimum.
8. **EVERY declared Element needs a matching TriggerStrings name entry**,
   including local variables and ParamDefs inside FunctionDefs. Missing
   entries cause the editor to invent a garbage hash for the Galaxy
   symbol name. Easy to miss for inner elements.
9. **`TriggerAddEventUnitCreated` is unreliable for "any unit spawn"** —
   fires inconsistently across train / spawn / warp-in. Use
   `TriggerAddEventUnitRegion` (Ntve `00000041`) with region = Entire Map
   and default Enter state instead — catches all unit appearances
   uniformly.
10. **Don't filter "is this an enemy" by player ID range** like `2..16`.
    Maps mix allies and enemies in that range. Use `PlayerIsEnemy`
    (Ntve `CA3AB9A9`, signature `(source, target, relation)` with
    `relation` from preset `PlayerRelation` = `2D9EC843`).
11. **`nativelib` parameter defaults DO NOT auto-apply.** Even if a
    ParamDef has a `<Default Type="Param" .../>` in nativelib, you MUST
    emit an explicit `<Parameter Type="Param" Id="..."/>` for every
    declared param when constructing a `<FunctionCall>` — otherwise the
    editor renders the param as red "(No Value)" and compile fails.
12. **The `NoUnit` PresetValue (Ntve `630EB901`) is corrupt** — its
    `<Value>` is `true` (bool) not `null`. Comparing a Unit-typed value
    to NoUnit emits Galaxy `x != true` which fails to compile. Workaround:
    use an indirect filter instead (e.g. `ZoneOwner[i] == EnemyPlayer`
    instead of `Building[i] != NoUnit`).
13. **`Or` / `And` use different cond sub-types** (`Or` = `00000001`,
    `And` = `00000002`). See SubFunctionType section above.
14. **`.version` binary stamps must EXIST for the map to load.** Deleting
    them breaks load with "Unable to copy file" errors. The editor
    regenerates them on save, but needs them present on load. If you
    must reset, copy from a sibling map — the editor overwrites with
    current hashes on next save.
15. **Galaxy Custom Script parser quirks** (in `<ScriptCode>` blocks):
    - `for (init; cond; incr) { … }` — fails. Use `init; while (cond) { …; incr; }`.
    - `break;` inside loops — fails. Use a sentinel variable in the while condition.
    - `+=` / `-=` / `++` / `--` — fail. Use explicit `x = x + 1;`.
    - **PREFIX EVERY LINE with 4 spaces.** The Trigger Editor's Custom
      Script display strips the first 4 characters of every line. Without
      the prefix, lines render mangled (`unitgroup` → `group`,
      `while (…)` → `e (…)`). Galaxy ignores extra indentation so this
      is safe both ways.
    - **`//` line comments work**, but multi-hyphen separators don't —
      Galaxy's tokenizer flags `--` as the unsupported decrement
      operator even inside `//` comments. Use single hyphens.
    - **Em-dashes and any non-ASCII** — parser is ASCII-only. Strip
      smart-quotes, em-dashes, arrows.
    - **Cascade failure:** any `<ScriptCode>` parse error aborts the
      WHOLE file load and emits "Orphaned trigger parameter" / "Empty
      trigger element reference" warnings for everything downstream.
      Look for the real parse error in `MapScript.galaxy`.
16. **Galaxy constants that DO NOT exist:** `c_unitStateStructure` — use
    `UnitTypeTestAttribute(UnitGetType(u), c_unitAttributeStructure)`.
    Validated existing: `c_messageAreaDirective`, `c_messageAreaChat`,
    `c_playerAny`, `c_unitCountAll`, `c_unitCountAlive`,
    `c_unitCreateIgnorePlacement`, `c_orderQueueReplace`, `c_anchorBottom`,
    full `c_triggerControl*` and `c_unitAttribute*` families.
17. **`AIStart` is `(int player, bool isCampaign, int apm)`** — not the
    older `(player, bool restart, string script)` signature in old docs.
    Use `AIStart(p, true, 200);`.
18. **`<ArraySize>` MUST be nested INSIDE `<VariableType>`**, not after
    it. A misplaced ArraySize creates a SCALAR variable, not an array —
    all subsequent `Set X[i]` GUI actions silently invalidate. Correct:
    ```xml
    <Element Type="Variable" Id="...">
        <VariableType>
            <Type Value="int"/>
            <ArraySize Dim="0" Value="6"/>
        </VariableType>
    </Element>
    ```
    Two `<ArraySize Dim="..."/>` siblings for 2D arrays.
19. **Self-closing `<Element Type="Comment" Id="…"/>` crashes editor on
    save.** Comments MUST have a non-empty `<Comment>…</Comment>` body
    AND a `Comment/Name/X=…` entry in TriggerStrings. Crash is on save,
    not load.
20. **Custom Script Action as the body of a USER FunctionDef does NOT
    work reliably** — opaque compile failures even after stripping
    em-dashes / decrement operators / prefixing 4 spaces. Workaround:
    put Custom Script Actions directly in Trigger bodies, OR use pure
    GUI native FunctionCalls in your user FunctionDef.
21. **FunctionCall elements can only have ONE parent reference at a
    time.** Pointing two Params at the same FunctionCall Id (to "reuse"
    a subtree) binds the FIRST and renders the SECOND as red "(No
    Value)". Orphan branches still steal bindings — delete orphans or
    copy the subtree to fresh IDs instead of sharing.
22. **`TriggerStrings.txt` is PLAIN TEXT — do NOT HTML-entity-escape.**
    Writing `Init &amp; Scaffolding` shows literally as `Init &amp;
    Scaffolding` in the editor. Use raw characters. (Inside the
    Triggers XML itself, entities ARE required for special chars in
    attribute values.)
23. **`ArithmeticInt` (`00000128`) and `ArithmeticReal` (`00000129`)
    have DIFFERENT ParamDef IDs** despite identical 3-slot shape:
    - ArithmeticInt: `00000205` val1 int, `00000206` op, `00000207` val2 int.
    - ArithmeticReal: `00000208` val1 fixed, `00000209` op, `00000210` val2 fixed.
    - Op preset values shared: `00000085` = `+`, `00000086` = `-`,
      `00000087` = `*`, `00000088` = `/`. Pick by the surrounding
      context's expected type.
24. **`Repeat Action Forever` code-generates as `while (true)`.** Actions
    after it execute only when the loop reaches an explicit `break`;
    `return` exits the entire trigger. For a persistent monitor whose
    caller must continue, put the loop in a separate no-event trigger and
    run it without waiting for completion. Keep a `Wait` inside the loop
    to avoid the execution limit. Blizzard-generated examples show both
    patterns: `paiur02`'s `Group - Burrowed Zerg` breaks before later
    actions, while `paiur03` runs `Deploy Pylon Units Powered` with
    `TriggerExecute(..., true, false)` before continuing its caller.
25. **Show/Hide and Pause are independent unit states.** Show/Hide changes
    `c_unitStateHidden`; Pause changes `c_unitStatePaused`. If a unit must
    be both absent from presentation and inactive, set both states and
    later restore both. Blizzard's `pshakuras02` intro keeps separate
    hidden and paused groups and restores each group independently.

---

## ID generation strategy

Pick a recognizable 4- or 5-char hex prefix per generation pass (any hex
string that's unlikely to collide with existing IDs, e.g. `A1B2C…`,
`DEAD0…`). Grep the existing Triggers file for the prefix first to
confirm no collisions. Use suffix ranges to make the element tree
readable: e.g. `<prefix>100..1FF` for the trigger event chain,
`<prefix>200..2FF` for branch 1, `<prefix>300..3FF` for branch 2.

---
