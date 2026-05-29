---
name: hugr-suite-yaams
description: Use when an agent touches raw memory, asks where ingested data came from, queries Tier 1, or works with ingest sources, promotion candidates, or the YAAMS schema.
metadata:
  suite_version: "0d1c0f6"
---

# YAAMS — Tier 1 raw memory store

YAAMS (Yet Another Agentic Memory Store) is the high-volume ingest
layer of the hugr suite. It normalizes iMessage, Apple Mail, Signal,
GitHub, Teams, calendar events, and more into a single SQLite database,
embeds them, and makes them queryable by semantic search plus keyword
filters.

## Architecture summary

- YAAMS is **Tier 1** in the two-tier memory model: ingest everything
  first, curate later via promotion to the cognitive ledger.
- The store is a local SQLite file (`db_path`) — never committed, never
  synced by default. Each adapter has a watermark so re-ingests are
  incremental.
- **Semantic search** uses embeddings (default: BAAI/bge-m3) stored
  alongside each row; `yaams query` does ANN search + keyword boosting.
- **Tier 2 integration**: the `tier2_ledger` adapter reads the cognitive
  ledger as a source during query, giving curated notes a small rank
  boost over raw ingest when both match (`--tier both` default).
- YAAMS never imports hugr, cognitive-ledger, owa-piggy, or owa-tools
  at runtime. It shells out to `owa-piggy` for Teams/calendar adapters
  and accepts `owa-piggy` tokens over the local socket.

## Public surface

Binary: `yaams`

Config: `$XDG_CONFIG_HOME/hugr/yaams/config.yaml` (env: `YAAMS_CONFIG`)
Data: `$HUGR_HOME/yaams/data.db` or config `db_path` (env: `HUGR_HOME`)

### Top-level commands

| command | class | description |
|---|---|---|
| `yaams setup` | action | First-time setup wizard |
| `yaams init-db` | action | Create / migrate the SQLite schema |
| `yaams ingest [--source <src>] [--json]` | action | Ingest all (or one) source; streams NDJSON progress |
| `yaams query "<text>" [--tier raw|ledger|both] [--json]` | data | Semantic + keyword search |
| `yaams stats [--json]` | data | Counts, sizes, last-ingest timestamps |
| `yaams signals [--json]` | data | List configured signal sources |
| `yaams feedback --id <id> --verdict <v>` | action | Log hit/miss/correction feedback |
| `yaams consolidate` | action | De-duplicate and re-embed |
| `yaams promote generate` | action | Generate promotion candidates |
| `yaams promote list [--json]` | data | List existing candidates |
| `yaams promote review` | interactive | Review candidates (TTY) |
| `yaams entities list/add/remove/discover/denied/manage` | data/action | Managed entity registry |
| `yaams enrich retag` | action | Re-run entity tagging across the store |
| `yaams reset-db --yes` | action + destructive | Drop and recreate the database |
| `yaams --doctor [--json]` | data | Conformance + health check |
| `yaams --version` | data | `{"tool":"yaams","version":"x.y.z"}` |

### `--tier` flag (Phase 2b addition)

`--tier raw` — query YAAMS rows only.
`--tier ledger` — query via the `tier2_ledger` adapter only.
`--tier both` — query both; ledger notes get a rank boost (default).

`hugr query` is a thin passthrough; `--tier` is handled natively by
yaams and needs no rewrite in the hugr router.

## Code location

Repo: `~/code/yaams/`

| file | purpose |
|---|---|
| `yaams/cli/main.py` | Click CLI entry point |
| `yaams/ingest/` | per-source adapters (imessage, signal, github, …) |
| `yaams/query.py` | semantic search + tier routing |
| `yaams/promote/` | candidate generation and review |
| `yaams/entities/` | entity registry |
| `yaams/conventions.py` | vendored CONVENTIONS.md helpers |
| `yaams/db.py` | SQLite schema + watermarks |

## Key conventions

- `--json` must be accepted on every non-interactive command
  (`req` in the conformance table). Legacy `--format json` is an alias.
- `yaams ingest` is action-class; with `--json` it streams NDJSON
  (`{type:"progress",...}` lines) terminated by `{type:"result",...}`.
- `yaams promote review` is interactive-class; rejects `--json`.
- The internal source ID for the ledger adapter is `tier2_ledger`
  (not `ledger`). The CLI accepts `ledger` as an alias; SQLite rows
  store the original ID unchanged.
- Exit codes: 0 ok, 1 user error, 2 transient, 3 auth, 4 not found,
  5 partial success (some sources failed during ingest).

## Cross-component touchpoints

| component | how YAAMS talks to it |
|---|---|
| cognitive-ledger | reads the notes directory directly as `tier2_ledger` adapter (path from config); no subprocess, no import |
| owa-piggy | shells out to `owa-piggy token` to get M365 access tokens for Teams/calendar adapters |
| hugr | YAAMS is called *by* hugr via subprocess; YAAMS never calls hugr |

## Pointers

- Full verb table with options and exit semantics: `references/cli-surface.md`
- CONVENTIONS.md slices relevant to YAAMS: `references/conventions.md`
- Common failure modes: `references/troubleshooting.md`
- Suite hub and router: `[[hugr-suite-hugr]]`
- Tier 2 curated notes engine: `[[hugr-suite-ledger]]`
- M365 auth (needed for Teams/calendar adapters): `[[hugr-suite-owa-piggy]]`
