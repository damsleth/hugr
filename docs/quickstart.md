# Quickstart

A five-minute tour of the verbs that matter day-to-day. Assumes you
already ran `hugr init --quick` (see [installation.md](installation.md)).

## 0) Sanity check

```bash
hugr hello       # one-screen tour
hugr doctor      # everything green?
```

If `doctor` lights up red, run `hugr doctor --fix --yes` to apply
the bounded self-healing fixes, or jump to
[troubleshooting.md](troubleshooting.md).

## 1) Ingest something

`hugr ingest` walks every adapter you enabled in the wizard (iMessage,
mail, calendar, GitHub, etc.) and writes rows into the YAAMS SQLite
DB. First run downloads embedding models with a prompt before any
download.

```bash
hugr ingest                  # all enabled sources, partial-success tolerant
hugr ingest --json           # NDJSON progress + final result envelope
hugr ingest --source imessage  # one source only
```

Re-run any time. YAAMS is incremental - it skips rows it already has.

## 2) Ask a question - `hugr recall`

`hugr recall` is the fused-query verb. It hits YAAMS (Tier 1 raw +
Tier 2 ledger via `tier2_ledger`) and opportunistically queries live
M365 buckets:

```bash
hugr recall "what did we decide at the brand kickoff?"
hugr recall "easter dinner" --pretty
hugr recall "current OKRs" --json | jq '.citations'
```

The result document has `sources[]` (one per tool it called) and
`citations[]` (one per result that came back ok). See
[recall.md](recall.md) for the full shape.

## 3) Typed search - `hugr find`

When you know what kind of thing you want:

```bash
hugr find person nina
hugr find event "easter dinner"
hugr find message "PR review"
hugr find note "auth refactor"
hugr find file "deploy script"
```

`hugr find` routes each kind to the right tool: `person` -> owa-people,
`event` -> owa-cal, `message` -> owa-mail, `note` -> ledger,
`file` -> yaams. See [recall.md](recall.md) for the routing table.

## 4) Today's triage - `hugr inbox`

One screen across every tool: unread mail + today's calendar events
+ open ledger loops + pending YAAMS promotion candidates.

```bash
hugr inbox
hugr inbox --json | jq '.sources[] | {source, command, ok}'
```

## 5) Capture a fact - `hugr remember`

Promote a fact directly into the ledger (bypassing the YAAMS-promote
review queue):

```bash
hugr remember "Nina prefers early flights" --type fact --link person:nina --yes
```

`--yes` is required when stdin is not a TTY (or when `--json` is set).
Without `--yes`, hugr prompts interactively. See
[mutations.md](mutations.md) for the confirmation rules.

## 6) Send mail or create a calendar event

```bash
hugr send mail --to a@example.com --subject "lunch" --body "12:00 tomorrow?" --yes
hugr send invite --subject "Standup" --date tomorrow --start 09:00 --end 09:15 --yes
```

Same `--yes` rule: in JSON mode or non-TTY, the flag is required.

## 7) Find a meeting slot - `hugr book`

`hugr book propose "Standup" --who a@x.com --duration 15 --date tomorrow`
returns a slot proposal (no mutation). Pick a slot and commit:

```bash
hugr book propose "Standup" --who a@x.com --duration 15 --date tomorrow --pretty
hugr book commit "Standup" --who a@x.com --slot 0 --duration 15 --date tomorrow --yes
```

`book commit` calls `hugr send invite` under the hood with the chosen
slot. The `--yes` rule applies.

## 8) Sessions (optional)

If you want one set of verb invocations to share state - last result,
working set, scratchpad - start a session:

```bash
$(hugr session start --json | jq -r '.hint')
# now $HUGR_SESSION is set; subsequent recall / inbox commands write
# last_recall.json and working_set.json under that session.

hugr recall "what did we decide?"
hugr session status --pretty
hugr session end       # uses the active session id

hugr session gc        # purge stale sessions older than their TTL
```

See [sessions.md](sessions.md).

## 9) Open the TUI or the web UI

```bash
hugr tui     # requires hugr-cli[tui]; default screen is recall
hugr web     # requires hugr-cli[web]; opens 127.0.0.1:7777
```

See [surfaces.md](surfaces.md) for what each screen does and how to
expose the web UI over a tunnel or VPN.

## 10) Move state between devices (optional)

Once you have a private GitHub repo for state (e.g.
`damsleth/hugr-state`):

```bash
hugr sync init git@github.com:you/hugr-state.git
hugr sync status
hugr sync push --yes   # snapshots master config + commits + pushes
hugr sync pull         # fast-forwards the local clone
```

See [sync.md](sync.md) for the data model, age-encryption, per-device
folders, and what is and isn't synced.

## Where to go from here

- The full command surface: [cli-reference.md](cli-reference.md)
- Configuration: [config.md](config.md)
- TUI / web / MCP / server: [surfaces.md](surfaces.md)
- When things break: [troubleshooting.md](troubleshooting.md)
