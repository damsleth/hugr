# hugr CLI surface

_Generated from `router.TABLE`, `src/hugr/api/__init__.py`, and
`CONVENTIONS.md`. Source of truth: `hugr --help` and `hugr hello`._

## Usage

```
hugr [OPTIONS] COMMAND [ARGS]...
```

Global flags accepted on every command:
- `--json`     machine mode (assert JSON output; enables NDJSON stream on long-running actions)
- `--pretty`   human-readable rendering (tables / prose)
- `--version`  emit `{tool, version, observed[]}` and exit
- `--help`     show help for the command

---

## Discovery verbs

### `hugr hello`
List all routed verbs with backing binary and one-line description.
- class: data
- stdout: `{"verbs": [...], "examples": [...]}`
- exit: 0 ok, 1 user error

### `hugr version`
Aggregate version of hugr + observed versions of backing binaries.
- class: data
- stdout: `{"tool":"hugr","version":"x.y.z","observed":[...]}`
- exit: 0 ok, 1 user error

### `hugr doctor [--fix] [--yes]`
Aggregate `--doctor` from all components.
- class: data
- `--fix` lists bounded self-healing fixes; `--fix --yes` applies them
- stdout: `{"tool":"hugr","findings":[...],"components":{...}}`
- exit: 0 ok, 1 user-fixable, 2 transient, 3 auth

---

## Memory verbs (fused — hugr.api)

### `hugr recall "<question>"`
Query Tier 1 (YAAMS) + Tier 2 (ledger) + live M365 when cache stale.
- class: data (fused)
- stdout: `{"answer":"...","sources":[...],"citations":[...],"warnings":[]}`
- exit: 0 ok, 2 transient, 3 auth, 5 partial

### `hugr find <kind> <query>`
Typed lookup against a single backing source.
- class: data
- `kind` one of: `person`, `event`, `message`, `note`, `fact`
- exit: 0 ok, 4 not found, 5 partial

### `hugr inbox`
Unread mail + today's calendar events + ledger open loops + YAAMS promotions.
- class: data (fused)
- stdout: `{"sources":{"mail":[...],"events":[...],"loops":[...],"promotions":[...]},"warnings":[]}`
- exit: 0 ok, 5 partial

### `hugr remember "<fact>" [--yes]`
Promote a one-line fact straight to the cognitive ledger.
- class: action
- `--yes` skips confirmation prompt
- stdout: action envelope with child ledger result under `stats`
- exit: 0 ok, 1 user error, 3 auth

---

## YAAMS verbs (Tier 1 passthrough)

### `hugr query <text> [OPTIONS]`
Query Tier 1 raw store via `yaams query`. Accepts `--tier raw|ledger|both`.
- class: data; `--json` injected
- exit: 0, 1, 2, 4

### `hugr ingest [OPTIONS]`
Ingest all configured sources via `yaams ingest`.
- class: action; streams NDJSON progress with `--json`
- exit: 0, 1, 2, 3, 5

### `hugr stats`
YAAMS store stats (counts, sizes, last ingest).
- class: data; exit: 0, 1

### `hugr sources`
Toggle ingest sources interactively.
- class: interactive; rejects `--json`

### `hugr promote generate`
Generate fresh promotion candidates.
- class: action; exit: 0, 1, 2

### `hugr promote list`
List existing promotion candidates.
- class: data; exit: 0, 1

### `hugr promote review`
Review candidates interactively (TTY required).
- class: interactive; rejects `--json`

### `hugr feedback`
Log retrieval feedback for a query.
- class: action; exit: 0, 1, 4

---

## cognitive-ledger verbs (Tier 2 passthrough)

All forwarded to `ledger` binary. `--json` injected unless noted.

### `hugr briefing [--weekly]`
Daily or weekly briefing. `json_policy=none` — ledger renders natively.

### `hugr ledger init`
Bootstrap a new ledger. action-class.

### `hugr ledger paths`
Show resolved ledger paths. data-class.

### `hugr ledger query <text>`
Query curated atomic notes directly. data-class.

### `hugr ledger loops`
List open loops. data-class.

### `hugr ledger notes [--type <type>]`
List notes by type. data-class.

### `hugr ledger context`
Output boot context as JSON. Rewritten to `ledger context --format json`.
`json_policy=none` — the `--format json` flag carries the contract.

### `hugr ledger context build`
Build curated context files. action-class; `--json` injected.

### `hugr ledger context profiles`
List ledger context profiles. data-class; `--json` injected.

### `hugr ledger sleep`
Electric Sheep maintenance (sleep, lint, index, status, sync).
`json_policy=none`; pass `--json` explicitly if needed.

### `hugr ledger links`
Show ledger link graph. `json_policy=none`.

---

## M365 auth verbs (owa-piggy passthrough, JSON-native)

### `hugr auth status [--profile <name>]`
Auth status for all profiles. data-class.

### `hugr auth setup`
Interactive first-time M365 setup. interactive; rejects `--json`.

### `hugr auth reseed [--profile <name>]`
Refresh expired tokens from Edge sidecar. action-class.

### `hugr auth profiles`
List / manage M365 profiles. data-class.

### `hugr auth token [--audience <aud>] [--profile <name>]`
Print an M365 access token. data-class. Exit 3 if expired.

### `hugr auth remaining [--profile <name>]`
Minutes left on current token. data-class. stdout: `{"minutes": N}`.

### `hugr auth debug [--profile <name>]`
Full owa-piggy diagnostics. data-class.

### `hugr auth decode [--profile <name>]`
Decode JWT header + payload. data-class.

---

## M365 read/write verbs (owa-tools passthrough, JSON-native)

All forwarded verbatim to the named binary. `json_policy=native`:
hugr never injects `--json`; owa-tools is JSON-by-default.
Use `--agent` (or `OWA_AGENT=1`) for the owa-tools machine-mode
envelope `{"_owa":{...},"data":<result>}`.

### `hugr mail <subcommand> [OPTIONS]` → `owa-mail`
subcommands: `messages`, `show`, `send`, `reply`, `reply-all`,
`forward`, `delete`, `move`, `mark`, `folders`, `config`, `refresh`

### `hugr cal <subcommand> [OPTIONS]` → `owa-cal`
subcommands: `events`, `events-webcal`, `create`, `update`, `delete`,
`categories`, `config`, `refresh`, `profiles`

### `hugr graph <subcommand> [OPTIONS]` → `owa-graph`
subcommands: `get`, `post`, `put`, `patch`, `delete`, `batch`,
`config`, `refresh`

### `hugr people <subcommand> [OPTIONS]` → `owa-people`
subcommands: `find`, `directory`, `show`, `me`, `contacts`,
`config`, `refresh`

### `hugr schedule <subcommand> [OPTIONS]` → `owa-sched`
subcommands: `availability`, `find-time`, `config`, `refresh`

### `hugr drive <subcommand> [OPTIONS]` → `owa-drive`
subcommands: `ls`, `show`, `get`, `put`, `rm`, `config`, `refresh`

---

## Exit code summary

| code | meaning |
|---|---|
| 0 | success |
| 1 | user error (bad flag, bad input) |
| 2 | transient / retryable (network, lock) |
| 3 | auth (token expired, scope missing) |
| 4 | not found |
| 5 | partial success — some sub-tasks failed, `warnings[]` populated |

Note: owa-tools command paths use `0/2/10-15/20`; hugr maps that
taxonomy on the `--doctor` surface only.
