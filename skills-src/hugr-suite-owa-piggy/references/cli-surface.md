# owa-piggy CLI surface

_Source: CONVENTIONS.md conformance table._

owa-piggy is JSON-by-default. `--json` is accepted but redundant on
data commands; needed only when asserting machine mode explicitly.

## Global flags

- `--version` — `{"tool":"owa-piggy","version":"x.y.z"}`
- `--doctor` — health check (see schema below)
- `--help` — command help

---

## Token commands

### `owa-piggy token [--audience <aud>] [--profile <name>]`
Print current access token for the given audience.
- class: data
- stdout: `{"token":"<jwt>","audience":"<aud>","expires_at":"<iso>","profile":"<name>"}`
- exit: 0 ok, 1 user error, 3 token expired/unavailable

### `owa-piggy remaining [--profile <name>]`
Minutes remaining on the current access token.
- class: data
- stdout: `{"minutes": N, "profile": "<name>", "expires_at": "<iso>"}`
- exit: 0 ok, 1 user error, 3 unavailable

### `owa-piggy decode [--profile <name>]`
Decode JWT header + payload (does not validate signature).
- class: data
- stdout: `{"header":{...},"payload":{...},"profile":"<name>"}`
- exit: 0 ok, 1 user error, 3 unavailable

---

## Status / diagnostics

### `owa-piggy status [--profile <name>]`
Auth status for one or all profiles.
- class: data
- stdout: `{"profiles":[{"name":"<n>","state":"ok|expired|missing","expires_at":"<iso>"}]}`
- exit: 0 ok, 1 user error, 3 auth issue

### `owa-piggy debug [--profile <name>]`
Full diagnostics: token state, FOCI family, Edge sidecar connectivity.
- class: data
- stdout: raw diagnostics doc (fields vary by version)
- exit: 0 ok, 1 user error, 3 auth issue

---

## Reseed

### `owa-piggy reseed [--profile <name>] [--audience <aud>]`
Refresh expired tokens from the Edge browser sidecar.
- class: action
- stdout: action envelope `{tool,version,command,ok,duration_ms,stats,warnings,error}`
- exit: 0 ok, 1 user error, 2 transient, 3 sidecar unavailable

---

## Setup (interactive)

### `owa-piggy setup [--profile <name>]`
Interactive first-time M365 auth flow. TTY required.
- class: interactive; rejects `--json`
- exit: 0 ok, 1 user error, 3 auth failed

---

## Profiles subcommands

### `owa-piggy profiles list`
List all profiles with name, default flag, and state.
- class: data
- stdout: `[{"name":"<n>","is_default":bool,"state":"ok|expired|missing"}]`
- exit: 0 ok, 1 user error

### `owa-piggy profiles set-default --name <n>`
Set the named profile as default.
- class: action; stdout: action envelope; exit: 0, 1

### `owa-piggy profiles delete --name <n> --yes`
Delete a profile and its keychain entries.
- class: action + destructive; stdout: action envelope; exit: 0, 1

---

## Version / doctor

### `owa-piggy version`
`{"tool":"owa-piggy","version":"x.y.z"}`

### `owa-piggy --doctor`
```json
{
  "tool": "owa-piggy",
  "version": "0.9.0",
  "config_path": "/Users/cj/.config/hugr/owa-piggy/config.yaml",
  "auth": {"ok": true, "profiles": [{"name":"work","state":"ok"}]},
  "findings": []
}
```
exit: 0 ok, 1 user-fixable, 2 transient, 3 auth

---

## Exit codes

| code | meaning |
|---|---|
| 0 | success |
| 1 | user error (bad flag, profile not found) |
| 2 | transient (sidecar timeout, network) |
| 3 | auth (token expired, FOCI failed, keychain unavailable) |
