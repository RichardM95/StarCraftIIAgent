# Galaxy Language Gotchas

Confirmed compile errors and API surprises in StarCraft II Galaxy Script. Check here before writing any Galaxy code.

For a full Galaxy language primer, see [wiki/reference/galaxy-language.md](../reference/galaxy-language.md).  
For SC2 bank function signatures, see [wiki/reference/galaxy-bank.md](../reference/galaxy-bank.md).

---

## Confirmed Compile Errors & Syntax Rules

### Custom Script XML indentation

When writing a FunctionCall's `<ScriptCode>` in the current Triggers layout,
prefix every code line with the 16 spaces used by Editor-authored script blocks.
The Editor's code generation removes this indentation; unindented code can lose
the first 16 characters of each statement. A reported Bank diagnostic compile
error showed `if (EventChatMessage(false)` becoming `sage(false)`.
Check the generated code after Editor save. XML parsing and the ordinary
catalog/Galaxy validator do not compile embedded Custom Script.

```galaxy
// Array declaration — CORRECT syntax:
string[90] arr;
// NOT: string arr[90];

// Dialog/dialogitem variables — always primitive int:
int myDialog;
int myButton;

// Global variable initializers — integer/fixed literals only:
int gMyCount = 0;
// NOT: int gMyDialog = c_invalidDialog;  <-- causes compile error

// Trigger action function signature:
bool MyAction(bool testConds, bool runActions) { ... }

// Get the unit that triggered a unit event:
lv_u = EventUnit();
// NOT: UnitFromEvent()  <-- does not exist, causes syntax error

// Calling a galaxy function from a GUI trigger (use #PARAM):
MySetCurrentMap(#PARAM(name));  // use your Galaxy function prefix from AGENTS.md

// Local variable declarations — must be at the TOP of the function body:
bool MyFunc(bool testConds, bool runActions) {
    trigger orbTrig;   // correct: declared at top, no initializer
    if (!runActions) { return true; }
    orbTrig = TriggerCreate("Foo");  // correct: assigned in body
    // NOT: trigger orbTrig = TriggerCreate("Foo");  <-- inline init causes parse error
    // NOT: declared inside an if/else/while block   <-- also invalid
}

// Unit created event — correct function and parameter count (4 params):
TriggerAddEventUnitCreated(myTrig, null, null, "");  // any unit
TriggerAddEventUnitCreated(myTrig, null, "Zergling", "");  // specific type
// NOT: TriggerAddEventUnitBirth(myTrig, null)  <-- function does not exist
// NOT: TriggerAddEventUnitCreated(myTrig, null, null)  <-- wrong param count (needs 4th "" arg)

// Reading a unit's current max life (or any max-value property):
fixed hp = UnitGetPropertyFixed(u, c_unitPropLifeMax, c_unitPropCurrent);
// NOT: c_unitPropMax  <-- constant does not exist, causes "Invalid parameter"

// Increments / Decrements — use compound assignment:
count += 1;
// NOT: count++; or count--;  <-- unsupported operator, causes parse error

// Loops — use while (...):
while (i < 10) {
    // ...
    i += 1;
}
// NOT: for (i = 0; i < 10; i++)  <-- unsupported in SC2 custom script

// Include directives — relative path without extension:
include "Scripts/MyGlobals"
include "Scripts/MyBank"
// NOT: include "Scripts/MyGlobals.galaxy";  <-- causes file open failure
// NOT: #include "Scripts/MyGlobals.h";      <-- unsupported C preprocessor directive

// Dynamic catalog reflection paths must mirror XML element tree structure:
CatalogFieldValueSet(c_gameCatalogUnit, "Marine", "Armor", player, "1");
CatalogFieldValueSet(c_gameCatalogUnit, "Marine", "CostResource[Minerals]", player, "75");
```

---

## Modular Script Boundary Rules

1. **Top-Level Declarations:** Every included `.galaxy` file MUST begin with declarations at brace depth 0 and end with a closed function brace `}`. Splitting a function body across file boundaries produces compilation errors.
2. **Duplicate Functions:** Defining the same function name across multiple included scripts fails compilation with `"function already defined: <function_name>"`.
3. **Forward References:** Functions must be **defined before they are called** within script blocks. Calls from GUI triggers are linked independently, but script-to-script internal calls require the callee to appear first in the compilation order.

---

## Community Error Triage

- `Can only pass basic types`: Structs and arrays cannot be passed as regular function arguments. Pass scalar IDs/indices or use global data structures.
- `struct forward declaration not supported`: Define structs before functions or variables that use them.
- `Bulk copy not supported`: Assigning entire arrays/structs by value can fail. Copy scalar elements explicitly.
- `Could not allocate Global Memory` / `e_globalsTooLarge`: Global arrays consume real VM heap. Keep project state compact.
- `failed: 32k - 1 size limit to local variables`: Avoid huge local arrays; allocate small globals or split calculations.
- `Registry overflow`: A single expression has too many string, text, or point references. Break it into smaller statements.
- `Internal compiler error`: Can be caused by a single line or string longer than ~2046 characters.
