# Installation

`hugr` is one binary that wraps four underlying tools. You can install
everything via Homebrew (one command), or install each piece via pipx
when you want finer control.

## Homebrew (recommended)

```bash
brew install damsleth/tap/hugr
```

The formula pulls the whole suite via dependencies: `yaams`,
`cognitive-ledger`, `owa-piggy`, `owa-tools`, plus the system deps
`age`, `git`, and `sqlite3` for the sync and DB paths.

## pipx (Python install)

```bash
pipx install hugr-cli
```

Or install with every optional surface:

```bash
pipx install "hugr-cli[tui,web,server,mcp]"
# shorthand:
pipx install "hugr-cli[all]"
```

Individual extras:

| Extra | What it adds |
| --- | --- |
| `tui` | `hugr tui` (Textual terminal UI) |
| `web` | `hugr web` (FastAPI web UI on `127.0.0.1:7777`) |
| `server` | `hugr server` (same web app, deploy-friendly) |
| `mcp` | `hugr mcp --stdio` / `hugr mcp --http` (MCP transports) |
| `all` | shortcut for the four above |

`hugr` itself depends only on `click`. Everything else is optional.
The binary name installed on `$PATH` is `hugr`.

You will still need the four underlying tools (`yaams`, `ledger`,
`owa-piggy`, `owa-*`) on `PATH` for the corresponding verbs to work.
The Homebrew tap pulls them in automatically; with pipx, install each
via `pipx install` from its own GitHub repo.

## First-time setup

The fastest path is the non-interactive `--quick` wizard:

```bash
hugr init --quick
```

What it does:

1. Probes for iMessage, Apple Mail, Signal, GitHub, owa-piggy,
   Obsidian, and an existing cognitive-ledger.
2. Adopts any existing tool configs it finds **in place** (it never
   moves, copies, or rewrites them - see [init.md](init.md)).
3. Writes the master config at `$XDG_CONFIG_HOME/hugr/config.toml`.
4. Runs `yaams setup`, `yaams init-db`, and `yaams ingest --dry-run`
   to validate the new bootstrap when `yaams` is on PATH.
5. Skips embedding-model downloads unless you pass `--with-models`.

The wizard finishes in well under 30s on a laptop that already has
iMessage / GitHub / Obsidian present. Add `--json` for a machine
envelope; add `--with-models` to also download embedding models in
the same run.

Prefer an interactive wizard? Drop `--quick`:

```bash
hugr init
```

This is the prompt-driven version - same probing, same adoption
contract, but pauses for confirmation at each step.

## Confirming the install

```bash
hugr hello              # one-screen tour of the verbs
hugr version            # hugr + each observed tool version
hugr doctor             # cross-tool health check
hugr doctor --fix --yes # apply bounded self-healing fixes
hugr list               # list all binaries under the umbrella
```

`hugr doctor` is the source of truth - if it reports green, the suite
is wired correctly and ready to ingest.

## Add embedding models (optional)

The first time `hugr ingest` runs without local embedding models, it
asks before downloading (~2 GB). To stage them up front during the
quick bootstrap:

```bash
hugr init --quick --with-models
```

You can always re-trigger the download with `hugr ingest` later.

## Upgrades

Homebrew handles upgrades when each underlying tool ships a new
release:

```bash
brew upgrade hugr
```

pipx upgrades each component independently:

```bash
pipx upgrade hugr-cli
pipx upgrade yaams
pipx upgrade cognitive-ledger
pipx upgrade owa-piggy
pipx upgrade owa-tools
```

`hugr version` lists every observed component version side-by-side,
which is the easiest way to spot drift.

## Uninstall

```bash
brew uninstall damsleth/tap/hugr   # plus each component if you want them gone too
# or
pipx uninstall hugr-cli
```

The master config at `~/.config/hugr/config.toml` and the data root
at `~/.local/share/hugr/` are not removed automatically - delete them
by hand if you want a clean wipe. The per-tool configs (yaams, ledger,
owa-piggy) live under their own XDG paths and outlive hugr.
