---
name: telemetry-hmi
description: Design, generate or review telemetry displays for UBC Solar (sunlink Grafana dashboards, the DRD driver LCD, Sunglasses strategy views) using situation-awareness and high-performance-HMI principles. Includes a Grafana dashboard generator with one consistent board layout, a linter that checks dashboard JSON against the car's DBC, and a live check that every panel returns data. Use when asked to build, rebuild, clean up, review or "make readable" a dashboard, panel or display, or to port dashboards to a new car/DBC.
---

# Telemetry HMI

A display is good when the person glancing at it knows, in a second or two, **whether
anything needs attention, what, and where it is heading**. Everything here serves that.
The method distils four sources (summaries in `references/`):

| Source | What we take from it |
|---|---|
| Endsley 1995, situation awareness (`references/endsley-situation-awareness.md`) | Design from the reader's goals: perception, then comprehension, then projection. Keep a global overview always visible, put critical cues in salient places, show data integrated into information |
| PAS High Performance HMI (`references/pas-high-performance-hmi.md`) | Grey when normal, colour only for abnormal; analog/trend with normal and alarm bands instead of bare numbers; display hierarchy; redundant alarm coding |
| Wickens 2008, multiple resources (`references/wickens-multiple-resources.md`) | Pit crew share attention between radio (auditory-verbal) and screen (visual-spatial): favour spatial/analog encodings, short text, few traces |
| FAA HF-STD-001B (`references/faa-hf-std-001b.md`) | Concrete rules: reserved colour meanings, at most 4 colours per screen, labelled axes with units, no more than 1 alphanumeric update per second, flashing only for urgent alarms |

## Method

1. **Task analysis first.** For each board/view, write down who reads it and their goals.
   For each goal list the L1 elements (what to perceive), L2 (what they mean: in band?
   reset? stuck?) and L3 (where they are heading: trend toward a limit). Only signals that
   serve a goal go on the top half of the screen.
2. **Get the facts from the source of truth.** Signal names, units, scaling and fault
   limits come from the DBC and firmware, not from the old dashboard. If a panel needs a
   signal the DBC lacks, check the firmware (`firmware_v4/firmware/components/<board>/`):
   firmware sends it → fix the DBC; firmware doesn't → fix or drop the panel. Write the
   evidence (file:line) into the PR.
3. **Use the standard board skeleton** (all boards identical, so readers know where to look):
   - **Row 1, Health & faults:** link freshness (s since last frame, red when stale),
     uptime (reset detector), MCU Vdd / temperature with the firmware fault limit as the
     red threshold, the board's key state, and **one fault strip** (state timeline, OK grey /
     FAULT red, `max` per window so a single faulted frame is never averaged away).
     Left of the strip, a **fault status tile** (`Board.fault_block`): ACTIVE FAULT (red) if any
     bit is set in the latest frame, FAULT IN WINDOW (yellow) if one was set in the range shown
     but has cleared, NO FAULTS (unfilled) otherwise.
   - **Rows 2+, grouped data:** one row per goal (e.g. GPS position & status, motion, IMU).
     Trends with the alarm band drawn in, at most 4 traces each; enums and bits as state
     timelines with a word for every state.
   - **Last, raw/diagnostic:** collapsed row for things you only need when diagnosing.
4. **Colour discipline.** Grey = normal/OK/off. Blue = active/advisory (an input is on, a
   less common mode). Orange = caution/marginal/timeout/unknown. Red = fault/out of limit.
   Never red or green as the only cue; every coloured state also has text. No decorative
   colour, 3D or animation. Values outside an enum table read "UNKNOWN" in orange.
   Alarm red is saturated (#ff1a1a) so it reads as an alarm, not decoration. Stat tiles fill
   with colour only when abnormal (normal and advisory states stay unfilled), so a red tile is
   the only filled thing on the row.
5. **Every numeric panel has a unit** (Grafana unit id or `suffix: <unit>`), and every panel
   title is `<BOARD>: <Signal> (<unit>)` per sunlink `docs/GRAFANA.md`. Dashboard titles are
   `<BUCKETS>: <TITLE> - <CAR>` with a fixed uid. Put the meaning and the source of each
   threshold in the panel description (knowledge in the display, not in someone's head).
6. **Verify, then look.** Lint against the DBC, prove every panel returns rows, then
   screenshot and review against this checklist. Random data proves queries and layout,
   not values; say so, and recheck on live or logged data when it's available.

## Tools (in this skill's `scripts/`)

| Script | Use |
|---|---|
| `hmi_grafana.py` | Library: `Board` (queries, freshness, uptime, faults), `Dash` (flow layout, rows, `below=True` stacking), `stat`, `trend` (alarm bands), `timeline` (state words, per-group mappings), `geomap` (OSM basemap, works offline from the CARTO key). Grafana 9.5 / schemaVersion 38 |
| `check_dashboard.py --dbc car.dbc *.json` | Every `_field` / `class` exists for that board in the DBC; numeric panels have units; naming; trace count. Exit 1 on errors. Run it on old dashboards too: it lists exactly which panels are stale |
| `check_panels_live.py *.json` | Runs every panel query through Grafana (`GRAFANA_URL`, `GRAFANA_AUTH`) and lists panels with no rows |

`examples/sunlink_cascadia.py` builds the four Cascadia board dashboards (TEL, MDI, DRD,
STR) and is the reference for new boards: `python examples/sunlink_cascadia.py <sunlink>/dashboards/PROD`.

## Sunlink specifics and gotchas

- InfluxDB layout: bucket `CAN_prod`, `_measurement` = DBC sender, `_field` = signal,
  tag `class` = message name. Filter on all three so same-named signals can't collide.
- Grafana 9.5 state timeline: colour mode must be `fixed`, not `thresholds`, or it merges
  states into threshold ranges ("-∞+") and ignores value mappings.
- Flux frames name series by `_field` once you `keep(["_time","_value","_field"])`; don't
  set `displayName` to `${__field.labels._field}` (it renders literally).
- Two groups on one state timeline from the same message can drop a row; if a row is
  missing, give it its own panel.
- Local test stack: `docker compose -p <name> up -d --no-deps influxdb grafana` with an
  untracked override that sets `DOCKER_INFLUXDB_INIT_MODE=setup` and the admin token, then
  `./link_telemetry.py -r can --prod -f 200 --force-random --batch-size 400 --local --dbc ./dbc/<car>.dbc`.
  Check that the parser really uses that DBC: the `--dbc` override only took effect for the
  random generator and decoder after they were changed to read `parameters.CAR_DBC` at
  call time, and enum (VAL_) signals need `decode_choices=False` or InfluxDB rejects the write.

## Review checklist

- [ ] Health and faults row on top, same layout as the other boards
- [ ] Every fault/flag bit in the DBC for this board is on the fault strip
- [ ] Thresholds match firmware limits (cited in the description)
- [ ] Units on every numeric panel; axis ranges sensible (min 0 where physical)
- [ ] Colour only for abnormal (plus blue for active inputs), always with text
- [ ] ≤ 4 traces per trend; trends for anything whose direction matters
- [ ] `check_dashboard.py` 0 errors; `check_panels_live.py` 0 empty
- [ ] Screenshot reviewed; differences from live data noted
