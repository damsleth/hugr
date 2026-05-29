# cognitive-ledger CLI surface

_Source: CONVENTIONS.md conformance table + SUITE.md._

## `ledger` global flags

- `--json` — machine mode (required on all non-interactive commands)
- `--pretty` — human rendering
- `--version` — `{"tool":"ledger","version":"x.y.z"}`
- `--doctor` — health check
- `--help` — command help

---

## `ledger` commands

### `ledger init [--json]`
Bootstrap a new ledger: create notes directory, write default config.
- class: action; exit: 0, 1

### `ledger paths [--json]`
Show resolved config path, notes directory, embedding index path.
- class: data; exit: 0, 1

### `ledger query "<text>" [OPTIONS]`
Semantic search over atomic notes.
- `--type <t>` — filter by note type (fact, preference, goal, open-loop, concept, identity)
- `--limit <n>` — max results
- `--json`, `--pretty`
- class: data; exit: 0, 1, 4

### `ledger loops [--json]`
List all open loops with their last-updated timestamp.
- class: data; exit: 0, 1

### `ledger notes [--type <t>] [--json]`
List notes, optionally filtered by type.
- class: data; exit: 0, 1

### `ledger discover [--json]`
Find candidate cross-links between notes based on entity co-occurrence.
- class: data; exit: 0, 1

### `ledger context [--format boot|identity|json] [--profile <name>]`
Emit boot context for agent initialization.
- `--format boot` — markdown boot document (default)
- `--format identity` — identity-only subset
- `--format json` — machine-readable JSON
- class: data; exit: 0, 1
- **Note**: hugr router rewrites `hugr ledger context` to
  `ledger context --format json`; do not add `--json` on top.

### `ledger context build [--json]`
Build curated context files from the notes tree.
- class: action; exit: 0, 1

### `ledger context profiles [--json]`
List available context profiles.
- class: data; exit: 0, 1

---

## `ledger embed` subcommands

### `ledger embed build [--json]`
Build or update the embedding index over all notes.
Streams NDJSON progress with `--json`.
- class: action; exit: 0, 1, 2

### `ledger embed status [--json]`
Coverage stats: how many notes are embedded vs. stale.
- class: data; exit: 0, 1

### `ledger embed clean --yes [--json]`
Wipe the embedding index. Requires `--yes`.
- class: action + destructive; exit: 0, 1

---

## `ledger eval`

### `ledger eval [--json]`
Run the eval suite against the notes directory.
- class: action; exit: 0, 1

---

## `ledger ingest [--source <src>] [--json]`
Ingest external sources into the ledger. Streams NDJSON with `--json`.
- class: action; exit: 0, 1, 2, 5

---

## `sheep` commands

### `sheep status [--json]`
Sleep audit: per-note health overview (stale links, missing fields).
- class: data; exit: 0, 1
- Known: wraps human lines rather than structured fields (open audit item)

### `sheep lint [--json]`
Lint all notes for schema violations and broken links.
- class: data; exit: 0, 1
- Known: same structured-output gap as status

### `sheep sleep [--json]`
Daily sleep checklist: which notes need review before end of day.
- class: data; exit: 0, 1

### `sheep index [--json]`
Re-index notes for fast lookup. Returns proper envelope.
- class: action; exit: 0, 1, 2

### `sheep sync [--json]`
Diff the notes directory against remote/Obsidian state.
- class: data; exit: 0, 1

### `sheep --doctor [--json]`
Health check. exit: 0, 1, 2

### `sheep --version`
`{"tool":"sheep","version":"x.y.z"}`

---

## `ledger-obsidian` commands

### `ledger-obsidian sync [--json]`
Two-way sync with the configured Obsidian vault.
- class: action; exit: 0, 1, 2

### `ledger-obsidian --doctor [--json]`
Health check. exit: 0, 1, 2, 3

### `ledger-obsidian --version`
`{"tool":"ledger-obsidian","version":"x.y.z"}`

---

## Exit codes

| code | meaning |
|---|---|
| 0 | success |
| 1 | user error |
| 2 | transient / retryable |
| 3 | auth (ledger-obsidian only) |
| 4 | not found |
| 5 | partial success |
