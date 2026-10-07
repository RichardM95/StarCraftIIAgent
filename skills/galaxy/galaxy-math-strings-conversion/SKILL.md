---
name: galaxy-math-strings-conversion
description: Integer and fixed-point math, trigonometry, random numbers, type conversions, string and text operations, color construction, bitwise operations, and number formatting for display in Galaxy script. Use when performing arithmetic, converting between int/fixed/string/text, building display strings, working with colors, or using NativeLib math helpers (ArithmeticIntClamp, Log, RandomPercent). Do not use for point/geometry math (use galaxy-points-regions-geometry).
---

## Loading Boundary

- **This sub-skill owns:** integer/fixed math, trigonometry, random numbers, type conversions, string/text operations, colors, bitwise ops, and number formatting
- **Parent root skill (`sc2-galaxy-scripting`) owns:** project conventions, schema/syntax rules, source-of-truth, naming prefixes
- **Sibling sub-skills own:** `galaxy-points-regions-geometry` (point/region math), `galaxy-language-fundamentals` (type system), `galaxy-debug-data-catalog` (debug print/output)

# Galaxy Scripting – Math, Strings & Conversion

## Prerequisite

Load [`sc2-galaxy-scripting`](../../sc2-galaxy-scripting/SKILL.md) first for project-wide Galaxy syntax constraints (variable hoisting, no `++`/`--`, `while` not `for`, include paths without extensions), source-of-truth rules, modular script boundaries, and naming conventions (e.g. `libMy_` function prefix, `libMy_g_` global prefix). This sub-skill owns deep API reference only; project conventions live in the router skill.

## Key References

| Resource | URL |
|---|---|
| Native function reference | https://mapster.talv.space/galaxy/reference |
| Per-function reference pages | https://mapster.talv.space/galaxy/reference/`function-name` (e.g. `/text-case`, `/string-case`, `/string-external`) |
| Galaxy syntax definition | https://github.com/Talv/vscode-sc2-galaxy/blob/master/syntaxes/galaxy.json |
| **SC2-IngameDevTools (PRIMARY — #1 codebase)** | https://github.com/abrahamYG/SC2-IngameDevTools/tree/main/DevToolsIngame.SC2Mod/Script |
| SSF codebase (secondary style) | https://github.com/Cristall/SC2-SwarmSpecialForces/tree/main/SwarmSpecialForces.SC2Map/scripts |
| NativeLib | `TriggerLibs/NativeLib.galaxy` — `libNtve_gf_Log`, `libNtve_gf_RandomPercent`, `libNtve_gf_ArithmeticIntClamp`, `libNtve_gf_ConvertBooleanToText`, conversion helpers |
| Math Functions guide | https://s2editor-guides.readthedocs.io/New_Tutorials/03_Trigger_Editor/045_Math_Functions/ |
| SC2Mapster wiki | https://sc2mapster.wiki.gg/ |

---

## Integer Math

```galaxy
int lv_a = 10;
int lv_b = 3;

int lv_sum  = lv_a + lv_b;
int lv_diff = lv_a - lv_b;
int lv_mul  = lv_a * lv_b;
int lv_div  = lv_a / lv_b;      // integer division — truncates
int lv_mod  = ModI(lv_a, lv_b); // remainder (no % operator)
int lv_min  = MinI(lv_a, lv_b);
int lv_max  = MaxI(lv_a, lv_b);
int lv_abs  = AbsI(lv_a);
```

## Fixed-Point Math

Galaxy uses `fixed` instead of `float`. Precision is typically 1/65536.

```galaxy
fixed lv_x = 3.5;
fixed lv_y = 1.25;

fixed lv_sum  = lv_x + lv_y;
fixed lv_mul  = lv_x * lv_y;
fixed lv_min  = MinF(lv_x, lv_y);
fixed lv_max  = MaxF(lv_x, lv_y);
fixed lv_abs  = Abs(lv_x);
fixed lv_sqrt = Sqrt(lv_x);
fixed lv_pow  = Pow(lv_x, 2.0);
fixed lv_log2 = Log2(lv_x);
fixed lv_fl   = Floor(lv_x);
fixed lv_ceil = Ceiling(lv_x);
fixed lv_pi   = 3.14159;                 // no built-in Pi constant

// NativeLib math helpers (from TriggerLibs/NativeLib.galaxy):
// libNtve_gf_Log(x, base) — computes log base `base` of `x`
fixed lv_log10 = libNtve_gf_Log(lv_x, 10.0);   // log base 10
fixed lv_ln    = libNtve_gf_Log(lv_x, 2.71828); // natural log (approx)

// Clamp helpers:
int   lv_ci = libNtve_gf_ArithmeticIntClamp(lv_value, 0, 100);   // clamps int to [0,100]
fixed lv_cf = libNtve_gf_ArithmeticRealClamp(lv_value, 0.0, 1.0); // clamps fixed to [0,1]
```

## Trigonometry

Angles in Galaxy are in **degrees** (not radians).

```galaxy
fixed lv_sin = Sin(45.0);
fixed lv_cos = Cos(90.0);
fixed lv_tan = Tan(45.0);
fixed lv_asin = ASin(0.5);   // returns degrees
fixed lv_acos = ACos(0.5);
fixed lv_atan = ATan(1.0);
fixed lv_atan2 = ATan2(lv_dy, lv_dx);   // angle from delta components
```

## Random Numbers

```galaxy
int   lv_ri    = RandomInt(1, 10);             // [min, max] inclusive
fixed lv_rf    = RandomFixed(0.0, 1.0);        // [min, max]

// NativeLib random helpers:
fixed lv_pct   = libNtve_gf_RandomPercent();  // random fixed 0.0–100.0
fixed lv_angle = libNtve_gf_RandomAngle();    // random fixed 0.0–360.0
```

---

## Type Conversions

```galaxy
// int ↔ fixed ↔ string ↔ text
fixed lv_f  = IntToFixed(5);
int   lv_i  = FixedToInt(3.7);           // truncates towards zero
int   lv_i2 = FloorI(FixedToInt(3.7));   // same here
string lv_s = IntToString(42);
string lv_sf = FixedToString(3.14);
text   lv_t  = IntToText(42);
text   lv_tf = FixedToText(3.14, c_fixedPrecisionAny);
text   lv_tfa = FixedToTextAdvanced(3.14159, 2, true, false); // 2 decimals
int    lv_si = StringToInt("99");
fixed  lv_sf2 = StringToFixed("3.14");
text   lv_ts  = StringToText("hello");
string lv_st  = TextToString(lv_t);       // loses formatting

// bool conversions
int  lv_bi = BoolToInt(true);            // 1 or 0
bool lv_ib = (lv_bi != 0);

// NativeLib bool/string/point conversion helpers:
text   lv_bt  = libNtve_gf_ConvertBooleanToText(true);    // returns text "True"/"False"
string lv_bs  = libNtve_gf_ConvertBooleanToString(true);  // returns string "true"/"false"
bool   lv_sb  = libNtve_gf_ConvertStringToBoolean("true"); // string → bool

// Point ↔ string (useful for bank storage of positions)
string lv_ps  = libNtve_gf_ConvertPointToString(lv_point);   // "(x,y)"
point  lv_sp  = libNtve_gf_ConvertStringToPoint("(16.0,32.0)");
```

## Color

```galaxy
// Define colors (components 0.0–1.0)
color lv_red   = Color(1.0, 0.0, 0.0);
color lv_white = ColorWithAlpha(1.0, 1.0, 1.0, 1.0);  // r, g, b, a

// Get a component
fixed lv_r = ColorGetComponent(lv_red, c_colorComponentRed);

// Player team color — convert player slot to color
color lv_pc = libNtve_gf_ConvertPlayerColorToColor(lv_player);
// (int playerSlot) — returns the player's team color as a color value

// From index
color lv_ci = ColorFromIndex(3, c_teamColorType);

// Convert 0-255 integer to 0.0-1.0
fixed lv_norm = Color255FromFixed(128) / 255.0;

// NativeLib color/string helpers:
string lv_colorStr = libNtve_gf_ConvertColorToString(lv_red);
// Returns the color as a string (e.g. for debug or bank storage)
```

---

## Strings

```galaxy
// Concatenation (+ operator)
string lv_full = "Hello" + ", " + PlayerName(lv_player) + "!";

// Length
int lv_len = StringLength(lv_str);

// Equality
bool lv_eq = StringEqual(lv_a, lv_b, c_stringNoCase);  // or c_stringCase

// Compare (lexicographic)
int lv_cmp = StringCompare(lv_a, lv_b, c_stringNoCase);  // -1, 0, 1

// Substring tests
bool lv_has = StringContains(lv_str, "zerg", c_stringAnywhere, c_stringNoCase);
int  lv_pos = StringFind(lv_str, "zerg", c_stringAnywhere, c_stringNoCase);
// returns c_stringNotFound (-1) if not found

// Extract
string lv_sub  = StringSub(lv_str, 1, 4);     // chars 1..4 (1-based)
string lv_word = StringWord(lv_str, 2);        // 2nd whitespace-delimited word

// Replace
string lv_rep  = StringReplace(lv_str, "old", "new", c_stringReplaceAll);
string lv_rep2 = StringReplaceWord(lv_str, "colour", "color");

// Containment location constants
c_stringAnywhere
c_stringBeginsWith
c_stringEndsWith

// Case constants
c_stringCase      // case-sensitive
c_stringNoCase    // case-insensitive
```

## Text (localized, rich)

```galaxy
// Build text
text lv_t = StringToText("plain string");

// Concatenate text
text lv_combined = lv_t1 + StringToText(" ") + lv_t2;

// Colorize text
text lv_colored = TextWithColor(lv_t, ColorWithAlpha(1.0, 0.4, 0.4, 1.0));

// Localized string from GameStrings.txt
text lv_loc = StringExternal("Param/Value/libXXXXXXXX_MyKey"); // replace prefix with your mod's prefix

// Text replace
text lv_tr = TextReplaceWord(lv_t, "old", StringToText("new"));

// Case conversion — text type
text lv_upper = TextCase(lv_t, true);   // UPPERCASE
text lv_lower = TextCase(lv_t, false);  // lowercase

// Case conversion — string type
string lv_up = StringCase(lv_s, true);  // UPPERCASE
string lv_lo = StringCase(lv_s, false); // lowercase

// Localized hotkey or asset path (companion to StringExternal)
text lv_hk  = StringExternalHotkey("Param/Hotkey/MyAbility"); // e.g. "Q"
string lv_asset = StringExternalAsset("Param/Asset/MyIcon");  // asset path string

// Text expression tokens (build parameterized display strings)
TextExpressionSetToken("Param/Expression/MyExpr", "UNIT", TextCase(UnitTypeGetName(UnitGetType(lv_unit)), true));
text lv_result = TextExpressionAssemble("Param/Expression/MyExpr");
```

---

## Bitwise Operations

```galaxy
int lv_flags = 0;
lv_flags = lv_flags | (1 << 3);   // set bit 3
lv_flags = lv_flags & ~(1 << 3);  // clear bit 3
bool lv_set = ((lv_flags & (1 << 3)) != 0);

// BitMask type (for unit filters etc.)
bitmask lv_mask = BitMaskMakeDefaultMask();
BitMaskSetIndex(lv_mask, 5, true);
bool lv_bit = BitMaskTrueIndex(lv_mask, 5);
```

---

## Formatting Numbers for Display

```galaxy
// Fixed with N decimal places
text lv_pct = FixedToTextAdvanced(66.667, 1, false, false);  // "66.7"

// Integer to padded string
string lv_padded = "00" + IntToString(lv_n);  // manual zero-pad
lv_padded = StringSub(lv_padded, StringLength(lv_padded) - 1, StringLength(lv_padded));

// Combine for display (e.g. kill counter)
text lv_display = IntToText(lv_kills) + StringToText(" kills");
```
