---
name: can-sync
description: Sync a firmware_v4 board's CAN messages into sunlink - diff the board's CAN TX code against the DBC, add/fix signals in sunlink/dbc/brightside.dbc, and add or update panels on that board's Grafana dashboard (dashboards/PROD/PROD_<BOARD>_Brightside.json) and its section of the Pit Crew dashboard. Use when the user asks to sync/update the DBC, add a CAN signal or message to telemetry, or update the DRD/STR/TEL/MDI/... dashboard or pit crew dashboard after a firmware CAN change.
---

# CAN sync: firmware_v4 → sunlink DBC → Grafana

Input: a board name (`drd`, `str`, `tel`, `mdi`, `hvc`, `mst`, `dist`, ...). Repos are siblings under
the UBC_Solar workspace: `firmware_v4/`, `sunlink/`, `sunlite/`.

Helper: `scripts/dash_tool.py` in this skill's base directory (stdlib Python, run with `python3 -I`):

- `dbc-signals <dbc> --node <BOARD>`: messages and signals a node sends, with bit layout. Warns on duplicate IDs, overlapping bits and bits past the DLC (multiplex-aware).
- `list <dashboard.json> [--prefix <BOARD>]`: panels with id, type, gridPos and queried fields, plus the next free id.
- `check <dashboard.json>... --dbc <dbc>`: invalid JSON, duplicate ids, gridPos overlaps, and fields that are missing from the DBC or filtered under the wrong `_measurement`.

## How the data flows

The sunlink parser decodes frames with the DBC (`parser/data_classes/CAN_Msg.py`) and writes to
InfluxDB with **`_measurement` = the DBC sender node** (`BO_ ... <NODE>`), **`class` = the message name**, and
**`_field` = the signal name**. A new DBC signal becomes a queryable field without any parser change.
Grafana loads the dashboards from `sunlink/dashboards/` (file provisioning, rescanned every 10s,
`provisioning/dashboards/release_telemetry_dash.yaml`).

## 1. Firmware is the source of truth

In `firmware_v4/firmware/components/<board>/`:

- IDs and DLCs: `driver/can_driver.h` (`#define ..._ID / ..._SIZE`) and the `CAN_TxHeaderTypeDef ... _header` definitions in `driver/can_driver.c`.
- Payload packing: `grep -rn "CAN_comms_Add_Tx_message" app/`, then read each pack function. Follow bitfield unions (e.g. `flags.all_flags`) back to their struct in the `.h`: the first declared bitfield is bit 0 on GCC/ARM. Also follow enum values (e.g. `DriveStateStates`).
- Note the branch: run `git -C firmware_v4 branch --show-current` and `git -C firmware_v4 diff origin/main -- <files>`. If a field exists only on an unmerged branch, say so. The sunlink change should merge after the firmware change (the extra bit just reads 0 until then).

Build a table per message: byte/bit → width → meaning → scale/unit.

## 2. Diff against the DBC

Run `dash_tool.py dbc-signals sunlink/dbc/brightside.dbc --node <BOARD>` and compare it with the table:
missing signals, extra/stale signals, wrong start bit/length/scale/unit, wrong DLC or ID.
**Show the diff to the user and confirm before editing.**

DBC rules:
- Signal line format: ` SG_ <PascalCaseName> : <start>|<len>@1+ (<scale>,<offset>) [0|0] "<unit>" Vector__XXX`. Use `@1` (Intel) for little-endian firmware packing and `-` for signed values. Keep the lines within the `BO_` block in bit order.
- The sender node must be listed in `BU_:`. CAN IDs are decimal in the DBC. Extended IDs have bit 31 set (`id | 0x80000000`).
- Signal names become Influx field names. Renaming one breaks existing panels and history, so grep the dashboards first.
- If the message also goes over cellular, update `sunlite/dbc/` and `sunlite/tools/can_messages.yaml` too.
- Re-run `dbc-signals` and make sure it prints no warnings for the edited node.

## 3. Dashboards

- Board dashboard: `sunlink/dashboards/PROD/PROD_<BOARD>_Brightside.json`.
- Pit Crew: `sunlink/dashboards/PROD/PROD_Pit_Crew_Brightside.json`. The board's section is the panels whose titles start with `<BOARD>` (`list --prefix <BOARD>`). Most of them sit under the "EMD Diagnostics" row, and some are under "Motor Control Details", "Regen" and "Pack Vitals".
- `TEST_`/`LOG_` Pit Crew copies point at other buckets. Only edit them if the user asks.

Ask the user which new signals belong on which dashboard. Pit Crew should only get what is useful trackside.

Edit with a short Python script (json load → modify → dump), not by hand:

- **Clone an existing panel of the same type** from the same file. That keeps the datasource uid, `pluginVersion` and Flux shape: `filter _measurement == "<BOARD>"`, `filter _field == "<Signal>" or ...`, `aggregateWindow(every: 1ms, fn: last, createEmpty: false)`.
- Panel types: booleans/flags go in a `state-timeline` (0 = green, 1 = red when the flag means a fault) or a `stat` with a 0/1 value mapping. Enums go in a `stat` with value mappings that match the firmware enum exactly. Numbers go in a `timeseries` or `stat` with a unit.
- Display names: use `byRegexp` overrides like `^<Signal> .*`. Older panels match `byName` with the full series name (`Signal {car="Brightside", class="..."}`), which breaks if tags change.
- Set `id` to the next free id (from `list`) and keep `gridPos` on the 24-column grid. To insert a line, shift every top-level panel at or below that y by the new height, and insert the panel in the file next to its neighbours so file order matches visual order.
- Bump the top-level `version`. Never change `uid`.
- Keep the formatting: `json.dumps(d, indent=2, ensure_ascii=False)`, and keep or omit the trailing newline the same way the original file does. Check with `git diff --stat` that only the intended panels changed.

## 4. Validate

```bash
T=<skill dir>/scripts/dash_tool.py
python3 -I $T dbc-signals sunlink/dbc/brightside.dbc --node <BOARD>
python3 -I $T check sunlink/dashboards/PROD/PROD_<BOARD>_Brightside.json \
  sunlink/dashboards/PROD/PROD_Pit_Crew_Brightside.json --dbc sunlink/dbc/brightside.dbc
# real decode with sunlink's cantools (venv at sunlink/environment)
sunlink/environment/bin/python3 -c "import cantools; db=cantools.database.load_file('sunlink/dbc/brightside.dbc'); \
  print(db.get_message_by_frame_id(<ID>).decode(bytes([...])))"
```

`check` may report problems that already existed before your edit. Compare against `git stash` or `origin/main`, and only fix new ones unless the user asks. Optional end-to-end check: `docker compose up` in sunlink and confirm the new panels render.

## 5. Hand off

Branch off `origin/main` in sunlink (`<board>-dbc-sync` or `EMB-<ticket#>/<board>-dbc-sync`). Summarize the firmware-vs-DBC table and the panels added. Offer to commit and open a PR. Never push without asking.
