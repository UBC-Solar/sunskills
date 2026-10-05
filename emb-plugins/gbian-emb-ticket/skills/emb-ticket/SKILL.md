---
name: emb-ticket
description: Create an embedded (EMB) ticket on the UBC Solar "EMB Projects" Monday board from a short description or a design review (DR0) - picks the group, status, priority, owner and tags, and posts the first update in the team's Description / Definition of Done format. Use when the user asks to make, file, open, add or edit an EMB/embedded/firmware ticket, task or item on Monday, or to turn a DR0 into tickets.
---

# EMB Monday ticket

Turns a short description or a DR0 into a ticket on **EMB Projects** (board `9565346490`) via
`scripts/create_ticket.py` in this skill's base directory (stdlib Python, no installs).

## Preflight

- `MONDAY_TOKEN` must be set (monday.com avatar → **Developers** → **My access tokens**). If it is
  missing, ask the user to `export MONDAY_TOKEN=...`; never print or echo the token.
- Run `python3 <skill dir>/scripts/create_ticket.py --schema` to get the live groups, statuses
  and priorities. Use those exact values; the board can change.

## 1. Ask for the two inputs

Before drafting, make sure you have both of these. Ask in one message for whichever is
missing (use AskUserQuestion if available):

1. **Owner**: who the ticket is assigned to (full Monday name or email), or "unassigned".
2. **Short description**: what's wrong or missing, and the proposed fix. A pasted DR0 also
   counts; for a DR0, also make sure you know which board this ticket is for.

Don't ask about anything else up front. Infer every other field below from these two and
show it in the draft, where the user can correct it.

## 2. Draft the ticket

| Field | How to choose |
|---|---|
| **Title** | Short and imperative, starting with the board/area: `STR: handle buttons with GPIO interrupts` |
| **Group** | The ECU/area it touches: `STR`, `MDI`, `Driver Dashboard` (DRD), `Telemetry` (TEL), `Sunlink`, `New Sensors`, `Testing`, `Embedded MicroIntegrations` (cross-board bench tests), `ALL ECUs` (shared code on every board). Use `Misc Tasks` only if nothing fits |
| **Owner** | From step 1. If "unassigned", leave it empty and the status becomes `Needs Owner` |
| **Status** | `Upcoming` for new work with an owner, `Needs Owner` without one. `Working on it` only if the user says it has started |
| **Priority** | `Critical` = blocks driving or safety, or a comp deadline. `High` = blocks other work or an upcoming test. `Medium` = normal feature or bug (default). `Low` = nice to have or cleanup |
| **Tags** | Optional, only if the user says so: `MVP` (needed for the car to run), `MMR`, `backlog` |
| **Timeline** | Optional `--start/--end YYYY-MM-DD`, only if the user gives dates |

## 3. Write the first update (required format)

The first update must have exactly these two sections, in this order:

```
Description:

<What is wrong or missing today, why it matters, and the proposed approach. 2-5 sentences
(a second paragraph for a DR0's open questions and links), plain language, name the board,
files and mechanisms involved.>

Definition of Done:

<one checkable deliverable per line>
```

Definition of Done rules:
- Each line is a concrete, checkable outcome (file or function written, behaviour verified),
  not a vague step.
- The last lines are always, in this order: **`Tested and Monday update written`** and
  **`Merged into main`**. Add them if the user left them out.
- If the input is a design review (DR0) instead of a short description, the ticket covers the
  **whole DR** for its board, not just one part. The Description gives the DR's purpose, open
  questions and resource links. The Definition of Done has one line per DR requirement, with
  its test (e.g. firmware, fault diagnostics, CAN ID + CAN ID table, DBC, Grafana). When the
  DR spans several boards, make one ticket per board, each with the full DR scoped to that board.
  Only TEL has the radio: on any other board, data goes over CAN to TEL, which sends it over radio.
  Leave out process steps the closing lines already cover (branch, PR): fold them into
  `Merged into main (branch off firmware_v4, GitHub pull request)`.
- Fix spelling and grammar, but keep the user's technical content. Don't invent requirements;
  if the scope is unclear, ask.

Example: user says *"STR polls GPIO in an RTOS task, fast presses can be missed, switch to
interrupts"*:

```
Description:

STR currently polls the GPIO pins: an if statement inside an RTOS task checks whether each
button is pressed. If a button is pressed and released quickly while another task is running,
the press is never seen. Switching to GPIO interrupts fixes this.

Definition of Done:

Software written in interrupts.c in the STR runtime with an IRQ handler
A state machine function that checks which GPIO pin was pressed and runs the corresponding functionality
Tested and Monday update written
Merged into main
```

## 4. Confirm, then create

1. Show the user the full draft (title, group, owner, status, priority, tags, update text) and
   wait for an OK. Creating the ticket posts to a shared team board. A reply that only
   adjusts fields (e.g. "do Kevin Yu instead for TEL") is an OK for the adjusted draft.
2. Dry run, which checks the group, labels and owner without writing anything:
   ```bash
   python3 <skill dir>/scripts/create_ticket.py --dry-run \
     --title "..." --group STR --priority Medium --owner "Full Name" [--tag MVP] \
     --description "$(cat <<'EOF'
   paragraph one

   optional paragraph two
   EOF
   )" \
     --dod "first deliverable" --dod "..." --dod "Tested and Monday update written" --dod "Merged into main"
   ```
   If an owner name is ambiguous, the script lists the matches. Ask which one.
   If the owner **matches nobody** (not on Monday yet, or an account that only shows an email),
   don't guess. Ask the user to choose: (a) a different full name or email, (b) create it
   unassigned as `Needs Owner` and assign later, or (c) wait until the person is added.
3. Run the same command without `--dry-run`. It creates the item, posts the update, and
   prints the ticket number (`EMB-<n>`) and URL. Report both to the user.

Never run the script twice for the same ticket. If it fails partway (e.g. the item was created
but the update failed), check the board before retrying.

## Changing an existing ticket

To fix a ticket after it's created (e.g. widen the scope), rewrite its first update in
place instead of posting a new one, so the formatted update stays first:

```bash
python3 <skill dir>/scripts/create_ticket.py --edit <item id> [--title "new title"] \
  --description "..." --dod "..." --dod "Tested and Monday update written" --dod "Merged into main"
```

The item id is the number after `/pulses/` in the URL. Add `--dry-run` to preview. If the
change makes the title wrong, pass a new `--title` too. Other columns (owner, group, status)
are quicker to change in Monday directly.
