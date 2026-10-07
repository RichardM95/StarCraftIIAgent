# Custom transmission GUI actions

The AeonOfIhanrii mod library exports three editable GUI actions:

| Action | First input | Sender and portrait source |
|---|---|---|
| `Play Custom Transmission` | Sender (`text`) | Explicit Sender and PortraitModel inputs |
| `Play Custom Transmission By UnitType` | Unit Type (`gamelink<Unit>`) | `UnitTypeGetName` and `TransmissionSourceFromUnitType` |
| `Play Custom Transmission By Unit` | Unit (`unit`) | `UnitGetName` and `TransmissionSourceFromUnit` |

Both actions then take Message (`text`), Audio (`soundlink`), Wait
(`bool`), Beep (`bool`), and Wait Duration (`fixed`, default 2.0
seconds). Message remains `text` so the Trigger Editor can use
localized Chinese text directly.

Each action sends one transmission with its own portrait source,
selected audio, sender, and message. A campaign sound may have its own
`Speaker`, `Subtitle`, and `Portrait` catalog fields. Do not first send
that sound through `SendTransmissionSimple`, because that produces a
separate transmission using the sound's original presentation data.
The unit source functions enable `overridePortrait` so the selected unit
portrait takes precedence over the sound's catalog portrait.

`Play Custom Transmission By Unit` hides the cinematic BottomLeft portrait
before sending to CenterLeft. In `pulnar02` the preceding campaign-native
transmission uses BottomLeft during cinematic mode and can remain visible
briefly while its delayed cleanup runs. The targeted hide removes that
previous portrait without clearing transmission audio or other portrait
slots.

With Audio set to `EditorDefaultSound`, Wait Duration controls both
the transmission display and, when Wait is enabled, the time spent
waiting. With audio supplied, both use `SoundLengthSync(Audio)`.
Wait uses real time without audio and game time with audio. When Wait
is disabled, neither action adds a trailing delay.

`Play Custom Transmission` retains its six-input GUI signature because
campaign maps call it. With no audio its display duration is 2 seconds;
with audio it uses `SoundLengthSync(Audio)`. Wait follows that duration
when enabled and has no unconditional trailing delay. Maintain these
actions in the GUI `Triggers` source. Do not edit generated
`Lib67AA1763.galaxy`.

After changing component source, open and save the mod in SC2 Editor.
Confirm all three actions retain editable inputs and compile. Test a Chinese
message with and without audio, Wait on and off, and a non-default
duration. For the unit action, test a valid existing unit instance.
