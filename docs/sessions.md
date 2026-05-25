# Sessions

Sessions are optional. They let one set of hugr verb invocations
share state - last result, working set, scratchpad - without needing
to thread that state through env vars or pipes.

## When to use them

- Multi-turn agent conversations where each `recall` is a follow-up.
- Notebook-style exploration in the TUI / web UI.
- Bookmarking "the things I'm currently looking at" across screens.

If you don't need any of this, ignore the verbs entirely. Sessions
are off by default; verbs work statelessly when `HUGR_SESSION` is
unset.

## Lifecycle

```bash
# Start - hugr prints the id and an export line you can eval.
$ hugr session start
started session a1b2c3d4
  export HUGR_SESSION=a1b2c3d4

# Use the session - subsequent verbs see HUGR_SESSION and write to it.
$ export HUGR_SESSION=a1b2c3d4
$ hugr recall "what did we decide?"
$ hugr inbox

# Status - what is active, who is in the list, when was each last used.
$ hugr session status --pretty
current: a1b2c3d4
  * a1b2c3d4  last_used=2026-05-25T12:30:21Z  ttl=1800s
  - 9f3aab12  last_used=2026-05-25T11:55:01Z  ttl=1800s

# End - removes the active session dir (or any session by id).
$ hugr session end
ended session a1b2c3d4

# GC - removes every session past its TTL.
$ hugr session gc
removed 1 stale session(s):
  - 9f3aab12
```

`hugr session start --json | jq -r '.hint'` returns the `export` line
ready for `eval`:

```bash
eval "$(hugr session start --json | jq -r '.hint')"
# now HUGR_SESSION is set in the current shell
```

## What gets stored

Each session lives under `$HUGR_HOME/sessions/<id>/`:

```
$HUGR_HOME/sessions/a1b2c3d4/
├── meta.json           # id, created_at, last_used_at, ttl_seconds
├── last_recall.json    # the last hugr.api.recall() document (when set)
└── working_set.json    # ids surfaced by the last hugr.api.inbox() call
```

The `scratch.md` slot from the original plan is reserved but not yet
auto-populated by any verb; you can write to it yourself for
surface-shared notes.

## Auto-populated fields

- `hugr recall` writes the full result document (including sources +
  citations + warnings) to `last_recall.json` and touches
  `last_used_at`.
- `hugr inbox` extracts ids from each `sources[].data` payload and
  writes them to `working_set.json` as
  `{"items": [...], "updated_at": "..."}`.

Other verbs (`find`, `remember`, `send mail`, ...) do **not** write
to the session today. Add them yourself if you want by editing the
JSON files directly - hugr will pick them up on the next read.

## TTL and GC

Default TTL is 1800 seconds (30 minutes). Override at creation:

```bash
hugr session start --ttl 3600
```

A session is "stale" when `last_used_at` falls more than `ttl_seconds`
into the past. `hugr session gc` removes the directory for each
stale session and returns the list of removed ids:

```json
{
  "tool": "hugr",
  "command": "session gc",
  "ok": true,
  "exit_code": 0,
  "removed": ["9f3aab12"],
  "count": 1
}
```

`hugr doctor` does not yet auto-run gc - call it from a cron or
launchd job if you create sessions often.

## Using sessions from agents / scripts

The cleanest pattern is to capture the id once and forward it via env:

```bash
SID=$(hugr session start --json | jq -r '.session.id')
HUGR_SESSION="$SID" hugr recall "..."
HUGR_SESSION="$SID" hugr inbox
HUGR_SESSION="$SID" hugr session status --json | jq '.active'
hugr session end "$SID"
```

For agents that fork multiple processes, each one only needs to
inherit `HUGR_SESSION` - the session storage is filesystem-backed and
safe for concurrent reads. Concurrent writes to the *same* file are
last-writer-wins; if you need stronger semantics, write through one
coordinator process.

## What sessions do NOT do

- They don't anonymize anything - `last_recall.json` contains the
  full query text and result payload.
- They aren't synced across devices by default; `hugr sync` does
  not push the sessions directory. Hand-edit the includes if you
  want them in the state repo.
- They're not access-controlled - file mode is whatever your umask
  gave you; sessions live in your user's data root.

## Web UI integration

`GET /session` (JSON: `GET /api/session`) renders the same data
`hugr session status` returns. `GET /session/<id>` (or
`GET /api/session/<id>`) renders one session with its `meta`,
`last_recall`, and `working_set` in one document. See
[surfaces.md](surfaces.md).
