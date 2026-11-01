#!/usr/bin/env python3
"""
check_panels_live.py: run every panel query of one or more dashboards through a Grafana
instance and report panels that return no rows ("No data").

Usage:
  GRAFANA_URL=http://localhost:3000 GRAFANA_AUTH=admin:password \
    python check_panels_live.py --from now-5m dashboard.json [...]

GRAFANA_AUTH is "user:password" (basic auth) or a service-account token ("glsa_...").
Exit code 1 if any panel is empty. Stdlib only.
"""
import argparse
import base64
import json
import os
import sys
import urllib.request
from pathlib import Path


def iter_panels(panels):
    for p in panels:
        if p.get("type") == "row":
            yield from iter_panels(p.get("panels", []))
        else:
            yield p


def ds_query(url, auth, target, t_from, t_to):
    body = {"queries": [{"refId": target.get("refId", "A"), "datasource": target["datasource"],
                         "query": target["query"], "intervalMs": 1000, "maxDataPoints": 500}],
            "from": t_from, "to": t_to}
    req = urllib.request.Request(f"{url}/api/ds/query", data=json.dumps(body).encode(),
                                 headers={"Content-Type": "application/json"})
    if auth.startswith("glsa_"):
        req.add_header("Authorization", f"Bearer {auth}")
    else:
        req.add_header("Authorization", "Basic " + base64.b64encode(auth.encode()).decode())
    with urllib.request.urlopen(req, timeout=30) as r:
        res = json.load(r)["results"]
    out = next(iter(res.values()))
    if out.get("error"):
        return -1, out["error"]
    rows = 0
    series = 0
    for fr in out.get("frames", []):
        vals = fr.get("data", {}).get("values", [])
        if vals and vals[0]:
            rows += len(vals[0])
            series += 1
    return rows, f"{series} series"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--from", dest="t_from", default="now-5m")
    ap.add_argument("--to", dest="t_to", default="now")
    ap.add_argument("dashboards", nargs="+")
    a = ap.parse_args()
    url = os.environ.get("GRAFANA_URL", "http://localhost:3000").rstrip("/")
    auth = os.environ.get("GRAFANA_AUTH", "admin:admin")
    empty = 0
    for path in a.dashboards:
        d = json.loads(Path(path).read_text())
        print(f"== {d['title']}")
        for p in iter_panels(d["panels"]):
            for t in p.get("targets", []):
                try:
                    rows, info = ds_query(url, auth, t, a.t_from, a.t_to)
                except Exception as e:  # noqa: BLE001
                    rows, info = -1, str(e)
                ok = rows > 0
                empty += not ok
                print(f"  {'OK   ' if ok else 'EMPTY'} {p['title']} [{t.get('refId')}]: "
                      f"{rows if rows >= 0 else 'error'} rows, {info}")
    print(f"{empty} empty panel queries")
    sys.exit(1 if empty else 0)


if __name__ == "__main__":
    main()
