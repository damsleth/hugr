# Mutating verbs: `send`, `book`, `remember`

The four fused mutating verbs share one rule: they require explicit
confirmation before they write anything. The exact mechanism depends
on how you invoke them.

## The confirmation rule

| Invocation context | Behavior |
| --- | --- |
| Interactive TTY, no `--yes` | Prompts `Proceed with hugr <verb>? [y/N]`. |
| Interactive TTY, `--yes` | Skips the prompt; proceeds. |
| Non-TTY (script / pipe), no `--yes` | Refuses; prints `requires --yes when stdin is not a TTY`. Exit 1. |
| `--json`, no `--yes` | Refuses; returns envelope with `error.code = "confirmation_required"`. Exit 1. |
| `--json --yes` | Proceeds. Recommended for scripts and agents. |

The same rule applies to `hugr sync push` (mutates the state repo)
and `hugr remember` (mutates the ledger).

## `hugr send mail`

Wraps `owa-mail send`. Required flags: `--to`, `--subject`, `--body`.

```bash
# Minimal interactive
hugr send mail --to a@example.com --subject "lunch" --body "12:00 tomorrow?"

# Headless / scripted
hugr send mail --to a@example.com --subject "lunch" --body "12:00?" --yes --json

# Multiple recipients, cc, bcc, html body
hugr send mail \
  --to a@example.com --to b@example.com \
  --cc team@example.com \
  --bcc audit@example.com \
  --subject "weekly update" \
  --body "$(cat update.html)" \
  --html \
  --yes
```

Response (action envelope):

```json
{
  "tool": "hugr",
  "command": "send mail",
  "ok": true,
  "exit_code": 0,
  "request": {
    "to": ["a@example.com"],
    "subject": "lunch",
    "cc": [],
    "bcc": [],
    "html": false,
    "body_length": 17
  },
  "result": {"id": "AAMkAG..."},
  "error": null
}
```

`body_length` (not the body itself) is echoed in `request` to keep
the envelope safe to log without leaking message contents.

## `hugr send invite`

Wraps `owa-cal create`. The only required flag is `--subject`.

```bash
hugr send invite --subject "Standup" --date tomorrow --start 09:00 --end 09:15 --yes

hugr send invite \
  --subject "Q3 review" \
  --date 2026-06-15 --start 14:00 --end 15:30 \
  --location "Oslo, Room 12" \
  --body "Agenda lives at notes/q3-review.md" \
  --category "internal" \
  --showas busy \
  --yes
```

**Heads up**: owa-cal create does not yet accept attendees (an
upstream gap, tracked in `AUDIT.md`). For meetings *with* attendees,
do one of:

- Follow up the create with a manual invite in Outlook.
- Wait for owa-tools v0.2.
- Use `hugr graph POST '/me/events' ...` for the raw Microsoft Graph
  call.

## `hugr book propose <intent>` + `hugr book commit <intent>`

Two-step scheduling.

### Step 1: propose

Calls `owa-sched find-time` and returns a `ScheduleProposal`. Pure
data, no mutation.

```bash
hugr book propose "Standup with Vibeke" \
  --who vibeke@example.com \
  --duration 30 \
  --date tomorrow \
  --pretty
```

```json
{
  "tool": "hugr",
  "command": "schedule",
  "ok": true,
  "exit_code": 0,
  "intent": "Standup with Vibeke",
  "proposed_subject": "Standup with Vibeke",
  "request": {
    "who": ["vibeke@example.com"],
    "duration_minutes": 30,
    "date": "tomorrow",
    "week": null,
    "year": null
  },
  "slots": [
    {"date": "2026-05-26", "start": "09:00", "end": "09:30"},
    {"date": "2026-05-26", "start": "10:30", "end": "11:00"}
  ],
  "raw": {...},
  "error": null
}
```

### Step 2: commit

Re-runs the proposal and creates the event from the chosen slot.

```bash
hugr book commit "Standup with Vibeke" \
  --who vibeke@example.com \
  --duration 30 \
  --date tomorrow \
  --slot 0 \
  --yes
```

`--slot N` (default 0) indexes into the proposal slot list. If the
slot is out of range, the envelope returns `error.code = "slot_unavailable"`
and exit 4:

```json
{
  "tool": "hugr",
  "command": "book commit",
  "ok": false,
  "exit_code": 4,
  "error": {
    "code": "slot_unavailable",
    "message": "no proposal slot at index 5 (found 3)",
    "hint": "Run `hugr book propose` first to see available slots."
  },
  "proposal": {...}
}
```

Optional event metadata is forwarded straight to `send invite`:

```bash
hugr book commit "1:1" \
  --who manager@example.com \
  --slot 1 \
  --location "Coffee shop" \
  --body "Catch up on the Q3 hand-off" \
  --category "1:1" \
  --yes
```

## `hugr remember <fact>`

Wraps `ledger notes add`. Captures a fact directly into Tier 2
without going through the YAAMS-promote review queue.

```bash
hugr remember "Nina prefers early flights" --yes
hugr remember "Deploy gate is the GROWTH-3142 flag" --type fact --link topic:deploys --yes
hugr remember "Acme moved the Globex onboarding to Q3" \
  --type project \
  --link org:acme --link person:nina \
  --yes --json
```

Flags:

| Flag | Default | Meaning |
| --- | --- | --- |
| `--type <name>` | `fact` | Note type; passed to `ledger notes add --type`. |
| `--link <slug>` | (empty) | Repeatable. Each becomes a `--link` on the ledger call. |
| `--yes` | off | Forwarded to ledger so the underlying note creation also skips its own confirmation. |

Response:

```json
{
  "tool": "hugr",
  "command": "remember",
  "ok": true,
  "exit_code": 0,
  "fact": "Nina prefers early flights",
  "note_type": "fact",
  "links": [],
  "result": {"id": "fact__nina_prefers_early_flights_2026-05-25.md"},
  "error": null
}
```

## When something fails

A non-zero exit from the underlying tool surfaces in the envelope:

```json
{
  "tool": "hugr",
  "command": "send mail",
  "ok": false,
  "exit_code": 3,
  "request": {...},
  "result": {...},
  "error": {
    "code": "owa_mail_send_failed",
    "message": "owa-mail send failed",
    "hint": "Run `hugr mail send --help` to inspect the underlying flags."
  }
}
```

Exit codes follow [CONVENTIONS.md](../CONVENTIONS.md):

- `0` success
- `1` user error / aborted
- `2` transient (network, rate limit)
- `3` auth (token expired - `hugr auth reseed`)
- `4` not found (or out-of-range slot, or missing master config)
- `5` partial success

When `-v`/`--verbose`/`--debug` is set (e.g. `hugr -v send mail ...`),
hugr forwards verbose mode to the underlying tool (owa-mail/owa-cal)
and streams its diagnostics — redacted — to stderr, leaving the JSON
envelope on stdout untouched.

## Web mutations

The web UI exposes the same verbs under `/send/mail`, `/send/invite`,
and `/remember`. Each GET page renders a form; each POST requires a
`confirm=on` field (the form has a visible "I confirm" checkbox).

A POST without `confirm` returns HTTP 412 with the same envelope
shape:

```bash
curl -sS http://127.0.0.1:7777/send/mail \
  -H 'Accept: application/json' \
  -d to=a@example.com -d subject=test -d body=hi
# -> 412 {"error": {"code": "confirmation_required", ...}}

curl -sS http://127.0.0.1:7777/send/mail \
  -H 'Accept: application/json' \
  -d to=a@example.com -d subject=test -d body=hi -d confirm=on
# -> 200 (or 502 on tool failure) action envelope
```

See [surfaces.md](surfaces.md) for the full web route inventory.
