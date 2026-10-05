#!/usr/bin/env python3
"""Create a ticket on the EMB Projects Monday board and post its first update.

Stdlib only. Needs MONDAY_TOKEN in the environment (monday.com avatar > Developers > My access tokens).

    create_ticket.py --title "STR GPIO buttons via interrupts" --group STR --priority Medium \
        --owner "Tony Chen" --tag MVP \
        --description "STR currently polls ..." \
        --dod "Software written in interrupts.c ..." --dod "Merged into main" [--dry-run]

    create_ticket.py --schema     # print groups, statuses, priorities, tags in use

    create_ticket.py --edit 13203465510 [--title "..."] --description "..." --dod "..."
        # rewrite an existing ticket's first update (and optionally its title)
"""
import argparse
import html
import json
import os
import sys
import time
import urllib.error
import urllib.request

API = "https://api.monday.com/v2"
BOARD_ID = "9565346490"  # EMB Projects
COL_OWNERS = "person"
COL_STATUS = "status"
COL_PRIORITY = "color_mm5dvzsj"
COL_TAGS = "tag_mktke5zs"
COL_TIMELINE = "timerange_mktkxtmj"
COL_ITEM_ID = "pulse_id_mm6mjjky"


def gql(query, variables=None):
    token = os.environ.get("MONDAY_TOKEN")
    if not token:
        sys.exit("MONDAY_TOKEN is not set (monday.com avatar > Developers > My access tokens)")
    req = urllib.request.Request(
        API,
        data=json.dumps({"query": query, "variables": variables or {}}).encode(),
        headers={"Authorization": token, "Content-Type": "application/json", "API-Version": "2024-10"},
    )
    for attempt in range(5):
        try:
            with urllib.request.urlopen(req, timeout=60) as r:
                data = json.load(r)
            break
        except urllib.error.HTTPError as e:
            if e.code != 429 or attempt == 4:
                raise
            time.sleep(int(e.headers.get("Retry-After") or 20))  # rate limited
    if data.get("errors") or data.get("error_message"):
        sys.exit(f"Monday error: {json.dumps(data.get('errors') or data.get('error_message'))}")
    return data["data"]


def board():
    return gql(
        """query($b: [ID!]) { boards(ids: $b) { name groups { id title }
           columns(ids: ["%s", "%s"]) { id settings_str } } }""" % (COL_STATUS, COL_PRIORITY),
        {"b": [BOARD_ID]},
    )["boards"][0]


def labels(b, col_id):
    col = next(c for c in b["columns"] if c["id"] == col_id)
    return [v for v in json.loads(col["settings_str"]).get("labels", {}).values() if v]


def pick(value, options, what):
    """Case-insensitive match; also accepts a prefix (e.g. 'critical' -> 'Critical ⚠️')."""
    low = value.strip().lower()
    hits = [o for o in options if o.lower() == low] or [o for o in options if o.lower().startswith(low)]
    if len(hits) != 1:
        sys.exit(f"{what} {value!r} not found; options: {', '.join(options)}")
    return hits[0]


def find_user(name):
    """Full Monday name or email."""
    if "@" in name:
        users = gql("query($e: [String]) { users(emails: $e) { id name email } }", {"e": [name]})["users"]
    else:
        users = gql("query($n: String) { users(name: $n) { id name email } }", {"n": name})["users"]
        exact = [u for u in users if u["name"].lower() == name.lower()]
        users = exact or users
    if len(users) != 1:
        found = ", ".join(f"{u['name']} <{u['email']}>" for u in users) or "nobody"
        sys.exit(f"owner {name!r} matched {found}; use the full name or email")
    return users[0]


def edit(item_id, title, body):
    """Replace the item's first (oldest) update and optionally rename it."""
    it = gql("query($i: [ID!]) { items(ids: $i) { name board { id } updates(limit: 100) { id created_at } } }",
             {"i": [item_id]})["items"]
    if not it:
        sys.exit(f"item {item_id} not found")
    it = it[0]
    if it["board"]["id"] != BOARD_ID:
        sys.exit(f"item {item_id} is not on the EMB Projects board")
    if not it["updates"]:
        sys.exit("item has no updates; nothing to edit")
    first = min(it["updates"], key=lambda u: u["created_at"])["id"]
    gql("mutation($id: ID!, $b: String!) { edit_update(id: $id, body: $b) { id } }", {"id": first, "b": body})
    if title and title != it["name"]:
        gql('mutation($b: ID!, $i: ID!, $v: String) { change_simple_column_value(board_id: $b, item_id: $i, '
            'column_id: "name", value: $v) { id } }', {"b": BOARD_ID, "i": item_id, "v": title})
    print(json.dumps({"edited": True, "item_id": item_id, "update_id": first, "title": title or it["name"]},
                     indent=2, ensure_ascii=False))


def update_body(description, dod):
    paras = "".join(f"<p>{html.escape(p.strip())}</p>" for p in description.split("\n\n") if p.strip())
    items = "".join(f"<li>{html.escape(d.strip())}</li>" for d in dod)
    return f"<p>Description:</p>{paras}<p>Definition of Done:</p><ul>{items}</ul>"


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--schema", action="store_true", help="print groups/labels and exit")
    ap.add_argument("--edit", metavar="ITEM_ID", help="rewrite this item's first update (and --title) instead of creating")
    ap.add_argument("--title")
    ap.add_argument("--group", help="group title, e.g. STR, Telemetry, Misc Tasks")
    ap.add_argument("--status", default=None, help="default: Upcoming, or Needs Owner if no --owner")
    ap.add_argument("--priority", default="Medium")
    ap.add_argument("--owner", action="append", default=[], help="full Monday name or email; repeatable")
    ap.add_argument("--tag", action="append", default=[], help="e.g. MVP, MMR, backlog; repeatable")
    ap.add_argument("--start", help="timeline start YYYY-MM-DD")
    ap.add_argument("--end", help="timeline end YYYY-MM-DD")
    ap.add_argument("--description")
    ap.add_argument("--dod", action="append", default=[], help="one Definition of Done item; repeatable")
    ap.add_argument("--dry-run", action="store_true", help="resolve everything and print, but create nothing")
    a = ap.parse_args()

    b = board()
    groups = {g["title"]: g["id"] for g in b["groups"]}
    if a.schema:
        print(json.dumps({"board": b["name"], "groups": list(groups),
                          "status": labels(b, COL_STATUS), "priority": labels(b, COL_PRIORITY)}, indent=2, ensure_ascii=False))
        return

    if a.edit:
        if not a.description or not a.dod:
            ap.error("--edit needs --description and --dod")
        body = update_body(a.description, a.dod)
        if a.dry_run:
            print(json.dumps({"dry_run": True, "edit": a.edit, "title": a.title, "update_html": body},
                             indent=2, ensure_ascii=False))
        else:
            edit(a.edit, a.title, body)
        return

    missing = [f for f in ("title", "group", "description") if not getattr(a, f)]
    if missing or not a.dod:
        ap.error(f"missing: {', '.join(['--' + m for m in missing] + ([] if a.dod else ['--dod']))}")
    if bool(a.start) != bool(a.end):
        ap.error("--start and --end go together")

    group_title = pick(a.group, list(groups), "group")
    status = pick(a.status or ("Upcoming" if a.owner else "Needs Owner"), labels(b, COL_STATUS), "status")
    priority = pick(a.priority, labels(b, COL_PRIORITY), "priority")
    owners = [find_user(n) for n in a.owner]

    values = {
        COL_STATUS: {"label": status},
        COL_PRIORITY: {"label": priority},
    }
    if owners:
        values[COL_OWNERS] = {"personsAndTeams": [{"id": int(u["id"]), "kind": "person"} for u in owners]}
    if a.start:
        values[COL_TIMELINE] = {"from": a.start, "to": a.end}
    body = update_body(a.description, a.dod)

    summary = {"title": a.title, "group": group_title, "status": status, "priority": priority,
               "owners": [u["name"] for u in owners], "tags": a.tag,
               "timeline": f"{a.start} - {a.end}" if a.start else None}
    if a.dry_run:
        print(json.dumps({"dry_run": True, **summary, "update_html": body}, indent=2, ensure_ascii=False))
        return

    if a.tag:
        tag_ids = [int(gql("mutation($n: String, $b: ID) { create_or_get_tag(tag_name: $n, board_id: $b) { id } }",
                           {"n": t, "b": BOARD_ID})["create_or_get_tag"]["id"]) for t in a.tag]
        values[COL_TAGS] = {"tag_ids": tag_ids}

    item = gql(
        """mutation($b: ID!, $g: String, $n: String!, $v: JSON) {
             create_item(board_id: $b, group_id: $g, item_name: $n, column_values: $v, create_labels_if_missing: false) { id url } }""",
        {"b": BOARD_ID, "g": groups[group_title], "n": a.title, "v": json.dumps(values)},
    )["create_item"]
    gql("mutation($i: ID!, $body: String!) { create_update(item_id: $i, body: $body) { id } }",
        {"i": item["id"], "body": body})
    ticket = gql('query($i: [ID!]) { items(ids: $i) { column_values(ids: ["%s"]) { text } } }' % COL_ITEM_ID,
                 {"i": [item["id"]]})["items"][0]["column_values"][0]["text"]
    print(json.dumps({"created": True, "ticket": ticket, "url": item["url"], "item_id": item["id"], **summary},
                     indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
