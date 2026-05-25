# CLI reference

Every `hugr` subcommand, what it does, and at least one realistic
example. For verbs that are pure passthroughs to an underlying tool
(`hugr mail`, `hugr cal`, `hugr ledger`, ...) the underlying tool's
`--help` is the source of truth; the entries below cover the hugr
shape.

Common flags accepted on most verbs:

| Flag | Meaning |
| --- | --- |
| `--json` | Machine mode (JSON document or envelope on stdout). |
| `--pretty` | Human rendering. Default for terminals. |
| `--yes` | Skip the interactive confirmation prompt on mutating verbs. |
| `--verbose` / `-v` | Dump captured stderr from subprocess failures. |

Exit codes follow [CONVENTIONS.md](../CONVENTIONS.md):
`0` ok, `1` user error, `2` transient, `3` auth, `4` not found,
`5` partial success.

## Top-level

### `hugr` (no subcommand)

Bare `hugr` prints the hello screen. On a fresh machine without a
master config it offers to launch `hugr init`.

```bash
hugr
hugr --doctor       # equivalent to `hugr doctor`
hugr --json         # machine mode for top-level commands
```

### `hugr hello`

One-screen tour: fused verbs, tool passthroughs, current doctor status.

```bash
hugr hello
hugr hello --json   # JSON document with the same content
```

### `hugr version`

hugr's own version plus the observed version of every detected
component on PATH.

```bash
hugr version
hugr version --json | jq '.components'
```

### `hugr list`

Enumerate every binary the suite installs (`hugr`, `yaams`, `ledger`,
`ledger-obsidian`, `sheep`, `owa-piggy`, `owa-cal`, `owa-mail`,
`owa-graph`, `owa-people`, `owa-sched`, `owa-drive`, `owa-doctor`).

```bash
hugr list
hugr list --json
```

### `hugr doctor`

Cross-tool health check.

```bash
hugr doctor
hugr doctor --json
hugr doctor --fix --yes   # apply bounded self-healing
```

`--fix` is gated by `--yes` (or per-item TTY confirmation). Today the
applied fixes cover: missing master config, missing yaams DB,
disabled-but-still-present adapters, M365 profile staleness hints.

### `hugr init`

First-run wizard. See [init.md](init.md) for the full contract.

```bash
hugr init           # interactive
hugr init --quick   # non-interactive, recommended for install docs
hugr init --quick --json
hugr init --force   # overwrite an existing yaams config without prompting
hugr init --quick --with-models   # also download embedding models
```

`--quick` accepts `--json`. The bare `hugr init` is interactive and
rejects `--json`.

## Fused query verbs

These call multiple underlying tools and return a fused result. See
[recall.md](recall.md) for the full output shape.

### `hugr recall <question>`

Fused cross-tool ask. Hits YAAMS query plus, optionally, live
`owa-cal events --search` and `owa-mail search` buckets.

```bash
hugr recall "what did we decide at the brand kickoff?"
hugr recall "easter dinner" --pretty
hugr recall "OKRs" -k 20 --json
hugr recall "OKRs" --no-live   # skip the live M365 hop
```

### `hugr find <kind> <query>`

Typed search. `<kind>` is one of: `person`, `event`, `message`,
`mail` (alias for message), `note`, `file`. Anything else falls back
to `yaams query`.

```bash
hugr find person nina
hugr find event "easter dinner"
hugr find message "PR review"
hugr find note "auth refactor"
hugr find file "deploy script" --json
hugr find people nina        # alias for person
```

### `hugr inbox`

Cross-tool triage view. Calls (in order) `owa-mail list --unread`,
`owa-cal events --today`, `ledger loops`, `yaams promote list`.

```bash
hugr inbox
hugr inbox --pretty
hugr inbox --json | jq '.sources[] | {source, ok}'
```

## Mutating fused verbs

All four are interactive by default. Without `--yes`, they prompt the
user; in `--json` mode without `--yes`, they return an envelope with
`error.code = "confirmation_required"` and exit 1. See
[mutations.md](mutations.md).

### `hugr remember <fact>`

Promote a fact directly into the ledger.

```bash
hugr remember "Nina prefers early flights" --yes
hugr remember "deploy gate is the GROWTH-3142 flag" --type fact --link topic:deploys --yes
hugr remember "Inmeta moved Norconsult onboarding to Q3" --type project --link org:inmeta --yes --json
```

### `hugr send mail`

Send mail via `owa-mail send`.

```bash
hugr send mail --to a@example.com --subject "lunch" --body "12:00 tomorrow?" --yes
hugr send mail \
  --to a@example.com --to b@example.com \
  --cc team@example.com \
  --subject "weekly update" \
  --body "$(cat update.md)" \
  --html \
  --yes
```

### `hugr send invite`

Create a calendar event via `owa-cal create`.

```bash
hugr send invite --subject "Standup" --date tomorrow --start 09:00 --end 09:15 --yes
hugr send invite \
  --subject "Q3 review" \
  --date 2026-06-15 --start 14:00 --end 15:30 \
  --location "Oslo Office, Room 12" \
  --body "Agenda lives at notes/q3-review.md" \
  --category "internal" \
  --showas busy \
  --yes
```

Note: owa-cal create does not yet accept attendees (an upstream gap in
owa-tools v0.1). For meetings with attendees, follow up the create
with a manual invite, or wait for owa-tools v0.2.

### `hugr book propose <intent>`

Find candidate slots without mutating anything.

```bash
hugr book propose "Standup with Vibeke" --who vibeke@example.com --duration 30 --date tomorrow --pretty
hugr book propose "Brand kickoff" --who a@x.com --who b@x.com --duration 60 --week 23 --year 2026 --json
```

### `hugr book commit <intent>`

Re-runs the proposal and creates the event from the chosen slot.

```bash
hugr book commit "Standup with Vibeke" --who vibeke@example.com --duration 30 --date tomorrow --slot 0 --yes
hugr book commit "1:1" --who manager@example.com --duration 30 --date 2026-06-01 --slot 2 --location "Coffee" --yes --json
```

If the slot index is out of range, the envelope returns
`error.code = "slot_unavailable"` and exit 4 - re-run `book propose`
to see the current slot list.

## Sessions

See [sessions.md](sessions.md).

```bash
hugr session start                # creates a new session, prints HUGR_SESSION hint
hugr session start --ttl 3600     # set the TTL on the new session (default 1800s)
hugr session status               # active + listed sessions
hugr session list                 # just the list
hugr session end                  # ends the active session (HUGR_SESSION)
hugr session end abc123ef         # ends a specific session by id
hugr session gc                   # purge stale sessions
```

## Underlying-tool passthroughs

These pass arguments through to the named tool. JSON-by-default tools
(owa-*, owa-piggy) keep their native JSON; yaams/ledger get `--json`
injected per the router table.

### YAAMS (Tier 1)

```bash
hugr query "easter dinner"
hugr query "easter dinner" --tier ledger    # only Tier 2 (ledger via tier2_ledger source)
hugr query "easter dinner" --tier both
hugr ingest                                  # all enabled sources
hugr ingest --json                           # NDJSON stream + final envelope
hugr ingest --source imessage                # one source
hugr promote review                          # interactive (rejects --json)
hugr promote generate
hugr promote list
```

### cognitive-ledger (Tier 2)

```bash
hugr ledger init
hugr ledger paths
hugr ledger query "auth refactor"
hugr ledger loops
hugr ledger notes
hugr ledger context              # bare 'context' emits boot JSON
hugr ledger context build
hugr ledger context profiles
```

### owa-piggy (auth)

```bash
hugr auth status                 # all profiles
hugr auth profiles               # list / manage M365 profiles
hugr auth reseed                 # refresh expired tokens from Edge sidecar
hugr auth setup                  # interactive first-time setup (rejects --json)
```

### owa-tools (M365 read/write)

```bash
hugr mail list --unread
hugr mail search "PR review"
hugr cal events --today
hugr cal events --search "easter"
hugr graph GET '/me/messages?$top=5'
hugr people lookup nina
hugr schedule find-time --who a@x.com --duration 30 --date tomorrow
hugr schedule availability --who a@x.com --date tomorrow
hugr drive ls /Documents
```

`hugr schedule` is the **passthrough** to owa-sched. The **fused**
slot proposal verb is `hugr book propose` (renamed to avoid the name
collision).

## Surfaces

```bash
hugr tui                             # Textual TUI (requires [tui] extra)
hugr web                             # FastAPI web on 127.0.0.1:7777
hugr web --host 0.0.0.0 --public     # requires HUGR_WEB_TOKEN
hugr server --host 127.0.0.1 --port 7777
hugr server --host 0.0.0.0 --insecure  # opt-in: no auth proxy required
hugr server --mcp                    # also mount /mcp Streamable HTTP
hugr mcp                             # stdio (default; for Claude Code)
hugr mcp --http --host 127.0.0.1 --port 7777   # standalone MCP HTTP
```

`hugr server` refuses non-loopback binds unless `HUGR_AUTH_PROXY` is
set to a known value (`cloudflare`, `tailscale`) or `--insecure` is
passed.

## Sync

See [sync.md](sync.md).

```bash
hugr sync init git@github.com:you/hugr-state.git
hugr sync init https://github.com/you/hugr-state.git --clone-into /var/lib/hugr/state
hugr sync status
hugr sync status --json
hugr sync push --yes
hugr sync push --yes --message "after kickoff"
hugr sync pull
```

## Global flags

```bash
hugr --version
hugr --doctor       # alias for `hugr doctor`
hugr --json ...     # top-level machine-mode hint
hugr -v ...         # verbose stderr dumps on subprocess failure
```

## Environment variables

Listed in [config.md](config.md). The high-value ones:

```bash
HUGR_HOME=...           # data root (default ~/.local/share/hugr)
XDG_CONFIG_HOME=...     # config root; master at $XDG_CONFIG_HOME/hugr/config.toml
HUGR_CONFIG=...         # override master config path
HUGR_SESSION=...        # current session id (see sessions.md)
HUGR_STATE_DIR=...      # state repo clone (see sync.md)
HUGR_DEVICE_ID=...      # per-device id for sync (default $USER@$HOSTNAME)
HUGR_AUTH_PROXY=...     # required for hugr server non-loopback bind
HUGR_WEB_TOKEN=...      # required for hugr web --public
YAAMS_CONFIG=...        # bypass hugr's first-run guard; resolved by yaams natively
```
