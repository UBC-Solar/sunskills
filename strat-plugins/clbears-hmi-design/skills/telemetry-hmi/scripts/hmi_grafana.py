"""
hmi_grafana.py: build Grafana 9.5 dashboards that follow the telemetry-hmi method.

Every board dashboard gets the same skeleton:
  Row 1  "Health & faults"  link freshness, uptime, MCU health, one fault strip
  Row 2+ grouped data       trends with units and alarm bands, state timelines
  Last   "Raw / diagnostic" collapsed, for detail you only need when diagnosing

Colour discipline (see references/pas-high-performance-hmi.md and faa-hf-std-001b.md):
  normal/OK/off = neutral grey, active/advisory = blue, caution = orange, fault = red.
  Red and orange are never used for anything but abnormal states. Every colour is
  paired with text (OK/FAULT, ON/OFF, mapped enum names) so colour is never the only cue.

Stdlib only. Typical use (see examples/sunlink_cascadia.py):

    from hmi_grafana import Board, Dash
    b = Board("TEL")
    d = Dash("PROD: TEL - Cascadia", uid="cascadia-prod-tel", tags=["cascadia"])
    d.row("Health & faults")
    d.add(b.freshness("TELTimeSinceBootup"), w=4)
    ...
    d.write("PROD_TEL_Cascadia.json")
"""
from __future__ import annotations

import json
from pathlib import Path

DATASOURCE = {"type": "influxdb", "uid": "P951FEA4DE68E13C5"}
BUCKET = "CAN_prod"

# Palette: one meaning per colour, at most 4 per screen in normal operation.
GREY = "#8e8e8e"       # normal / OK / off / no information
DARK = "#464c54"       # inactive fill in timelines
BLUE = "#5794f2"       # active / advisory (an input is on, a mode is engaged)
ORANGE = "#ff9830"     # caution / marginal
YELLOW = "#f2cc0c"     # a fault happened in the window shown but is not active now
RED = "#ff1a1a"        # fault / failure / out of limits (saturated: it must look angry)
TRANSPARENT = "transparent"

GRID_W = 24


# ----------------------------------------------------------------------------- queries
def flux(measurement: str, cls: str, fields: list[str], agg: str = "mean",
         bucket: str = BUCKET, window: str = "v.windowPeriod", tail: str = "") -> str:
    """Flux query filtered by board (measurement), message (class tag) and signal(s).

    agg: "mean" for analog values, "last" for enums/counters, "max" for fault bits
    (so a one-sample fault is never averaged away inside a window).
    The result keeps only _time/_value/_field so series are named by signal.
    """
    field_expr = " or ".join(f'r["_field"] == "{f}"' for f in fields)
    return (
        f'from(bucket: "{bucket}")\n'
        f'  |> range(start: v.timeRangeStart, stop: v.timeRangeStop)\n'
        f'  |> filter(fn: (r) => r["_measurement"] == "{measurement}")\n'
        f'  |> filter(fn: (r) => r["class"] == "{cls}")\n'
        f'  |> filter(fn: (r) => {field_expr})\n'
        f'  |> aggregateWindow(every: {window}, fn: {agg}, createEmpty: false)\n'
        f'  |> keep(columns: ["_time", "_value", "_field"])\n'
        f'{tail}'
        f'  |> yield(name: "{agg}")'
    )


def target(query: str, ref: str = "A") -> dict:
    return {"datasource": DATASOURCE, "query": query, "refId": ref}


# ----------------------------------------------------------------------------- field config helpers
def steps(*pairs) -> dict:
    """steps((None, GREY), (2000, RED)) -> absolute thresholds."""
    return {"mode": "absolute", "steps": [{"color": c, "value": v} for v, c in pairs]}


def value_map(mapping: dict, unknown: bool = True) -> list:
    """{0: ("OK", GREY), 1: ("FAULT", RED)} -> Grafana value mappings.

    unknown=True adds a catch-all so a value outside the table reads "UNKNOWN <n>" in orange
    instead of a bare number (an undefined state is itself abnormal and must say so).
    """
    opts = {str(k): {"text": t, "color": c, "index": i} for i, (k, (t, c)) in enumerate(mapping.items())}
    maps = [{"type": "value", "options": opts}]
    if unknown:
        maps.append({"type": "range", "options": {"from": -1e12, "to": 1e12,
                                                  "result": {"text": "UNKNOWN", "color": ORANGE,
                                                             "index": len(opts)}}})
    return maps


OK_FAULT = {0: ("OK", GREY), 1: ("FAULT", RED)}
FAULT_STATES = {0: ("OK", GREY), 1: ("CLEARED", YELLOW), 2: ("FAULT", RED)}
OFF_ON = {0: ("OFF", DARK), 1: ("ON", BLUE)}
NO_YES = {0: ("NO", DARK), 1: ("YES", BLUE)}


def _defaults(unit: str, thresholds: dict | None = None, mappings: list | None = None,
              decimals: int | None = None, vmin=None, vmax=None, color_mode: str = "thresholds",
              custom: dict | None = None) -> dict:
    d = {
        "unit": unit,
        "color": {"mode": color_mode, **({"fixedColor": GREY} if color_mode == "fixed" else {})},
        "thresholds": thresholds or steps((None, GREY)),
        "mappings": mappings or [],
    }
    if decimals is not None:
        d["decimals"] = decimals
    if vmin is not None:
        d["min"] = vmin
    if vmax is not None:
        d["max"] = vmax
    if custom:
        d["custom"] = custom
    return d


def _panel(ptype: str, title: str, targets: list, defaults: dict, options: dict,
           description: str = "", overrides: list | None = None) -> dict:
    return {
        "type": ptype,
        "title": title,
        "description": description,
        "datasource": DATASOURCE,
        "targets": targets,
        "fieldConfig": {"defaults": defaults, "overrides": overrides or []},
        "options": options,
        "pluginVersion": "9.5.2",
    }


# ----------------------------------------------------------------------------- panel builders
def stat(title: str, query: str, unit: str, thresholds=None, mappings=None, decimals=None,
         description: str = "", sparkline: bool = True, vmin=None, vmax=None) -> dict:
    """Single value. Use for current state at a glance; prefer trend() when the history matters."""
    # Tiles fill with colour only when abnormal: normal grey becomes transparent, so a red
    # or orange tile is the only filled thing on the row.
    thresholds = thresholds or steps((None, GREY))
    for st in thresholds["steps"]:
        if st["color"] == GREY:
            st["color"] = TRANSPARENT
    for m in mappings or []:
        for r in ([m["options"]["result"]] if m["type"] == "range" else m["options"].values()):
            if r.get("color") in (GREY, DARK, BLUE):
                r["color"] = TRANSPARENT
    return _panel(
        "stat", title, [target(query)],
        _defaults(unit, thresholds, mappings, decimals, vmin, vmax),
        {
            "reduceOptions": {"calcs": ["lastNotNull"], "fields": "", "values": False},
            "colorMode": "background", "graphMode": "area" if sparkline else "none",
            "justifyMode": "auto", "orientation": "auto", "textMode": "auto",
        },
        description,
    )


def trend(title: str, queries: list[str] | str, unit: str, *, limits: dict | None = None,
          vmin=None, vmax=None, decimals=None, description: str = "", stack: bool = False) -> dict:
    """Time series with the alarm band drawn in (dashed line + light area beyond the limit).

    limits: {"low": 2000, "high": 125, "caution_high": 95} -> red below low / above high,
            orange above caution_high. Normal range stays uncoloured.
    Keep to <= 4 traces per panel (Wickens/PAS: more traces stop being readable at a glance).
    """
    if isinstance(queries, str):
        queries = [queries]
    pairs = [(None, TRANSPARENT)]
    if limits:
        if "low" in limits:
            pairs = [(None, RED), (limits["low"], TRANSPARENT)]
        if "caution_high" in limits:
            pairs.append((limits["caution_high"], ORANGE))
        if "high" in limits:
            pairs.append((limits["high"], RED))
    custom = {
        "drawStyle": "line", "lineWidth": 2, "fillOpacity": 0, "showPoints": "never",
        "spanNulls": True, "axisPlacement": "auto", "axisLabel": "",
        "thresholdsStyle": {"mode": "dashed+area" if limits else "off"},
        "stacking": {"mode": "normal" if stack else "none", "group": "A"},
        "lineInterpolation": "linear", "gradientMode": "none", "barAlignment": 0,
        "scaleDistribution": {"type": "linear"}, "hideFrom": {"legend": False, "tooltip": False, "viz": False},
    }
    return _panel(
        "timeseries", title, [target(q, chr(65 + i)) for i, q in enumerate(queries)],
        _defaults(unit, steps(*pairs), None, decimals, vmin, vmax, color_mode="palette-classic", custom=custom),
        {"legend": {"displayMode": "list", "placement": "bottom", "showLegend": True,
                    "calcs": ["lastNotNull"]},
         "tooltip": {"mode": "multi", "sort": "none"}},
        description,
    )


def timeline(title: str, query, mapping: dict | None = None, description: str = "") -> dict:
    """State timeline for bits and enums; every state gets a word, not just a colour.

    Either one query + one mapping ({raw: (text, colour)}), or a list of (query, mapping)
    groups when signals in the same panel need different words (e.g. enum + flags).
    """
    groups = query if isinstance(query, list) else [(query, mapping)]
    targets, overrides = [], []
    for i, (q, m) in enumerate(groups):
        ref = chr(65 + i)
        targets.append(target(q, ref))
        if i:
            overrides.append({"matcher": {"id": "byFrameRefID", "options": ref},
                              "properties": [{"id": "mappings", "value": value_map(m)}]})
    return _panel(
        "state-timeline", title, targets,
        # colour mode must be "fixed": with "thresholds", Grafana 9.5 merges states by threshold
        # range ("-inf+") and ignores the value mappings.
        _defaults("none", steps((None, GREY)), value_map(groups[0][1]), color_mode="fixed",
                  custom={"fillOpacity": 80, "lineWidth": 0, "hideFrom": {"legend": False, "tooltip": False, "viz": False}}),
        {"showValue": "auto", "mergeValues": True, "alignValue": "left", "rowHeight": 0.85,
         "legend": {"displayMode": "list", "placement": "bottom", "showLegend": False},
         "tooltip": {"mode": "single", "sort": "none"}},
        description, overrides,
    )


def geomap(title: str, measurement: str, cls: str, lat: str, lon: str, description: str = "") -> dict:
    """Track of GPS fixes. Lat/lon are pivoted into one frame for the coords layer."""
    q = (
        f'from(bucket: "{BUCKET}")\n'
        f'  |> range(start: v.timeRangeStart, stop: v.timeRangeStop)\n'
        f'  |> filter(fn: (r) => r["_measurement"] == "{measurement}")\n'
        f'  |> filter(fn: (r) => r["class"] == "{cls}")\n'
        f'  |> filter(fn: (r) => r["_field"] == "{lat}" or r["_field"] == "{lon}")\n'
        f'  |> aggregateWindow(every: v.windowPeriod, fn: last, createEmpty: false)\n'
        f'  |> pivot(rowKey: ["_time"], columnKey: ["_field"], valueColumn: "_value")\n'
        f'  |> keep(columns: ["_time", "{lat}", "{lon}"])\n'
        f'  |> yield(name: "track")'
    )
    p = _panel(
        "geomap", title, [target(q)],
        {"unit": "degree", "color": {"mode": "fixed", "fixedColor": BLUE}, "thresholds": steps((None, BLUE)),
         "mappings": [], "custom": {"hideFrom": {"legend": False, "tooltip": False, "viz": False}}},
        {
            "view": {"id": "fit", "lat": 0, "lon": 0, "zoom": 15, "allLayers": True, "lastOnly": False},
            "controls": {"showZoom": True, "mouseWheelZoom": False, "showAttribution": True},
            # OpenStreetMap tiles: the default CARTO basemap needs an API key offline/on the pit laptop
            "basemap": {"type": "xyz", "name": "OpenStreetMap",
                        "config": {"url": "https://tile.openstreetmap.org/{z}/{x}/{y}.png",
                                   "attribution": "OpenStreetMap contributors"}},
            "layers": [{
                "type": "route", "name": "Track", "tooltip": True,
                "location": {"mode": "coords", "latitude": lat, "longitude": lon},
                "config": {"style": {"color": {"fixed": BLUE}, "size": {"fixed": 3}, "opacity": 0.9}},
            }, {
                "type": "markers", "name": "Now", "tooltip": True,
                "location": {"mode": "coords", "latitude": lat, "longitude": lon},
                "filterData": {"id": "byRefId", "options": "A"},
                "config": {"showLegend": False, "style": {"color": {"fixed": BLUE}, "size": {"fixed": 6},
                                                          "symbol": {"fixed": "img/icons/marker/circle.svg", "mode": "fixed"}}},
            }],
            "tooltip": {"mode": "details"},
        },
        description,
    )
    return p


def text(title: str, markdown: str) -> dict:
    return {"type": "text", "title": title, "options": {"mode": "markdown", "content": markdown}}


# ----------------------------------------------------------------------------- board helper
class Board:
    """Shortcuts for one CAN node (InfluxDB measurement = DBC sender)."""

    def __init__(self, name: str):
        self.name = name

    def q(self, cls: str, fields, agg: str = "mean", **kw) -> str:
        return flux(self.name, cls, [fields] if isinstance(fields, str) else list(fields), agg, **kw)

    def q_multi(self, pairs: list[tuple[str, str]], agg: str = "mean") -> str:
        """One query over signals from different messages: [(class, field), ...]."""
        cond = " or ".join(f'(r["class"] == "{c}" and r["_field"] == "{f}")' for c, f in pairs)
        return (
            f'from(bucket: "{BUCKET}")\n'
            f'  |> range(start: v.timeRangeStart, stop: v.timeRangeStop)\n'
            f'  |> filter(fn: (r) => r["_measurement"] == "{self.name}")\n'
            f'  |> filter(fn: (r) => {cond})\n'
            f'  |> aggregateWindow(every: v.windowPeriod, fn: {agg}, createEmpty: false)\n'
            f'  |> keep(columns: ["_time", "_value", "_field"])\n'
            f'  |> yield(name: "{agg}")'
        )

    def t(self, signal: str, unit_label: str = "") -> str:
        """Panel title per docs/GRAFANA.md: '<BOARD>: <Signal> (<unit>)'."""
        return f"{self.name}: {signal}" + (f" ({unit_label})" if unit_label else "")

    def freshness(self, heartbeat_cls: str, stale_s: float = 3.0) -> dict:
        """Seconds since this board's last heartbeat frame. Red once the link is stale."""
        q = (
            f'from(bucket: "{BUCKET}")\n'
            f'  |> range(start: -1h)\n'
            f'  |> filter(fn: (r) => r["_measurement"] == "{self.name}")\n'
            f'  |> filter(fn: (r) => r["class"] == "{heartbeat_cls}")\n'
            f'  |> last()\n'
            f'  |> map(fn: (r) => ({{_time: r._time, _field: "Last frame",'
            f' _value: float(v: uint(v: now()) - uint(v: r._time)) / 1000000000.0}}))\n'
            f'  |> yield(name: "age")'
        )
        return stat(self.t("Link", "s since last frame"), q, "s", steps((None, GREY), (stale_s, RED)),
                    decimals=1, sparkline=False,
                    description=f"Time since the last {heartbeat_cls} frame reached InfluxDB (looks back 1 h). "
                                f"Red after {stale_s:g} s: the board, CAN or the radio link is down.")

    def uptime(self, cls: str, field: str) -> dict:
        return stat(self.t("Uptime", "s"), self.q(cls, field, "last"), "s", decimals=0,
                    description=f"{field}: seconds since boot. A drop to ~0 means the board reset.")

    def faults(self, cls: str, fields: list[str], title: str = "Faults", description: str = "") -> dict:
        """Fault strip. Each row: OK (grey) until the signal faults, FAULT (red) while it is set,
        then CLEARED (yellow) for the rest of the time range shown, so a past fault stays visible
        without a separate status tile."""
        field_expr = " or ".join(f'r["_field"] == "{f}"' for f in fields)
        q = (
            f'from(bucket: "{BUCKET}")\n'
            f'  |> range(start: v.timeRangeStart, stop: v.timeRangeStop)\n'
            f'  |> filter(fn: (r) => r["_measurement"] == "{self.name}")\n'
            f'  |> filter(fn: (r) => r["class"] == "{cls}")\n'
            f'  |> filter(fn: (r) => {field_expr})\n'
            f'  |> aggregateWindow(every: v.windowPeriod, fn: max, createEmpty: false)\n'
            f'  |> keep(columns: ["_time", "_value", "_field"])\n'
            f'  |> toInt()\n'
            f'  |> duplicate(column: "_value", as: "now")\n'
            f'  |> cumulativeSum(columns: ["_value"])\n'
            f'  |> map(fn: (r) => ({{_time: r._time, _field: r._field,'
            f' _value: if r.now > 0 then 2 else if r._value > 0 then 1 else 0}}))\n'
            f'  |> yield(name: "fault_state")'
        )
        return timeline(self.t(title), q, FAULT_STATES,
                        (description + " " if description else "") +
                        "Per row: OK, FAULT (red) while set, CLEARED (yellow) once it has faulted in the "
                        "time range shown. Zoom the time range past an old fault to clear the yellow.")

    def fault_block(self, d: "Dash", cls: str, fields: list[str], w: int = 24, h: int = 6, description: str = ""):
        d.add(self.faults(cls, fields, description=description), w=w, h=h)


# ----------------------------------------------------------------------------- dashboard layout
class Dash:
    """Flow layout: panels are placed left to right, wrapping at 24 columns; row() starts a band."""

    def __init__(self, title: str, uid: str, tags: list[str] | None = None, description: str = "",
                 refresh: str = "1s", time_from: str = "now-5m"):
        self.d = {
            "title": title, "uid": uid, "tags": tags or [], "description": description,
            "editable": True, "graphTooltip": 1, "fiscalYearStartMonth": 0, "liveNow": False,
            "refresh": refresh, "schemaVersion": 38, "version": 1, "style": "dark",
            "time": {"from": time_from, "to": "now"}, "timepicker": {}, "timezone": "",
            "templating": {"list": []}, "annotations": {"list": []},
            "links": [{"title": "Cascadia boards", "type": "dashboards", "tags": tags or [],
                       "asDropdown": False, "includeVars": False, "keepTime": True, "icon": "external link",
                       "targetBlank": False}],
            "panels": [],
        }
        self.x = self.y = 0
        self.row_h = 0
        self.next_id = 1
        self._open_row = None

    def _place(self, panel: dict, w: int, h: int):
        if self.x + w > GRID_W:
            self.x, self.y = 0, self.y + self.row_h
            self.row_h = 0
        panel["gridPos"] = {"x": self.x, "y": self.y, "w": w, "h": h}
        panel["id"] = self.next_id
        self.next_id += 1
        self.x += w
        self.row_h = max(self.row_h, h)

    def row(self, title: str, collapsed: bool = False):
        self.newline()
        r = {"type": "row", "title": title, "collapsed": collapsed, "panels": [],
             "gridPos": {"x": 0, "y": self.y, "w": 24, "h": 1}, "id": self.next_id}
        self.next_id += 1
        self.d["panels"].append(r)
        self._open_row = r if collapsed else None
        self.y += 1

    def newline(self):
        if self.x:
            self.x, self.y = 0, self.y + self.row_h
            self.row_h = 0

    def add(self, panel: dict, w: int = 8, h: int = 7, below: bool = False):
        """below=True stacks the panel under the previous one in the same column."""
        prev = (self._open_row["panels"] if self._open_row else self.d["panels"])[-1] if below else None
        if prev and "gridPos" in prev:
            g = prev["gridPos"]
            panel["gridPos"] = {"x": g["x"], "y": g["y"] + g["h"], "w": w, "h": h}
            panel["id"] = self.next_id
            self.next_id += 1
            self.row_h = max(self.row_h, g["y"] + g["h"] + h - self.y)
        else:
            self._place(panel, w, h)
        (self._open_row["panels"] if self._open_row else self.d["panels"]).append(panel)
        return panel

    def json(self) -> dict:
        return self.d

    def write(self, path: str | Path):
        Path(path).write_text(json.dumps(self.d, indent=2) + "\n")
