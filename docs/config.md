# Configuration

`hugr` keeps its own master config small and points at the per-tool
configs you (or the wizard) already have.

## File layout

```
$XDG_CONFIG_HOME/                 (default: ~/.config)
├── hugr/
│   └── config.yaml               # master config
├── yaams/
│   └── config.yaml               # adopted in place; hugr never edits this
├── cognitive-ledger/
│   └── config.yaml               # adopted in place
└── owa-piggy/
    └── profiles.conf             # adopted in place

$HUGR_HOME/                       (default: ~/.local/share/hugr)
├── cache/
│   └── detection.json            # source-detection cache (TTL 24h)
├── sessions/
│   └── <id>/                     # see sessions.md
└── state/                        # if hugr sync init lives here too (default location)
```

## Master config

`hugr init` writes `$XDG_CONFIG_HOME/hugr/config.yaml`. The file is
flat YAML; you can edit it freely.

```yaml
version: 1
data_root: ~/.local/share/hugr

# Pointers to the per-tool configs. hugr resolves these at runtime
# and passes them through as env vars (e.g. YAAMS_CONFIG) when it
# spawns subprocesses.
yaams_config: ~/.config/yaams/config.yaml
ledger_config: ~/.config/cognitive-ledger/config.yaml
owa_piggy_config: ~/.config/owa-piggy/profiles.conf

# Optional. If set, owa-piggy verbs invoked through hugr default to
# this profile. Selectable per-invocation via OWA_PROFILE=...
# default_owa_profile: personal
```

What it does NOT contain:

- Anything that already lives in the per-tool configs (ingest sources,
  ledger roots, OWA tokens, etc.).
- Anything sensitive. The pointers are paths; the secrets stay inside
  the tool configs and the OS keychain.

## "Adopted in place" - the contract

`hugr init` searches for tool configs at the canonical paths above
(and a few legacy fallbacks). If it finds one, it records the path
in the master config and **moves on**:

- No reading of the file beyond detecting its existence.
- No merging, rewriting, or moving.
- No `--force` overrides this for existing tool configs. `--force`
  only governs whether `hugr init` overwrites its own master config.

If a tool config is missing, hugr can create one (with your consent
for yaams), but it never touches a file that already exists.

See [init.md](init.md) for the full contract.

## Env vars

Listed by category.

### Paths

| Var | Default | Meaning |
| --- | --- | --- |
| `XDG_CONFIG_HOME` | `~/.config` | Where master + per-tool configs live. |
| `HUGR_HOME` | `~/.local/share/hugr` | hugr's data root: caches, sessions, optional state repo clone. |
| `HUGR_CONFIG` | (unset) | Override the master config path entirely. |
| `HUGR_STATE_DIR` | `$HUGR_HOME/state` | Where `hugr sync init` clones the state repo. |

### Per-tool config overrides

These are honored natively by the underlying tools; hugr forwards
them via env when spawning subprocesses:

| Var | Used by |
| --- | --- |
| `YAAMS_CONFIG` | `yaams` and every `hugr` verb that routes to yaams. |
| `LEDGER_CONFIG` | `ledger`, `ledger-obsidian`, `sheep`. |
| `OWA_PIGGY_CONFIG` | `owa-piggy`. |
| `OWA_PROFILE` | All `owa-*` tools - selects an owa-piggy profile per invocation. |

If you set `YAAMS_CONFIG` (or `HUGR_CONFIG`) in the environment,
hugr's first-run guard treats it as "user has a configured suite" and
skips the "Run: hugr init" hint. Useful for one-off agent runs.

### Sessions

| Var | Default | Meaning |
| --- | --- | --- |
| `HUGR_SESSION` | (unset) | Session id for `recall` / `inbox` writebacks. See [sessions.md](sessions.md). |

### Sync

| Var | Default | Meaning |
| --- | --- | --- |
| `HUGR_DEVICE_ID` | `$USER@$HOSTNAME` (sanitised) | Per-device id used as the recipient label and the `devices/<id>/` folder name. |
| `HUGR_STATE_DIR` | `$HUGR_HOME/state` | Local state repo clone. |

### Web / server

| Var | Default | Meaning |
| --- | --- | --- |
| `HUGR_WEB_TOKEN` | (unset) | Required when starting `hugr web --public`. |
| `HUGR_WEB_BIND` | (unset) | Optional override for the web bind addr. |
| `HUGR_AUTH_PROXY` | (unset) | `cloudflare` / `tailscale`. Required for non-loopback `hugr server` without `--insecure`. |

## Detection cache

`hugr sources` probes the local machine for adapters (iMessage, Mail,
Signal, GitHub, Obsidian, ledger root, owa-piggy profiles, ...). The
result is cached at `$HUGR_HOME/cache/detection.json` for 24 hours.

```bash
hugr doctor --pretty       # uses the cache when fresh
hugr doctor --rescan       # busts the cache and re-probes
```

The cache structure (TTL is configurable in the file):

```json
{
  "generated_at": "2026-05-25T12:00:00Z",
  "ttl_seconds": 86400,
  "report": { ... hugr.sources output ... }
}
```

## First-run guard

Subcommands that depend on the yaams DB (`recall`, `find`, `inbox`,
`remember`, `query`, `ingest`, `promote review`, `promote generate`)
refuse to run when no master config exists. They exit code 4 with:

```
x hugr: no hugr config at /Users/.../config.yaml.
    Fix:  hugr init
```

Bypass paths (any one of these turns the guard off):

- Run `hugr init --quick` (recommended).
- Pass `--config /path/to/yaams.yaml` to the verb.
- Set `YAAMS_CONFIG` or `HUGR_CONFIG` in the environment.

## Multiple owa-piggy profiles

`owa-piggy` supports profiles (e.g. work / personal / volunteer).
`hugr` does not bake any default profile - selection is per
invocation:

```bash
OWA_PROFILE=personal hugr mail list --unread
OWA_PROFILE=work hugr cal events --today
```

`hugr doctor` shows a stanza for each profile with its token-expiry
state (the "M365 profiles" section). Set `default_owa_profile` in the
master config to make one of them the implicit default.

## Where each config lives by default

| Tool | macOS | Linux |
| --- | --- | --- |
| hugr master | `~/.config/hugr/config.yaml` | `~/.config/hugr/config.yaml` |
| yaams | `~/.config/yaams/config.yaml` | `~/.config/yaams/config.yaml` |
| cognitive-ledger | `~/.config/cognitive-ledger/config.yaml` | same |
| owa-piggy profiles | `~/.config/owa-piggy/profiles.conf` | same |

`XDG_CONFIG_HOME` is honored when set; in its absence hugr falls back
to `~/.config` on every platform - yes, even on macOS, for parity with
the underlying tools (hugr does not use `~/Library/Application Support`).

## Editing safely

```bash
# Validate after editing the master config:
hugr doctor --json | jq '.findings[] | select(.severity != "info")'

# See where everything resolves on this machine:
hugr doctor --pretty
hugr version --json | jq '.config_paths'
```

If a hand-edit breaks resolution, `hugr doctor --fix --yes` will
offer to rerun `hugr init --quick` and rebuild the master config from
the current detection state.
