# hugr init

`hugr init` is the interactive first-run wizard. It probes your machine
for ingest sources, resolves per-tool config paths, and writes the hugr
master config at `$XDG_CONFIG_HOME/hugr/config.yaml`.

## Idempotent by design

Re-running `hugr init` at any time is safe. The wizard re-probes and
re-renders the master config, but prompts you before overwriting an
existing one unless the content is unchanged.

## Existing tool configs are adopted, never modified

If `hugr init` finds a tool config at any of the canonical paths it
searches, it records that path in the master config and moves on. It
does **not** read the file, merge it, rewrite it, or move it.

The three tools and their canonical paths:

| Tool | Canonical path |
| --- | --- |
| yaams | `$XDG_CONFIG_HOME/yaams/config.yaml` |
| cognitive-ledger | `$XDG_CONFIG_HOME/cognitive-ledger/config.yaml` |
| owa-piggy | `$XDG_CONFIG_HOME/owa-piggy/profiles.conf` |

The only file hugr ever writes during `init` is:
1. The master config (`$XDG_CONFIG_HOME/hugr/config.yaml`).
2. A new yaams config at the canonical location - but **only** if no
   yaams config exists yet and you confirm the prompt.

## What hugr init does NOT do

- It does not move, copy, or rename any existing config file.
- It does not pick a default owa-piggy profile. Profile selection is
  per-invocation via `OWA_PROFILE=...` or per-tool flags.
- It does not download embedding models (that happens on first ingest,
  with a confirmation prompt).
- It does not run any downstream tool commands unless it successfully
  resolved a yaams config (in which case it runs `yaams setup`,
  `yaams init-db`, and `yaams ingest --dry-run` to validate the setup).

## The master config

After `hugr init` the master config is a flat YAML file with pointers
to per-tool configs:

```yaml
version: 1
data_root: ~/.local/share/hugr
yaams_config: ~/.config/yaams/config.yaml
ledger_config: ~/.config/cognitive-ledger/config.yaml
owa_piggy_config: ~/.config/owa-piggy/profiles.conf
# default_owa_profile:  # optional: set to your preferred owa-piggy profile alias
```

Edit this file freely. `hugr init` overwrites it only when you confirm,
and only after comparing the new content to the existing file.

## Checking the result

```bash
hugr doctor          # human-readable health check including M365 profiles
hugr doctor --json   # machine-readable form; includes m365_profiles[]
```
