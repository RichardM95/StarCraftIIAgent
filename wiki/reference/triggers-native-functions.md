# SC2 Native Function Reference

Full `Ntve` native function lookup split into one page per alphabetic bucket for faster agent search.

| Page | Range |
|---|---|
| [triggers-native/a.md](triggers-native/a.md) | A |
| [triggers-native/b.md](triggers-native/b.md) | B |
| [triggers-native/c.md](triggers-native/c.md) | C |
| [triggers-native/d.md](triggers-native/d.md) | D |
| [triggers-native/e.md](triggers-native/e.md) | E |
| [triggers-native/f.md](triggers-native/f.md) | F |
| [triggers-native/g.md](triggers-native/g.md) | G |
| [triggers-native/h.md](triggers-native/h.md) | H |
| [triggers-native/i.md](triggers-native/i.md) | I |
| [triggers-native/k.md](triggers-native/k.md) | K |
| [triggers-native/l.md](triggers-native/l.md) | L |
| [triggers-native/m.md](triggers-native/m.md) | M |
| [triggers-native/n.md](triggers-native/n.md) | N |
| [triggers-native/o.md](triggers-native/o.md) | O |
| [triggers-native/p.md](triggers-native/p.md) | P |
| [triggers-native/q.md](triggers-native/q.md) | Q |
| [triggers-native/r.md](triggers-native/r.md) | R |
| [triggers-native/s.md](triggers-native/s.md) | S |
| [triggers-native/t.md](triggers-native/t.md) | T |
| [triggers-native/u.md](triggers-native/u.md) | U |
| [triggers-native/v.md](triggers-native/v.md) | V |
| [triggers-native/w.md](triggers-native/w.md) | W |
| [triggers-native/other.md](triggers-native/other.md) | `_other` |

## Full native function reference (3,196 entries)

All 3,196 FunctionDef IDs were reconciled with the supplied official Core NativeLib on 2026-10-07, including eight previously missing rows. Use [the definition query](trigger-knowledge.md) for full parameter IDs, defaults, presets and sub-action definitions, and to confirm target dependency availability.

Every `FunctionDef` in `Ntve` (`Core.SC2Mod` nativelib). Sorted
alphabetically by name; bucketed by first letter so you can jump.

Columns:
- **Name** — the Galaxy identifier (also what the editor displays after
  TriggerStrings localisation, in most cases). Reference in XML as
  `<FunctionDef Type="FunctionDef" Library="Ntve" Id="<ID>"/>`.
- **ID** — 8-char hex.
- **Kind** — `call` (returns a value, has `<ReturnType>`), `action`
  (void / statement), `event` (registration native — call inside an
  `<Event>`-referenced FunctionCall element).
- **Returns** — return type, with `<gameType>` suffix for catalog-linked
  types (`gamelink<Unit>` etc.). `—` for actions/events.
- **Params** — comma-separated `name:type` list. Type is the Galaxy
  primitive (`int`, `fixed`, `string`, `bool`, `unit`, `point`,
  `region`, `text`, etc.) or `gamelink<X>` for catalog refs or `preset`
  for enum-typed slots. `—` for no params. `+Nsub` suffix means the
  native has N SubFunctionType slots (e.g. IfThenElse's then/else, loop
  bodies, conditions) — look up the SubFuncType IDs in nativelib before
  embedding child FunctionCalls.

Reminder from gotcha #11: parameter defaults in nativelib do NOT
auto-apply. Even if a param has a `<Default>` element, you MUST emit an
explicit `<Parameter Type="Param" Id="…"/>` for every slot in the
`<FunctionCall>` you construct.


