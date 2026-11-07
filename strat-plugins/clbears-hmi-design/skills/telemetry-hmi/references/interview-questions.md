# Interview questions for a telemetry display

Ask in rounds of up to 4, with options and a recommended default. Skip anything already
answered by the request, the code, the DBC/firmware or an earlier answer. Defaults below are
what UBC Solar's sunlink boards were designed for (2026); change them when the answers differ.

## Round 1: context (before any layout)

| Question | Options (default first) | Why it matters |
|---|---|---|
| Who watches this display? | Pit crew during a race · Embedded/electrical on the bench · Strategy · Driver (LCD) · Several of these | Sets the goals and the expertise level (Endsley: novices need more L2/L3 support built in) |
| In what situation? | Live race/test drive · Bench test of one board · Debugging logged data afterwards · Demo | Live: glanceability and alarms first. Debugging: detail, long time ranges, raw values |
| What decisions do they make from it? | Call the driver/stop the car · Swap/reboot a board · File a bug · Just monitor | Each decision needs its cue (L1) and its meaning (L2) on screen, together |
| What else are they doing at the same time? | Talking on the radio · Running other screens · Typing/debugging · Nothing else | Wickens: radio is auditory-verbal, so use spatial/analog encodings and few words |

## Round 2: what matters (after reading the DBC/firmware, before generating)

| Question | Options (default first) | Why it matters |
|---|---|---|
| Which signals are critical, which are nice to have? | Show my proposed split and let them move items | Critical goes in the health row/banner; nice-to-have goes lower or collapsed |
| What counts as abnormal where firmware has no limit? | Propose a value with its reasoning, e.g. "< 4 GPS satellites (no 3D fix)", "CAN bus load >= 70 %" | Judgement thresholds must be the users', not the designer's |
| What must be noticed out of the corner of the eye? | Active faults · Link lost · Warnings too · Only faults | Goes on the full-width banner; everything else stays quiet |
| Where and how is it viewed? | Pit laptop (~15", daylight) · Big screen in the pit tent · Desk monitor · Phone | Text size, panel density, contrast |
| What time range do they look at? | Last 5 min live · Whole session · A specific test window | Trend lengths, what "CLEARED" means, refresh rate |

## Checkpoints (during and after)

- **Thresholds:** list every limit, marking each as *firmware* (file:line) or *judgement*, and
  ask the users to confirm or change the judgement ones.
- **First screenshot:** "What is hard to read? What would you miss out of the corner of your
  eye? What is on screen that you never use?"
- **Ambiguous feedback** ("make it pop", "looks stupid", "too small"): offer 2-3 concrete
  alternatives with a preview each (ASCII mock-up or screenshot) and a recommended one.
- **Before handing over:** "Is anything missing for the situations you described in round 1?"
  Then run the situations (e.g. with the scenario simulator) and show them.

## Record

Write the answers into the PR description or a design note: who, situation, decisions,
critical signals, thresholds and their source (firmware / user / designer default).
