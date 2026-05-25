# Recall, find, inbox

The three fused query verbs hit multiple underlying tools, merge the
results, and return one document. They're the "ask the suite anything"
surface.

## `hugr recall <question>`

What it calls:

1. `yaams query <question>` (Tier 1 raw + Tier 2 ledger via the
   `tier2_ledger` source).
2. **Live M365** when `--no-live` is not set:
   - `owa-cal events --search <question>`
   - `owa-mail search <question>`

Each tool's stdout becomes one entry in `sources[]`. Successful
sources also generate a `citations[]` entry so consumers can render a
deduped list of links.

### Examples

```bash
hugr recall "what did we decide at the brand kickoff?"
hugr recall "easter dinner" --pretty
hugr recall "OKRs" -k 20 --json | jq '.citations'
hugr recall "OKRs" --no-live           # skip live M365 hops
HUGR_SESSION=$(hugr session start --json | jq -r .session.id) hugr recall "follow-up"
```

### Output shape

```json
{
  "tool": "hugr",
  "command": "recall",
  "query": "easter dinner",
  "limit": 10,
  "sources": [
    {"source": "yaams", "command": "query", "ok": true, "exit_code": 0, "data": {...}},
    {"source": "owa-cal", "command": "events", "ok": true, "exit_code": 0, "data": [...]},
    {"source": "owa-mail", "command": "search", "ok": true, "exit_code": 0, "data": [...]}
  ],
  "citations": [
    {"source": "yaams", "label": "yaams", "ref": "...", "ok": true},
    {"source": "owa-cal", "label": "owa-cal", "ref": "evt-12", "ok": true}
  ],
  "warnings": []
}
```

If a source failed (auth expired, tool not on PATH, ...) it shows up
in `sources[].ok = false` and gets one entry in `warnings[]` with the
exit code and message. `recall` itself still returns exit 0 - partial
success is the norm here, not an error.

### Ranking

Today, ranking is "naive concatenation": each source returns its
top-k, and the result document carries them in source order with
basic dedupe by source-id. A future iteration may add embedding-based
fusion once the YAAMS embedding API stabilizes.

## `hugr find <kind> <query>`

Typed search. One source per kind:

| Kind | Route |
| --- | --- |
| `person`, `people` | `owa-people lookup <query>` |
| `event` | `owa-cal events --search <query>` |
| `message`, `mail` | `owa-mail search <query>` |
| `note` | `ledger query <query>` |
| `file` | `yaams query <query>` (Tier 1 raw) |
| (anything else) | `yaams query <query>` |

### Examples

```bash
hugr find person nina
hugr find event "easter dinner"
hugr find message "PR review"
hugr find note "auth refactor"
hugr find file "deploy script" --json
hugr find people "kim damsleth"
```

### Output shape

```json
{
  "tool": "hugr",
  "command": "find",
  "kind": "person",
  "query": "nina",
  "limit": 10,
  "source": {
    "source": "owa-people",
    "command": "lookup",
    "ok": true,
    "exit_code": 0,
    "data": [...]
  },
  "warnings": []
}
```

Unlike `recall`, `find` calls exactly one source, so the result
document carries `source` (singular) rather than `sources[]`.

## `hugr inbox`

Cross-tool triage. Always calls these four sources in this order:

1. `owa-mail list --unread`
2. `owa-cal events --today`
3. `ledger loops`
4. `yaams promote list`

### Examples

```bash
hugr inbox
hugr inbox --pretty
hugr inbox --json | jq '.sources[] | {source, command, ok}'
```

### Output shape

Same shape as `recall` but with no `query` / `citations`:

```json
{
  "tool": "hugr",
  "command": "inbox",
  "sources": [
    {"source": "owa-mail", "command": "list", "ok": true, "data": [...]},
    {"source": "owa-cal", "command": "events", "ok": true, "data": [...]},
    {"source": "ledger", "command": "loops", "ok": true, "data": {...}},
    {"source": "yaams", "command": "promote list", "ok": true, "data": [...]}
  ],
  "warnings": []
}
```

## How sessions interact with these verbs

If `HUGR_SESSION` is set to a real session id:

- `hugr recall` writes the full result document to
  `$HUGR_HOME/sessions/<id>/last_recall.json` so the next surface
  (TUI, web) can show it.
- `hugr inbox` extracts ids from each source's payload and writes
  them to `$HUGR_HOME/sessions/<id>/working_set.json`.

Sessions are entirely opt-in. Without `HUGR_SESSION`, neither verb
writes anything.

See [sessions.md](sessions.md).

## First-run guard

All three verbs require a master config at
`$XDG_CONFIG_HOME/hugr/config.toml`. Without one, hugr exits with
code 4 and prints:

```
x hugr: no hugr config at /Users/.../config.toml.
    Fix:  hugr init
```

Set `YAAMS_CONFIG` or `HUGR_CONFIG` in the environment to bypass the
guard (useful for one-off agent runs against a custom config).
