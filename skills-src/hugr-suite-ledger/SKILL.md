---
name: hugr-suite-ledger
description: Use when an agent works with promoted notes, open loops, briefings, the sleep/maintenance cycle, or the cognitive-ledger's two-CLI shape (ledger + sheep).
metadata:
  suite_version: "0d1c0f6"
---

# cognitive-ledger — Tier 2 curated atomic notes engine

The cognitive ledger is the permanent keep-forever layer of the hugr
suite. Items are promoted into it from YAAMS (Tier 1) by explicit human
or agent review, then maintained as atomic markdown notes with
frontmatter. The ledger is queried by hugr fused verbs as a Tier 2
source that outranks raw YAAMS results.

## Architecture summary

- The ledger is **Tier 2** in the two-tier memory model: curated,
  low-volume, high-signal. Promotion is one-way: YAAMS → ledger.
- Notes are typed atomic markdown files in a private directory tree
  (the "notes directory"). Note types: `fact`, `preference`, `goal`,
  `open-loop`, `concept`, `identity`. Each has a YAML frontmatter block.
- **Two binaries**: `ledger` (core engine: query, loops, context, embed)
  and `sheep` (Electric Sheep maintenance: sleep audit, lint, index,
  sync). A third binary `ledger-obsidian` syncs the notes directory
  with an Obsidian vault.
- The ledger never imports yaams, owa-piggy, or owa-tools at runtime.
  hugr calls `ledger` via subprocess; `ledger` exposes itself as the
  `tier2_ledger` adapter to YAAMS by path (read-only directory access).
- Context profiles (`ledger context`) let the ledger emit a
  curated boot-context document for agents, formatted as
  `--format boot|identity|json`.

## Public surface

Binaries: `ledger`, `sheep`, `ledger-obsidian`

Config: `$XDG_CONFIG_HOME/hugr/ledger/config.yaml` (env: `LEDGER_CONFIG`)
Notes dir: configured in `config.yaml` (`notes_dir`)

### `ledger` commands

| command | class | description |
|---|---|---|
| `ledger init` | action | Bootstrap a new ledger (create notes dir, config) |
| `ledger paths [--json]` | data | Show resolved config and data paths |
| `ledger query "<text>" [--json]` | data | Semantic search over notes |
| `ledger loops [--json]` | data | List all open loops |
| `ledger notes [--type <t>] [--json]` | data | List notes by type |
| `ledger discover [--json]` | data | Auto-discover linkable concepts |
| `ledger context [--format boot|identity|json]` | data | Emit boot context |
| `ledger context build` | action | Build curated context files |
| `ledger context profiles` | data | List context profiles |
| `ledger embed build` | action | Build / update embedding index |
| `ledger embed status [--json]` | data | Embedding coverage stats |
| `ledger embed clean --yes` | action + destructive | Wipe embedding index |
| `ledger eval` | action | Run eval suite against the notes |
| `ledger ingest [--json]` | action | Ingest external sources into the ledger |
| `ledger --doctor [--json]` | data | Health check |
| `ledger --version` | data | `{"tool":"ledger","version":"x.y.z"}` |

### `sheep` commands (Electric Sheep maintenance)

| command | class | description |
|---|---|---|
| `sheep status [--json]` | data | Sleep audit: note health overview |
| `sheep lint [--json]` | data | Lint all notes for schema / link issues |
| `sheep index [--json]` | action | Re-index notes for fast lookup |
| `sheep sleep [--json]` | data | Daily sleep checklist |
| `sheep sync [--json]` | data | Diff the notes dir against remote |
| `sheep --doctor [--json]` | data | Health check |
| `sheep --version` | data | `{"tool":"sheep","version":"x.y.z"}` |

Note: `sheep status`, `sheep lint`, and `sheep sleep` have a known
open audit item — they wrap human-readable lines rather than emitting
structured fields (minor, Phase 2b/2c target). `sheep index` and
`sheep sync` already return proper envelopes.

### `ledger-obsidian` commands

| command | class | description |
|---|---|---|
| `ledger-obsidian sync [--json]` | action | Two-way sync with Obsidian vault |
| `ledger-obsidian --doctor [--json]` | data | Health check |
| `ledger-obsidian --version` | data | version |

## Code location

Repo: `~/code/cognitive-ledger/`

| file | purpose |
|---|---|
| `ledger/cli/main.py` | `ledger` CLI entry point |
| `sheep/cli/main.py` | `sheep` CLI entry point |
| `ledger/query.py` | semantic search over notes |
| `ledger/context.py` | boot-context builder + profiles |
| `ledger/embed/` | embedding pipeline |
| `ledger/notes/` | note type schemas, frontmatter helpers |
| `ledger/conventions.py` | vendored CONVENTIONS.md helpers |

## Key conventions

- The hugr router sends `ledger context` as `ledger context --format json`
  (not `--json`), because the ledger's `context` command uses
  `--format boot|identity|json` instead of the standard `--json` flag.
  All other ledger commands use standard `--json`.
- `ledger embed build` and `ledger ingest` are action-class and stream
  NDJSON progress with `--json`.
- `ledger embed clean` requires `--yes` (destructive modifier).
- Exit codes: 0 ok, 1 user error, 2 transient; auth (3) applies only
  if external sources require it.
- `sheep` reads the same ledger config tree as `ledger` (both accept
  `LEDGER_CONFIG`).

## Cross-component touchpoints

| component | how ledger talks to it |
|---|---|
| YAAMS | YAAMS reads the notes directory as `tier2_ledger`; ledger itself doesn't call YAAMS |
| hugr | hugr calls `ledger` via subprocess; ledger never calls hugr |
| owa-piggy | no direct dependency; Obsidian sync may use local token if configured |

## Pointers

- Full verb table: `references/cli-surface.md`
- CONVENTIONS.md slices relevant to ledger: `references/conventions.md`
- Common failure modes: `references/troubleshooting.md`
- Suite hub and router: `[[hugr-suite-hugr]]`
- Tier 1 raw store (promotion source): `[[hugr-suite-yaams]]`
