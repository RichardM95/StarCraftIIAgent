---
name: galaxy-triggers-and-functions
description: Trigger declaration, event registration, async execution via TriggerExecute, the static parameter pattern for functions that use Wait, trigger management, cinematic sequencer queue, and common event types in Galaxy script. Use when creating triggers, attaching events, executing async functions, or building the trigger init chain. Do not use for unit-specific events (use galaxy-units-and-groups) or dialog events (use galaxy-ui-and-dialogs).
---

## Loading Boundary

- **This sub-skill owns:** trigger declaration, event registration, async TriggerExecute, the static parameter pattern for Wait-using functions, trigger management, cinematic sequencer queue, and common event types
- **Parent root skill (`sc2-galaxy-scripting`) owns:** project conventions, schema/syntax rules, source-of-truth, naming prefixes
- **Sibling sub-skills own:** `galaxy-units-and-groups` (unit-specific events), `galaxy-ui-and-dialogs` (dialog events), `galaxy-game-systems` (init chain/spawners)

# Galaxy Scripting – Triggers & Functions

## Prerequisite

Load [`sc2-galaxy-scripting`](../../sc2-galaxy-scripting/SKILL.md) first for project-wide Galaxy syntax constraints (variable hoisting, no `++`/`--`, `while` not `for`, include paths without extensions), source-of-truth rules, modular script boundaries, and naming conventions (e.g. `libMy_` function prefix, `libMy_g_` global prefix). This sub-skill owns deep API reference only; project conventions live in the router skill.

## Key References

| Resource | URL |
|---|---|
| Native function reference | https://mapster.talv.space/galaxy/reference |
| Galaxy script tutorial | https://s2editor-guides.readthedocs.io/New_Tutorials/03_Trigger_Editor/058_GalaxyScript/ |
| Multithreading guide | https://s2editor-guides.readthedocs.io/New_Tutorials/03_Trigger_Editor/057_Multithreading_with_Action_Definitions/ |
| Trigger Debugger guide | https://s2editor-guides.readthedocs.io/New_Tutorials/03_Trigger_Editor/053_Trigger_Debugger/ |
| Optimizing Code guide | https://s2editor-guides.readthedocs.io/New_Tutorials/03_Trigger_Editor/056_Optimizing_Code/ |
| Galaxy syntax definition | https://github.com/Talv/vscode-sc2-galaxy/blob/master/syntaxes/galaxy.json |
| **SC2-IngameDevTools (PRIMARY — #1 codebase)** | https://github.com/abrahamYG/SC2-IngameDevTools/tree/main/DevToolsIngame.SC2Mod/Script |
| SSF codebase (secondary style) | https://github.com/Cristall/SC2-SwarmSpecialForces/tree/main/SwarmSpecialForces.SC2Map/scripts |
| Alcyone Frontlines codebase | https://github.com/KimPlaybit/Alcyone_Frontlines/tree/master/ProximaFrontlines.SC2Mod/scripts |
| NativeLib | `TriggerLibs/NativeLib.galaxy` (sc2galaxy VS Code extension) |
| SC2Mapster wiki | https://sc2mapster.wiki.gg/ |
| Triggers overview (wiki) | https://sc2mapster.wiki.gg/wiki/Triggers |

---

---

## Functions

```galaxy
// Basic function
int Plus(int i, int j) {
    int result = i + j;   // locals declared at TOP of function, before any logic
    return result;
}

// void function (no return value)
void DoSomething(string lp_name, int lp_count) {
    // implementation
}

// File-private function (cannot be called from other files)
static bool IsInternal() {
    return true;
}

// Native function declaration (maps to engine internals)
native int AIGetRawGasNumSpots(int player, int town);

// Custom typedef / function pointer type
void MyCallback_t();
typedef funcref<MyCallback_t> MyCallbackRef;
```

**Rules:**
- All local variables **must** be declared at the very top of a function, before any statements or function calls.
- `var++` is not valid. Use `var += 1`.
- `static` makes a function file-private.
- Lines must not exceed 2048 characters.
- No `/* */` block comments—only `//` line comments.

---

## Triggers

A trigger is a named callback function registered to fire on certain game events.

### ⭐ SC2-IngameDevTools trigger registration pattern (PRIMARY — use this)

The SC2-IngameDevTools codebase uses a clean, consistent pattern for registering triggers by string name inside each module's `_Init()` function. This is the pattern to follow:

```galaxy
// Handler functions always have the bool(bool,bool) signature
bool BehaviorContainerSendHandler(bool a, bool b) {
    // ... handler logic
    return true;
}

bool BehaviorListBoxFilterQuery(bool a, bool b) {
    int player = EventPlayer();
    playergroup pg = PlayerGroupSingle(player);
    string val = DialogControlGetPropertyAsString(
        ListBoxFilter.editbox, c_triggerControlPropertyEditText, player);
    ItemList_FilterListRebuild(ItemList, ListBoxFilter, val, pg);
    return true;
}

void BehaviorHandler_Init() {
    trigger t;
    // Register trigger by STRING name — the string must exactly match the function name
    t = TriggerCreate("BehaviorContainerSendHandler");
    TriggerAddEventDialogControl(t, c_playerAny, BehaviorContainer.addButton,
        c_triggerControlEventTypeClick);
    TriggerAddEventDialogControl(t, c_playerAny, BehaviorContainer.removeButton,
        c_triggerControlEventTypeClick);

    // Filter query trigger
    t = TriggerCreate("BehaviorListBoxFilterQuery");
    TriggerAddEventDialogControl(t, c_playerAny, ListBoxFilter.editbox,
        c_triggerControlEventTypeTextChanged);
}
```

Key rules from this pattern:
- Trigger functions always have signature `bool FunctionName(bool a, bool b)`.
- `TriggerCreate("FunctionName")` — the string is the **exact function name** as written in code.
- Each module's `_Init()` creates all its own triggers and hooks its own events.
- `trigger t;` is declared as a local and reused for multiple registrations in the same `_Init()`.
- Chat message triggers use `TriggerAddEventChatMessage(t, c_playerAny, "commandString", false)`.
- Generic event triggers use `TriggerAddEventGeneric(handler, "EventName")` + `TriggerSendEvent("EventName")`.

```galaxy
// Chat command registration (from DevTools/ChatCommand.galaxy)
trigger DevTools_ChatCommand;

void DevTools_ChatCommand_Init() {
    DevTools_ChatCommand = TriggerCreate("DevTools_ChatCommand_Func");
    // Commands registered later via DevTools_ChatCommandCreate():
    //   TriggerAddEventChatMessage(DevTools_ChatCommand, c_playerAny, cmd, false);
    //   TriggerAddEventGeneric(handler, "DevTools_ChatCommand.Exec."+cmd);
}

void DevTools_ChatCommandCreate(string cmd, trigger handler, text description) {
    ItemListAdd(ItemList, cmd);
    TriggerAddEventChatMessage(DevTools_ChatCommand, c_playerAny, cmd, false);
    TriggerAddEventGeneric(handler, "DevTools_ChatCommand.Exec."+cmd);
    DevTools_ChatCommandSetDescription(cmd, description);
}

void DevTools_ChatCommandSend(string cmd) {
    TriggerSendEvent("DevTools_ChatCommand.Exec."+cmd);
}
```

### Declaring a trigger global

```galaxy
// In the header (_h.galaxy) — replace libXXXXXXXX_ with your mod's auto-generated library prefix:
trigger libXXXXXXXX_gt_SpawnUnits;
trigger libXXXXXXXX_gt_WinTeam1;
```

### Full trigger pattern (as generated by the editor)

```galaxy
// 1. The logic function — bool (bool testConds, bool runActions)
bool gt_SpawnUnits_Func(bool testConds, bool runActions) {
    // Conditions block
    if (testConds) {
        if (!(someCondition)) { return false; }
    }
    // Actions block
    if (!runActions) { return true; }

    // ... do work ...

    return true;
}

// 2. The init function — registers event(s) onto the trigger
void gt_SpawnUnits_Init() {
    gt_SpawnUnits = TriggerCreate("gt_SpawnUnits_Func");
    TriggerEnable(gt_SpawnUnits, true);
    // attach one or more events:
    TriggerAddEventTimePeriodic(gt_SpawnUnits, 10.0, c_timeGame);
}
```

### Creating a trigger dynamically (async / separate thread)

```galaxy
trigger MyGlobalTrigger;

bool MyTrigger_Func(bool testConds, bool runActions) {
    UIDisplayMessage(PlayerGroupSingle(EventPlayer()), c_messageAreaChat,
        StringToText(EventChatMessage()));
    return true;
}

void MyTrigger_Init() {
    MyGlobalTrigger = TriggerCreate("MyTrigger_Func");
    TriggerAddEventChatMessage(MyGlobalTrigger, c_playerAny, "echo", false);
}
```

### Trigger management functions

| Function | Signature | Purpose |
|---|---|---|
| `TriggerCreate` | `trigger (string funcName)` | Create trigger from function name string |
| `TriggerExecute` | `void (trigger t, bool checkConds, bool runActions)` | Run trigger immediately |
| `TriggerEnable` | `void (trigger t, bool enabled)` | Turn on/off |
| `TriggerIsEnabled` | `bool (trigger t)` | Check if on |
| `TriggerDestroy` | `void (trigger t)` | Remove trigger |
| `TriggerStop` | `void (trigger t)` | Stop executing trigger |
| `TriggerGetCurrent` | `trigger ()` | Currently running trigger |
| `TriggerEvaluate` | `bool (trigger t)` | Run condition check only |
| `TriggerGetExecCount` | `int (trigger t)` | How many times it has fired |
| `TriggerActiveCount` | `int ()` | Count of currently active triggers |

### Wrapping functions that need async execution (SSF pattern)

When a function needs `Wait()` or long-running logic, wrap it in a trigger. Use `static` file-scope variables as parameter registers, capturing them into locals immediately:

```galaxy
// Declare param register at file scope
static int Utility_DelayedTextTagDestroyer_ParamTextTag;
static trigger Utility_DelayedTextTagDestroyer_Trigger;

void Utility_DelayedTextTagCreate(text inText, color inColor, point position, playergroup pg, fixed offset) {
    // Store param in static, then kick the trigger
    Utility_DelayedTextTagDestroyer_ParamTextTag = TextTagCreate(TextWithColor(inText, inColor), 24, position, offset, true, false, pg);
    TextTagSetVelocity(Utility_DelayedTextTagDestroyer_ParamTextTag, 1.0, 90.0);
    TriggerExecute(Utility_DelayedTextTagDestroyer_Trigger, false, false);
}

bool Utility_DelayedTextTagDestroyer(bool testCond, bool runActions) {
    // Capture static into local BEFORE any Wait() — the static may be overwritten
    int textTag = Utility_DelayedTextTagDestroyer_ParamTextTag;
    Wait(3.5, c_timeGame);
    TextTagDestroy(textTag);
    return true;
}

// Init: register the trigger once
void Utilities_Init() {
    Utility_DelayedTextTagDestroyer_Trigger = TriggerCreate("Utility_DelayedTextTagDestroyer");
}
```

**Key rule:** Always copy the static into a local at the very top of the handler body, before any `Wait()`. Otherwise a concurrent call will overwrite the static before your thread reads it.

---

## Common Events

### Time events

```galaxy
TriggerAddEventMapInit(myTrigger);                        // map loads
TriggerAddEventTimeElapsed(myTrigger, 5.0, c_timeGame);   // after 5 seconds
TriggerAddEventTimePeriodic(myTrigger, 3.0, c_timeGame);  // every 3 seconds
TriggerAddEventTimer(myTrigger, myTimer);                 // when a timer expires
```

### Unit events

```galaxy
TriggerAddEventUnitDied(myTrigger, null, false);
TriggerAddEventUnitCreated(myTrigger, null, "", "");
TriggerAddEventUnitGainLevel(myTrigger, null);
TriggerAddEventUnitGainExperience(myTrigger, null);
TriggerAddEventUnitBehaviorChange(myTrigger, null, "", 0);
TriggerAddEventUnitRegion(myTrigger, null, someRegion, true);
TriggerAddEventUnitOrder(myTrigger, null, null);
TriggerAddEventUnitBecomesIdle(myTrigger, null);
TriggerAddEventUnitProperty(myTrigger, null, c_unitPropLife);

// Range-based proximity events
TriggerAddEventUnitRange(myTrigger, lv_unit, lv_nearUnit, 5.0, true);   // unit enters/exits radius of another unit
TriggerAddEventUnitRangePoint(myTrigger, null, lv_point, 8.0, true);    // any unit enters/exits radius of a point

// Unit is issued a specific ability order
TriggerAddEventUnitOrder(myTrigger, null, AbilityCommand("move", 0));

// Unit is attacked (EventUnitTarget() returns the attacker)
TriggerAddEventUnitAttacked(myTrigger, null);
unit lv_attacker = EventUnitTarget();   // inside handler

// Unit loaded/unloaded as cargo
TriggerAddEventUnitCargo(myTrigger, null, false);  // false = load event, true = unload

// Unit takes fatal damage (use with UnitDied for damage-source filtering)
TriggerAddEventUnitDamaged(myTrigger, null, c_unitDamageTypeAny, c_unitDamageFatal, null);

// Event accessors inside the trigger func:
unit lv_unit   = EventUnit();
int  lv_player = EventPlayer();
```

### Player / UI events

```galaxy
TriggerAddEventChatMessage(myTrigger, c_playerAny, "!cmd", false);
TriggerAddEventDialogControl(myTrigger, c_playerAny, myButton, c_triggerControlEventTypeClick);
TriggerAddEventPlayerJoin(myTrigger);
TriggerAddEventPlayerLeft(myTrigger, c_playerAny, c_gameOverLeave);
TriggerAddEventPlayerPropChange(myTrigger, c_playerAny, c_playerPropMinerals);
TriggerAddEventKeyPressed(myTrigger, c_playerAny, 'A', true, 0);
TriggerAddEventUpgradeLevelChanged(myTrigger, c_playerAny);
```

### Generic / custom events

```galaxy
TriggerSendEvent("MyCustomEvent");
TriggerAddEventGeneric(myTrigger, c_playerAny, "MyCustomEvent");
string lv_name = EventGenericName(); // inside handler
```

---

## Wait

`Wait` blocks the current trigger thread without blocking others:

```galaxy
Wait(0.5, c_timeGame);   // wait 0.5 game seconds
Wait(2.0, c_timeReal);   // wait 2 real seconds
```

---

## Timers

```galaxy
timer lv_t = TimerCreate();
TimerStart(lv_t, 10.0, false, c_timeGame);   // one-shot after 10s
TimerStart(lv_t, 5.0, true, c_timeGame);     // repeating every 5s
TimerPause(lv_t, true);
fixed lv_remaining = TimerGetDuration(lv_t);
libNtve_gf_StopTimer(lv_t);

// Fire a trigger when it expires:
TriggerAddEventTimer(myTrigger, lv_t);
timer lv_fired = EventTimer(); // in handler
```

---

## Map Init / Trigger Registration Pattern (SSF)

In SSF-style maps, `main()` registers a single map-init trigger. Each module registers its own triggers in a dedicated `_TriggerCreate()` function:

```galaxy
// scripts/main.galaxy
void main() {
    TriggerAddEventMapInit(TriggerCreate("MapInit_Main"));
}

// scripts/MapInit.galaxy
bool MapInit_Main(bool testCond, bool runActions) {
    MapInit_ActivePlayers();
    SSFCustomUI_Init();
    PartTerran_TriggerCreate();   // each module registers its own triggers
    PartProtoss_TriggerCreate();
    PartZerg_TriggerCreate();
    return true;
}

// scripts/PartTerran.galaxy
void PartTerran_TriggerCreate() {
    TriggerAddEventUnitDied(TriggerCreate("PartTerran_SomeHandler"), null, false);
}
```

### Library mod pattern (alternate)
```galaxy
// Replace libXXXXXXXX_ with your mod's auto-generated library prefix.
void libXXXXXXXX_InitTriggers() {
    libXXXXXXXX_gt_SpawnUnits_Init();
    libXXXXXXXX_gt_WinTeam1_Init();
    // ... all _Init calls ...
}
```

---

## Action Queue / Cinematic Sequencer

The trigger queue serializes long-running cinematic triggers so they don't overlap.

```galaxy
// Enter the queue at the START of a cinematic trigger
TriggerQueueEnter();
// ... all cinematic steps ...
TriggerQueueExit();   // release queue at END

// Pause / resume the queue
TriggerQueuePause(true);   // block next trigger from starting
TriggerQueuePause(false);  // resume

// Discard pending items
TriggerQueueClear(c_triggerQueueRemove);

// Check if the queue is empty (useful in victory checks)
bool lv_empty = TriggerQueueIsEmpty();
```

---

## Scope / Visibility

```galaxy
// File-private (not callable from outside)
static bool HelperFunc() { return true; }

// Public (callable from any file that is compiled together)
bool PublicFunc() { return HelperFunc(); }
```

> Functions can be declared before they are defined (forward declarations).  
> As long as files are all included into `MapScript.galaxy`, you can call any function from any file without a local `include`.

---

## Multithreading / Async Execution

### How Galaxy "multithreading" works (time-slicing)

Galaxy does **not** have true parallel execution. The editor implements **cooperative multithreading** via time-slicing:

1. A threaded trigger/action-def runs normally until it hits a `Wait()`.
2. At `Wait()`, control returns to the parent thread (or the next pending event).
3. When the wait resolves, control returns to the suspended thread.

This "fakes" parallelism by rapidly switching linear control around `Wait()` boundaries. It is **not** faster than sequential code — in fact, threaded code runs slower due to the overhead of managing thread state.

> **Source:** [Multithreading With Action Definitions](https://s2editor-guides.readthedocs.io/New_Tutorials/03_Trigger_Editor/057_Multithreading_with_Action_Definitions/)

### TriggerExecute — fire a trigger in its own thread

```galaxy
// Run trigger NOW in the SAME thread (blocks until done)
TriggerExecute(myTrigger, false, false);

// Run trigger in its OWN thread (returns immediately; trigger runs concurrently)
TriggerExecute(myTrigger, false, true);   // third arg = separate thread
```

The static-param pattern (see the Async section above) is the correct way to pass parameters into a trigger-based async function.

### Auto-generated implementation of threaded action definitions

When the GUI editor creates a threaded action definition, it generates:

```galaxy
// 1. Global parameter registers (one per action-def parameter)
int auto_gf_MyActionDef_lp_param;

// 2. Global trigger variable (created once, reused)
trigger auto_gf_MyActionDef_Trigger = null;

// 3. The trigger function body — captures params into locals BEFORE any Wait
bool auto_gf_MyActionDef_TriggerFunc(bool testConds, bool runActions) {
    int lp_param = auto_gf_MyActionDef_lp_param; // capture to local immediately
    Wait(5.0, c_timeGame);
    // use lp_param here safely
    return true;
}

// 4. Wrapper called at each invocation — copies args into global registers, fires trigger
void gf_MyActionDef(int lp_param) {
    auto_gf_MyActionDef_lp_param = lp_param;       // write to global register
    if (auto_gf_MyActionDef_Trigger == null) {
        auto_gf_MyActionDef_Trigger = TriggerCreate("auto_gf_MyActionDef_TriggerFunc");
    }
    TriggerExecute(auto_gf_MyActionDef_Trigger, false, true); // run in new thread
}
```

**Key rule:** Capture the global parameter register into a local variable **at the very first line** of the thread function, before any `Wait()`. Otherwise a new call can overwrite the global before the thread reads it.

### Performance notes

- Multithreaded action definitions run noticeably slower than non-threaded equivalents.
- Use threading only when you genuinely need concurrent `Wait()`-based timelines (e.g., five marines each on a 5-second lifecycle running in parallel).
- For one-off delays, a `Timer`-based trigger is usually simpler and cheaper.
