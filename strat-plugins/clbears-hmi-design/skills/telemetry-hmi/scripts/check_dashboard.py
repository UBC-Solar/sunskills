#!/usr/bin/env python3
"""
check_dashboard.py: lint Grafana dashboard JSON against a DBC and the telemetry-hmi rules.

Usage:
  python check_dashboard.py --dbc path/to/car.dbc dashboard.json [more.json ...]

Checks (ERROR fails the run, WARN is advisory):
  ERROR  a query filters a _field that the DBC doesn't define for that _measurement (DBC sender)
  ERROR  a query filters a class (message name) that isn't in the DBC, or isn't sent by that board
  ERROR  a numeric panel (stat/timeseries/gauge/bargauge) has no unit
  ERROR  dashboard uid missing, or title not '<BUCKETS>: <TITLE> - <CAR>' (sunlink docs/GRAFANA.md)
  WARN   panel title not '<BOARD>: <Signal>'
  WARN   a time series has more than 4 traces (glanceability)
  WARN   a state timeline / stat on an enum has no value mappings (colour or number as the only cue)
  WARN   red/orange used in a threshold base step (alarm colours reserved for abnormal states)

Needs cantools (pip install cantools).
"""
import argparse
import json
import re
import sys
from collections import defaultdict
from pathlib import Path

try:
    import cantools
except ImportError:  # pragma: no cover
    sys.exit("check_dashboard.py needs cantools: pip install cantools")

NUMERIC = {"stat", "timeseries", "gauge", "bargauge"}
ALARM_COLORS = {"red", "orange", "#f2495c", "#ff9830", "dark-red", "semi-dark-red"}
TITLE_RE = re.compile(r"^[A-Z_, ]+: .+ - [A-Za-z]+$")
PANEL_RE = re.compile(r"^[A-Za-z0-9_ ]+: .+")


def dbc_index(path):
    db = cantools.database.load_file(str(path), strict=False)
    by_sender = defaultdict(set)          # sender -> {signal}
    msg_sender = {}                       # message -> {senders}
    msg_signals = {}
    for m in db.messages:
        senders = set(m.senders or ["Vector__XXX"])
        msg_sender[m.name] = senders
        msg_signals[m.name] = {s.name for s in m.signals}
        for s in senders:
            by_sender[s].update(msg_signals[m.name])
    return by_sender, msg_sender, msg_signals


def iter_panels(panels):
    for p in panels:
        if p.get("type") == "row":
            yield from iter_panels(p.get("panels", []))
        else:
            yield p


def eq_values(query, key):
    return re.findall(r'r\["%s"\]\s*==\s*"([^"]+)"|r\.%s\s*==\s*"([^"]+)"' % (key, key), query)


def flat(matches):
    return [a or b for a, b in matches]


def check(path, by_sender, msg_sender, msg_signals):
    errs, warns = [], []
    d = json.loads(Path(path).read_text())
    name = Path(path).name
    if not d.get("uid"):
        errs.append("dashboard has no fixed uid")
    if not TITLE_RE.match(d.get("title", "")):
        errs.append(f"dashboard title '{d.get('title')}' is not '<BUCKETS>: <TITLE> - <CAR>'")

    n = 0
    for p in iter_panels(d.get("panels", [])):
        n += 1
        title = p.get("title", "")
        ptype = p.get("type")
        where = f"[{ptype}] '{title}'"
        if ptype == "text":
            continue
        if not PANEL_RE.match(title):
            warns.append(f"{where}: title not '<BOARD>: <Signal>'")
        defaults = p.get("fieldConfig", {}).get("defaults", {})
        mappings = defaults.get("mappings") or []
        if ptype in NUMERIC and not defaults.get("unit") and not mappings:
            errs.append(f"{where}: numeric panel without a unit")
        steps = defaults.get("thresholds", {}).get("steps", [])
        if steps and steps[0].get("value") is None and str(steps[0].get("color", "")).lower() in ALARM_COLORS \
                and len(steps) == 1:
            warns.append(f"{where}: alarm colour used as the only/normal colour")
        if ptype == "state-timeline" and not mappings:
            warns.append(f"{where}: state timeline without value mappings (no words for states)")

        traces = 0
        for t in p.get("targets", []):
            q = t.get("query", "")
            meas = flat(eq_values(q, "_measurement"))
            classes = flat(eq_values(q, "class"))
            fields = flat(eq_values(q, "_field"))
            traces += max(1, len(fields)) if "pivot(" not in q else 1
            for c in classes:
                if c not in msg_signals:
                    errs.append(f"{where}: class '{c}' is not a message in the DBC")
                elif meas and not (set(meas) & msg_sender[c]):
                    errs.append(f"{where}: message '{c}' is not sent by {meas} (DBC senders {sorted(msg_sender[c])})")
            for f in fields:
                if classes:
                    if not any(f in msg_signals.get(c, set()) for c in classes):
                        errs.append(f"{where}: field '{f}' is not a signal of {classes}")
                elif meas:
                    if not any(f in by_sender.get(m, set()) for m in meas):
                        errs.append(f"{where}: field '{f}' is not sent by {meas} in the DBC")
                else:
                    warns.append(f"{where}: query has no _measurement/class filter for field '{f}'")
        if ptype == "timeseries" and traces > 4:
            warns.append(f"{where}: {traces} traces (keep <= 4 per trend)")
    return name, n, errs, warns


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--dbc", required=True)
    ap.add_argument("dashboards", nargs="+")
    a = ap.parse_args()
    idx = dbc_index(a.dbc)
    failed = False
    for path in a.dashboards:
        name, n, errs, warns = check(path, *idx)
        status = "FAIL" if errs else "OK"
        print(f"{status}: {name} ({n} panels, {len(errs)} errors, {len(warns)} warnings)")
        for e in errs:
            print(f"  ERROR {e}")
        for w in warns:
            print(f"  WARN  {w}")
        failed |= bool(errs)
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
