# SC2 Native Functions: W

Columns are documented in [../triggers-native-functions.md](../triggers-native-functions.md). Reference in XML as `<FunctionDef Type="FunctionDef" Library="Ntve" Id="<ID>"/>`.

Parameter defaults in `nativelib` do not auto-apply; emit an explicit `<Parameter Type="Param" Id="..."/>` for every slot in generated `<FunctionCall>` XML.

### W

<a id="w"></a>

| Name | ID | Kind | Returns | Params |
|---|---|---|---|---|
| `Wait` | `00000242` | action | `—` | t:fixed, timeType:preset |
| `WaitForCondition` | `E89F1335` | action | `—` | t:fixed, timeType:preset +1sub |
| `WaitForConditionWithMaximumDuration` | `01DD8AFF` | action | `—` | t:fixed, timeType:preset, maxDuration:fixed +1sub |
| `WaitForCutsceneToEnd` | `0CDF60FB` | action | `—` | cutsceneId:preset |
| `WaitForProfilerLoggingToEnd` | `78CB0658` | action | `—` | — |
| `WaitForTimer` | `D34AEEAF` | action | `—` | timer:timer, time:fixed, waitType:preset |
| `WaterPause` | `E0519041` | action | `—` | waterType:gamelink<Water>, pauseUnpause:preset |
| `WaterSetState` | `56D51508` | action | `—` | waterState:water, duration:fixed, blendType:preset |
| `WaveLastCreated` | `7050204D` | call | `wave` | — |
| `While` | `71596144` | action | `—` | — +2sub |
| `While2` | `8B429DFA` | action | `—` | — +2sub |
| `WidthOfRegion` | `8C52DBB5` | call | `fixed` | region:region |
| `WithinBounds` | `1A5B44D4` | ? | `—` | value:anynumber, min:anynumber, max:anynumber |
| `WorldHeight` | `34643F2E` | call | `fixed` | type:preset, point:point |
