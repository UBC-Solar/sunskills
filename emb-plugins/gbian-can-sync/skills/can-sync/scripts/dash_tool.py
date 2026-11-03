#!/usr/bin/env python3
"""Inspect and sanity-check sunlink's DBC and Grafana dashboard JSON (stdlib only).

  dash_tool.py dbc-signals <dbc> [--node DRD]          messages/signals sent by a node, plus layout warnings
  dash_tool.py list <dashboard.json> [--prefix DRD]    panels: id, type, title, gridPos, measurement/fields
  dash_tool.py check <dashboard.json>... [--dbc <dbc>] duplicate ids, gridPos overlaps, fields missing from the DBC

Exit code 1 if `check` or `dbc-signals` finds a problem.
"""
import argparse
import json
import re
import sys

BO_RE = re.compile(r"^BO_\s+(\d+)\s+(\w+)\s*:\s*(\d+)\s+(\w+)")
SG_RE = re.compile(
    r"^\s*SG_\s+(\w+)\s*(?:([Mm]\d*)\s*)?:\s*(\d+)\|(\d+)@([01])([+-])\s*"
    r"\(([^,]+),([^)]+)\)\s*\[([^|]*)\|([^\]]*)\]\s*\"([^\"]*)\""
)
FIELD_RE = re.compile(r'r\["_field"\]\s*==\s*"([^"]+)"')
MEAS_RE = re.compile(r'r\["_measurement"\]\s*==\s*"([^"]+)"')


def parse_dbc(path):
    """Return list of messages: {id, name, dlc, node, signals:[{name,start,len,le,signed,scale,offset,unit}]}."""
    msgs, cur = [], None
    with open(path, encoding="utf-8", errors="replace") as f:
        for line in f:
            m = BO_RE.match(line)
            if m:
                cur = {"id": int(m[1]), "name": m[2], "dlc": int(m[3]), "node": m[4], "signals": []}
                msgs.append(cur)
                continue
            m = SG_RE.match(line)
            if m and cur is not None:
                cur["signals"].append({
                    "name": m[1], "mux": m[2] or "", "start": int(m[3]), "len": int(m[4]),
                    "le": m[5] == "1", "signed": m[6] == "-", "scale": m[7], "offset": m[8], "unit": m[11],
                })
            elif not line.strip():
                cur = None
    return msgs


def dbc_warnings(msgs):
    warns, seen = [], {}
    for msg in msgs:
        if msg["id"] in seen:
            warns.append(f"duplicate CAN ID {msg['id']} (0x{msg['id']:X}): {seen[msg['id']]} and {msg['name']}")
        seen[msg["id"]] = msg["name"]
        used = {}
        for s in msg["signals"]:
            if not s["le"]:
                continue  # Motorola bit numbering; skip overlap math
            # Multiplexed signals (mN) only collide with the multiplexor and same-N signals.
            groups = [""] if s["mux"] in ("", "M") else ["", s["mux"]]
            for b in range(s["start"], s["start"] + s["len"]):
                if b >= msg["dlc"] * 8:
                    warns.append(f"{msg['name']}.{s['name']} bit {b} beyond DLC {msg['dlc']}")
                    break
                hit = next((used[(g, b)] for g in groups if (g, b) in used), None)
                if hit:
                    warns.append(f"{msg['name']}.{s['name']} overlaps {hit} at bit {b}")
                    break
                used[(groups[-1], b)] = s["name"]
    return warns


def walk(panels, parent=None):
    for p in panels:
        yield p, parent
        yield from walk(p.get("panels", []), p)


def panel_refs(p):
    meas, fields = set(), set()
    for t in p.get("targets", []):
        q = t.get("query") or ""
        meas.update(MEAS_RE.findall(q))
        fields.update(FIELD_RE.findall(q))
    return meas, fields


def load(path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def cmd_dbc_signals(a):
    msgs = parse_dbc(a.dbc)
    for msg in msgs:
        if a.node and msg["node"] != a.node:
            continue
        print(f"BO_ {msg['id']} (0x{msg['id']:X}) {msg['name']} DLC={msg['dlc']} sender={msg['node']}")
        for s in sorted(msg["signals"], key=lambda s: s["start"]):
            sign = "-" if s["signed"] else "+"
            unit = f' "{s["unit"]}"' if s["unit"] else ""
            mux = f" [{s['mux']}]" if s["mux"] else ""
            print(f"   {s['start']:>3}|{s['len']:<2} {sign} ({s['scale']},{s['offset']}){unit}  {s['name']}{mux}")
    warns = dbc_warnings(msgs)
    for w in warns:
        print("WARN:", w, file=sys.stderr)
    return 1 if warns else 0


def cmd_list(a):
    d = load(a.dashboard)
    print(f"{d.get('title')}  uid={d.get('uid')}  version={d.get('version')}")
    ids = []
    for p, parent in walk(d.get("panels", [])):
        ids.append(p.get("id", 0))
        title = p.get("title", "")
        if a.prefix and p.get("type") != "row" and not title.upper().startswith(a.prefix.upper()):
            continue
        g = p.get("gridPos", {})
        meas, fields = panel_refs(p)
        indent = "    " if parent else ""
        where = f"x={g.get('x')} y={g.get('y')} w={g.get('w')} h={g.get('h')}"
        refs = f"  [{','.join(sorted(meas)) or '*'}] {', '.join(sorted(fields))}" if fields else ""
        print(f"{indent}{p.get('id'):>4} {p.get('type', ''):<15} {where:<24} {title!r}{refs}")
    print(f"next free id: {max(ids, default=0) + 1}")
    return 0


def overlaps(a, b):
    return (a["x"] < b["x"] + b["w"] and b["x"] < a["x"] + a["w"]
            and a["y"] < b["y"] + b["h"] and b["y"] < a["y"] + a["h"])


def cmd_check(a):
    signals = None
    if a.dbc:
        signals = {}
        for msg in parse_dbc(a.dbc):
            for s in msg["signals"]:
                signals.setdefault(s["name"], set()).add(msg["node"])
    bad = 0
    for path in a.dashboards:
        try:
            d = load(path)
        except (OSError, json.JSONDecodeError) as e:
            print(f"{path}: invalid JSON: {e}")
            bad += 1
            continue
        problems = []
        ids = {}
        for p, _ in walk(d.get("panels", [])):
            pid = p.get("id")
            if pid in ids:
                problems.append(f"duplicate panel id {pid}: {ids[pid]!r} and {p.get('title')!r}")
            ids[pid] = p.get("title")
        # Overlaps among top-level panels (collapsed rows keep their children in their own space).
        top = [p for p in d.get("panels", []) if "gridPos" in p]
        for i, p in enumerate(top):
            for q in top[i + 1:]:
                if overlaps(p["gridPos"], q["gridPos"]):
                    problems.append(f"gridPos overlap: {p.get('id')} {p.get('title')!r} / {q.get('id')} {q.get('title')!r}")
            if p["gridPos"].get("x", 0) + p["gridPos"].get("w", 0) > 24:
                problems.append(f"panel {p.get('id')} {p.get('title')!r} wider than 24 columns")
        if signals is not None:
            for p, _ in walk(d.get("panels", [])):
                meas, fields = panel_refs(p)
                for fld in sorted(fields):
                    nodes = signals.get(fld)
                    if not nodes:
                        problems.append(f"panel {p.get('id')} {p.get('title')!r}: field {fld!r} not in DBC")
                    elif meas and not (meas & nodes):
                        problems.append(f"panel {p.get('id')} {p.get('title')!r}: field {fld!r} sent by "
                                        f"{sorted(nodes)}, query filters measurement {sorted(meas)}")
        print(f"{path}: {'OK' if not problems else f'{len(problems)} problem(s)'}")
        for pr in problems:
            print("   ", pr)
        bad += bool(problems)
    return 1 if bad else 0


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("dbc-signals")
    s.add_argument("dbc")
    s.add_argument("--node")
    s.set_defaults(fn=cmd_dbc_signals)
    s = sub.add_parser("list")
    s.add_argument("dashboard")
    s.add_argument("--prefix", help="only panels whose title starts with this (e.g. DRD)")
    s.set_defaults(fn=cmd_list)
    s = sub.add_parser("check")
    s.add_argument("dashboards", nargs="+")
    s.add_argument("--dbc", help="also check every queried _field exists in this DBC")
    s.set_defaults(fn=cmd_check)
    a = ap.parse_args()
    sys.exit(a.fn(a))


if __name__ == "__main__":
    main()
