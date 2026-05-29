---
name: hugr-suite-owa-piggy
description: Use when an agent debugs M365 auth, token expiry, profile setup, FOCI quirks, or needs to understand how owa-tools borrows tokens from owa-piggy.
metadata:
  suite_version: "0d1c0f6"
---

# owa-piggy — M365 auth broker

owa-piggy is the Microsoft 365 authentication broker for the hugr suite.
It turns an existing Outlook Web session into reusable access tokens
stored in the OS keychain and serves them over a local socket to
owa-tools and YAAMS. It is the only component in the suite that holds
refresh tokens or touches the OWA session directly.

## Architecture summary

- owa-piggy is the **only auth touchpoint** in the suite. owa-tools,
  YAAMS, and hugr never see refresh tokens; they borrow access tokens
  from owa-piggy over a local socket.
- Tokens live in the **OS keychain** (macOS Keychain / Linux Secret
  Service), not on disk as plaintext files.
- owa-piggy uses **FOCI** (Family of Client IDs) to acquire tokens for
  multiple M365 audiences (mail, calendar, Teams, Graph) from one
  browser session, without requiring an app registration.
- Multiple **profiles** (e.g. `work`, `personal`, named aliases) each
  hold their own token bundle. `owa-piggy profiles set-default` selects
  the active profile; most commands accept `--profile <name>`.
- owa-piggy is JSON-by-default on all data and action commands.
  It never injects `--json` when called by hugr (`json_policy="native"`).

## Public surface

Binary: `owa-piggy`

Config: `$XDG_CONFIG_HOME/hugr/owa-piggy/config.yaml` (env: `OWA_PIGGY_CONFIG`)
Tokens: OS keychain (macOS Keychain or Linux Secret Service)

### Commands

| command | class | description |
|---|---|---|
| `owa-piggy token [--audience <aud>] [--profile <name>]` | data | Print current access token |
| `owa-piggy status [--profile <name>]` | data | Auth status for profile(s) |
| `owa-piggy remaining [--profile <name>]` | data | Minutes left on current token |
| `owa-piggy debug [--profile <name>]` | data | Full diagnostics (token, profile, sidecar) |
| `owa-piggy decode [--profile <name>]` | data | Decode JWT header + payload |
| `owa-piggy reseed [--profile <name>]` | action | Refresh expired tokens from Edge sidecar |
| `owa-piggy setup` | interactive | First-time M365 auth setup (TTY required) |
| `owa-piggy profiles list` | data | List profiles |
| `owa-piggy profiles set-default --name <n>` | action | Set default profile |
| `owa-piggy profiles delete --name <n> --yes` | action + destructive | Delete a profile |
| `owa-piggy version` | data | Version |
| `owa-piggy --doctor` | data | Health check |
| `owa-piggy --version` | data | Version |

### `--audience` values (common)

| audience | M365 resource |
|---|---|
| `mail` | Exchange / Outlook mail |
| `calendar` | Exchange calendar |
| `teams` | Microsoft Teams |
| `graph` | Microsoft Graph API |
| `onedrive` | OneDrive / SharePoint |

### Key env vars

| var | effect |
|---|---|
| `OWA_PIGGY_CONFIG` | config file path |
| `OWA_PROFILE` | default profile override |

## Code location

Repo: `~/code/owa-piggy/`

| file | purpose |
|---|---|
| `owa_piggy/cli/main.py` | Click CLI entry point |
| `owa_piggy/token.py` | token acquisition, FOCI flow |
| `owa_piggy/keychain.py` | OS keychain abstraction |
| `owa_piggy/profiles.py` | profile model |
| `owa_piggy/sidecar.py` | Edge sidecar token reseed |
| `owa_piggy/conventions.py` | vendored CONVENTIONS.md helpers (doctor surface only) |

## Key conventions

- **owa-piggy uses the hugr 0–5 exit code taxonomy on the `--doctor`
  surface.** Command-path exits use the same set (0, 1, 2, 3) because
  owa-piggy's command set is small and the flat taxonomy is sufficient.
- `owa-piggy setup` is interactive-class; it rejects `--json` per
  CONVENTIONS.md.
- `owa-piggy token` exit 3 means "token expired or unavailable"; run
  `owa-piggy reseed` or `owa-piggy setup`.
- owa-piggy does NOT emit the owa-tools `--agent` envelope; it uses
  the standard hugr action envelope on action commands.
- Tokens are redacted from all stderr output per the CONVENTIONS.md
  redaction contract.

## Cross-component touchpoints

| component | how owa-piggy talks to it |
|---|---|
| owa-tools | owa-tools calls `owa-piggy token --audience <aud>` via subprocess to borrow access tokens |
| YAAMS | YAAMS calls `owa-piggy token` for Teams and calendar adapters |
| hugr | hugr calls owa-piggy via subprocess through the `auth` verb prefix |

owa-piggy never imports any sibling component.

## FOCI quirks

- FOCI token families vary by tenant. If `reseed` fails for one
  audience but not another, the tenant may not include that resource
  in the same family. Use `owa-piggy debug` to inspect the sidecar
  state.
- Tokens expire. `owa-piggy remaining` returns `{"minutes": N}`.
  At N < 5, proactively call `reseed` before a long operation.
- Profile names are case-sensitive in the keychain.

## Pointers

- Full verb table: `references/cli-surface.md`
- CONVENTIONS.md slices relevant to owa-piggy: `references/conventions.md`
- Token lifecycle and FOCI troubleshooting: `references/troubleshooting.md`
- Suite hub and router: `[[hugr-suite-hugr]]`
- M365 read/write CLIs that consume tokens: `[[hugr-suite-owa-tools]]`
