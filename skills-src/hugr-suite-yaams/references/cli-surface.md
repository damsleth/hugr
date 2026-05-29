# YAAMS CLI surface

_Source: CONVENTIONS.md per-command conformance table + SUITE.md._

## Global flags

- `--json` — machine mode; accepted on all non-interactive commands
- `--pretty` — human-readable rendering
- `--version` — emit `{"tool":"yaams","version":"x.y.z"}`
- `--doctor` — health + conformance check
- `--help` — command help

---

## Core commands

### `yaams query "<text>" [OPTIONS]`
Semantic + keyword search over Tier 1 + optional Tier 2.
- `--tier raw|ledger|both` (default: both)
- `--source <src>` — filter by ingest source
- `--limit <n>` — max results
- `--json`, `--pretty`
- class: data; exit: 0, 1, 2, 4

### `yaams ingest [--source <src>] [--json]`
Ingest all configured sources (or one with `--source`).
With `--json`: streams NDJSON progress lines, terminal result envelope.
- class: action; exit: 0, 1, 2, 3, 5

### `yaams stats [--json]`
Counts, sizes, per-source last-ingest timestamps.
- class: data; exit: 0, 1

### `yaams signals [--json]`
List configured signal sources with enabled/disabled state.
- class: data; exit: 0, 1

### `yaams feedback --id <id> --verdict <hit|miss|correction> [--correction "<text>"]`
Log retrieval feedback for query improvement.
- class: action; exit: 0, 1, 4

### `yaams consolidate [--json]`
De-duplicate rows and re-embed stale entries.
- class: action; exit: 0, 1, 2

### `yaams reset-db --yes [--json]`
Drop and recreate the database. Requires `--yes`.
- class: action + destructive; exit: 0, 1

### `yaams setup [--json]`
First-time setup wizard (NLP models, source config, embedding check).
- class: action; exit: 0, 1, 2

### `yaams init-db [--json]`
Create or migrate the SQLite schema without ingesting.
- class: action; exit: 0, 1

---

## Promote subcommands

### `yaams promote generate [--json]`
Run the candidate-generation pipeline over recent ingest.
- class: action; exit: 0, 1, 2

### `yaams promote list [--json]`
List existing promotion candidates with scores.
- class: data; exit: 0, 1

### `yaams promote review`
Interactively review candidates. TTY required.
- class: interactive; rejects `--json`; exit: 0, 1

---

## Entities subcommands

### `yaams entities list [--json]`
List all managed entities.
- class: data; exit: 0, 1

### `yaams entities add --name <n> [--type <t>] [--json]`
Add a managed entity.
- class: action; exit: 0, 1

### `yaams entities remove --name <n> --yes [--json]`
Remove a managed entity.
- class: action + destructive; exit: 0, 1

### `yaams entities discover [--json]`
Auto-discover entities from recent ingest.
- class: action; exit: 0, 1, 2

### `yaams entities denied [--json]`
List entities on the deny list.
- class: data; exit: 0, 1

### `yaams entities manage`
Interactive entity management TUI. Rejects `--json`.
- class: interactive; exit: 0, 1

---

## Enrich subcommands

### `yaams enrich retag [--json]`
Re-run entity-tagging pass across the store.
- class: action; exit: 0, 1, 2

---

## Doctor / version

### `yaams --doctor [--json]`
```json
{
  "tool": "yaams",
  "version": "0.2.0",
  "config_path": "/Users/cj/.config/hugr/yaams/config.yaml",
  "data_path": "/Users/cj/yaams/data.db",
  "models": {"embedding": "BAAI/bge-m3", "available": true},
  "findings": [{"id":"...", "severity":"error|warning|info", "message":"...", "hint":"..."}]
}
```
- exit: 0 ok, 1 user-fixable, 2 transient, 3 auth

### `yaams --version`
```json
{"tool": "yaams", "version": "0.2.0"}
```
