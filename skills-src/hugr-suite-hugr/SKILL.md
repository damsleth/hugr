---
name: hugr-suite-hugr
description: Use when an agent needs to know how a hugr verb reaches its backing tool — router TABLE, fused verbs, hugr.api, session model, or suite architecture.
metadata:
  suite_version: "0d1c0f6"
---

# hugr — suite hub and meta-CLI

hugr is the umbrella CLI that routes every user-facing verb to the
right underlying tool (yaams, cognitive-ledger, owa-piggy, owa-tools).
It adds fused verbs that combine results from multiple backends and
exposes a Python API layer used by the TUI and web surfaces.

## Architecture summary

- hugr is a **router + fuser**, not a reimplementation. It never
  reimplements logic that belongs in a backing tool; it only rewrites
  argv and aggregates results.
- The **TABLE** in `src/hugr/router.py` is the single source of truth
  for which hugr verb maps to which binary and subcommand.
- **Fused verbs** (`ask`, `find`, `inbox`, `remember`) live in
  `src/hugr/api/fused.py` and combine Tier 1 (YAAMS), Tier 2
  (ledger), and M365 (owa-tools) results in one response document.
- `hugr.api` is the internal Python API used by the TUI
  (`src/hugr/tui/`), web (`src/hugr/web/`), and automation.
  CLI, TUI, and web share the same fused result documents.
- The **passthrough layer** (`src/hugr/api/_passthrough.py`) shells
  out to the underlying binary, captures stdout, and returns
  `(exit_code, stdout_bytes)`. No inter-process imports; no runtime
  coupling to sibling repos.

## Public surface

Binary: `hugr`

Config: `$XDG_CONFIG_HOME/hugr/config.yaml`  (env: `HUGR_CONFIG`)
Data root: `$HUGR_HOME/` shared across the suite.

### Top-level verbs (router TABLE, abbreviated)

| hugr verb | backing binary | class |
|---|---|---|
| `query` | yaams | data |
| `ingest` | yaams | action |
| `stats` | yaams | data |
| `sources` | yaams | interactive |
| `promote review` | yaams | interactive |
| `promote generate` | yaams | action |
| `promote list` | yaams | data |
| `briefing` | ledger | data |
| `ledger init/paths/query/loops/notes/context` | ledger | data/action |
| `auth status/reseed/token/remaining/debug/decode/profiles` | owa-piggy | data |
| `auth setup` | owa-piggy | interactive |
| `mail` | owa-mail | data/action |
| `cal` | owa-cal | data/action |
| `graph` | owa-graph | data/action |
| `people` | owa-people | data |
| `schedule` | owa-sched | data |
| `drive` | owa-drive | data/action |

### Fused verbs (hugr.api, not in TABLE)

| verb | function | returns |
|---|---|---|
| `hugr recall` | `hugr.api.recall` | result doc with `sources[]`, `citations[]`, `warnings[]` |
| `hugr find <kind> <query>` | `hugr.api.find` | typed source result |
| `hugr inbox` | `hugr.api.inbox` | unread mail + events + loops + promotions |
| `hugr remember "<fact>"` | `hugr.api.remember` | action envelope |

### Special verbs (not in TABLE, implemented in commands/)

- `hugr hello` — lists verbs + examples; data-class.
- `hugr version` — aggregated version with `observed[]`; data-class.
- `hugr doctor` — aggregated `--doctor` from all components; data-class.
- `hugr init` — interactive first-time setup; rejects `--json`.
- `hugr server` — deploy-ready FastAPI runtime on loopback.
- `hugr tui` — Textual TUI.
- `hugr web` — FastAPI web on 127.0.0.1:7777.

### Key env vars

| var | effect |
|---|---|
| `HUGR_CONFIG` | hugr router-level config path |
| `HUGR_HOME` | shared data root; each tool resolves `$HUGR_HOME/<tool>/` |
| `HUGR_PASSTHROUGH` | set to `1` by hugr so child processes know they're inside a hugr call |
| `HUGR_AUTH_PROXY` | opt-in public bind (server mode) |

## Code location

Repo: `~/code/hugr/`

| file | purpose |
|---|---|
| `src/hugr/router.py` | TABLE, Mapping dataclass, `lookup()`, `verbs()` |
| `src/hugr/api/__init__.py` | public Python API; re-exports all wrappers |
| `src/hugr/api/fused.py` | `recall`, `find`, `inbox`, `remember` |
| `src/hugr/api/doctor.py` | `doctor()` aggregator |
| `src/hugr/api/_passthrough.py` | shells out to underlying binary |
| `src/hugr/cli.py` | Click CLI entry point |
| `src/hugr/commands/` | per-verb Click command modules |
| `src/hugr/conventions.py` | vendored CONVENTIONS.md contract helpers |
| `src/hugr/_minimums.py` | declared minimum versions per component |

## Key conventions

- **JSON policy** per TABLE row: `"inject"` (append `--json` if missing
  — yaams/ledger); `"native"` (owa-tools emit JSON by default, never
  inject); `"none"` (interactive or custom rewrite).
- **Action envelope invariant**: `ok: false` iff exit code is nonzero.
  Both must agree; disagreement is a bug.
- **stdout only** for all structured output (success docs, error
  envelopes, NDJSON streams). Stderr is free-text diagnostics only.
- **Exit codes**: 0 ok, 1 user error, 2 transient, 3 auth, 4 not found,
  5 partial success. owa-tools uses its own `0/2/10-15/20` taxonomy
  on command paths (deliberate signed-off divergence); hugr maps it
  on the `--doctor` surface.
- **No business logic in the router.** Argument mapping (flag rename,
  subcommand rename, default injection) is allowed. If a mapping needs
  more, the logic belongs in the underlying tool first.
- `HUGR_PASSTHROUGH=1` is set before every subprocess call so children
  can detect a hugr invocation and suppress TTY-only prompts.

## Cross-component touchpoints

hugr talks to all four components exclusively via subprocess (the
passthrough layer). No Python imports of yaams, ledger, owa-piggy,
or owa-tools at runtime — this is the loose-coupling axiom.

| component | how hugr calls it |
|---|---|
| yaams | `subprocess` via `_passthrough`; `--json` injected |
| cognitive-ledger (`ledger`) | `subprocess`; `--json` injected; `ledger context` gets `--format json` rewrite |
| owa-piggy | `subprocess`; JSON-native, no injection |
| owa-tools (`owa-*`) | `subprocess`; JSON-native, no injection; `--agent` envelope is owa-tools' machine-mode contract |

hugr.api fused verbs call `_passthrough.call()` for the sub-results
and merge them in Python before returning a single result dict.

## Pointers

- Full verb table with options and exit semantics: `references/cli-surface.md`
- CONVENTIONS.md contract excerpts relevant to hugr: `references/conventions.md`
- Common failure modes and remedies: `references/troubleshooting.md`
- Suite architecture diagram: `[[hugr-suite-hugr]]` → `SUITE.md`
- YAAMS (Tier 1 raw store): `[[hugr-suite-yaams]]`
- cognitive-ledger (Tier 2 curated): `[[hugr-suite-ledger]]`
- M365 auth broker: `[[hugr-suite-owa-piggy]]`
- M365 read/write CLIs: `[[hugr-suite-owa-tools]]`
