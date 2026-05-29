---
name: hugr-suite-owa-tools
description: Use when an agent calls calendar, mail, Graph, OneDrive, scheduling, or people-lookup verbs, or needs to understand the owa-tools --agent envelope and JSON-by-default contract.
metadata:
  suite_version: "0d1c0f6"
---

# owa-tools — M365 read/write CLIs

owa-tools is the Microsoft 365 read/write surface of the hugr suite.
Eight binaries (`owa-cal`, `owa-mail`, `owa-graph`, `owa-doctor`,
`owa-people`, `owa-sched`, `owa-drive`, plus the `owa` dispatcher)
cover calendar events, mail, Microsoft Graph API calls, OneDrive,
scheduling, and directory lookups — all JSON-by-default.

## Architecture summary

- owa-tools is **JSON-by-default** on every command. No `--json` flag
  needed to get machine output; the flag is accepted on `--doctor`
  surfaces only.
- The **`--agent` envelope** (or `OWA_AGENT=1`) is owa-tools' machine-mode
  contract: `{"_owa":{suite,tool,version,schema_version,command,profile},"data":<result>}`.
  This is a deliberate signed-off divergence from the hugr action envelope
  (`{tool,ok,duration_ms,...}`). Use `--agent` when calling owa-tools
  from automation that needs the versioned metadata wrapper.
- Each binary borrows access tokens from **owa-piggy** over a local
  socket. The tools never import owa-piggy and never see refresh tokens.
- **Exit code taxonomy**: owa-tools uses `0/2/10-15/20` on command
  paths (not hugr's 0–5). Mapping: 2=transient, 10=auth-expired,
  11=scope-missing, 12=not-found, 13=rate-limited, 14=conflict,
  15=bad-request, 20=internal. The hugr 0-5 set applies only to
  `--doctor` output.
- **Destructive gating**: `owa_core/tty.py:require_confirm_or_tty()`
  raises `UsageError` when neither `--confirm`/`--yes` nor an
  interactive TTY is present. Wired into `delete` and `rm` commands.
- owa-tools never imports yaams, cognitive-ledger, or hugr at runtime.

## Public surface

Binaries: `owa`, `owa-cal`, `owa-mail`, `owa-graph`, `owa-doctor`,
          `owa-people`, `owa-sched`, `owa-drive`

Config: `$XDG_CONFIG_HOME/hugr/owa/config.yaml` (env: `OWA_CONFIG`)
All eight binaries share one config.

### `owa` — dispatcher

`owa <tool> <args>` routes to `owa-<tool>` binary verbatim.
`owa --version` and `owa --doctor` are implemented natively.

### `owa-cal` commands

| command | class | description |
|---|---|---|
| `owa-cal events [--today\|--week\|--from X --to Y]` | data | List calendar events |
| `owa-cal events-webcal` | data | WebCal feed document |
| `owa-cal create --title T [--when W] [--duration N]` | action | Create event |
| `owa-cal update --id I [OPTIONS]` | action | Update event |
| `owa-cal delete --id I --confirm` | action + destructive | Delete event |
| `owa-cal categories` | data | List categories |
| `owa-cal profiles` | data | List auth profiles |
| `owa-cal config` | data | Resolved config |
| `owa-cal refresh` | action | Force token refresh |

### `owa-mail` commands

| command | class | description |
|---|---|---|
| `owa-mail messages [--folder F] [--unread] [--limit N]` | data | List messages |
| `owa-mail show --id I` | data | Show full message |
| `owa-mail send --to A --subject S --body B` | action | Send message |
| `owa-mail reply --id I --body B` | action | Reply to message |
| `owa-mail reply-all --id I --body B` | action | Reply-all |
| `owa-mail forward --id I --to A` | action | Forward |
| `owa-mail delete --id I --confirm` | action + destructive | Delete |
| `owa-mail move --id I --folder F` | action | Move to folder |
| `owa-mail mark --id I --read\|--unread` | action | Mark read/unread |
| `owa-mail folders` | data | List mail folders |
| `owa-mail config` | data | Resolved config |
| `owa-mail refresh` | action | Force token refresh |

### `owa-graph` commands

| command | class | description |
|---|---|---|
| `owa-graph get <path>` | data | GET Microsoft Graph endpoint |
| `owa-graph post <path> --body B` | action | POST |
| `owa-graph put <path> --body B` | action | PUT |
| `owa-graph patch <path> --body B` | action | PATCH |
| `owa-graph delete <path> --confirm` | action + destructive | DELETE |
| `owa-graph batch --ndjson` | action | Batch request (NDJSON per sub-response) |
| `owa-graph config` | data | Resolved config |
| `owa-graph refresh` | action | Force token refresh |

### `owa-people` commands

| command | class | description |
|---|---|---|
| `owa-people find "<query>"` | data | Search directory |
| `owa-people directory` | data | Full directory list |
| `owa-people show --id I\|--email E` | data | Show one person |
| `owa-people me` | data | Caller's own profile |
| `owa-people contacts` | data | Personal contacts |
| `owa-people config` | data | Resolved config |
| `owa-people refresh` | action | Force token refresh |

### `owa-sched` commands

| command | class | description |
|---|---|---|
| `owa-sched availability --who <email> [--from X --to Y]` | data | Free/busy for attendees |
| `owa-sched find-time --who <email> --duration N` | data | Find meeting slot |
| `owa-sched config` | data | Resolved config |
| `owa-sched refresh` | action | Force token refresh |

### `owa-drive` commands

| command | class | description |
|---|---|---|
| `owa-drive ls [<path>]` | data | List OneDrive entries |
| `owa-drive show <path>` | data | Show entry metadata |
| `owa-drive get <path> --out <file>` | action | Download file |
| `owa-drive put <file> --to <path>` | action | Upload file |
| `owa-drive rm <path> --confirm` | action + destructive | Delete |
| `owa-drive config` | data | Resolved config |
| `owa-drive refresh` | action | Force token refresh |

### `owa-doctor`

`owa-doctor` is the aggregated health check across all owa-tools
binaries. Its JSON payload matches the CONVENTIONS.md doctor schema;
exit codes follow the hugr 0-5 taxonomy (exception to the command-path
0/2/10-20 taxonomy).

## Code location

Repo: `~/code/owa-tools/`

| file | purpose |
|---|---|
| `owa_core/modes.py` | `run_with_output_modes()` — applies `--agent` envelope |
| `owa_core/errors.py` | `ExitCode` enum (0/2/10-20 taxonomy) |
| `owa_core/tty.py` | `require_confirm_or_tty()` — destructive gating |
| `owa_core/secrets.py` | `redact()` — body/content/token scrubbing |
| `owa_core/conventions.py` | vendored CONVENTIONS.md helpers (doctor surface) |
| `owa_cal/`, `owa_mail/`, etc. | per-binary packages |

## Key conventions

- **JSON-by-default**: no `--json` flag needed. Every command writes
  JSON to stdout whether or not stdout is a TTY.
- **`--agent` envelope**: `{"_owa":{...},"data":<result>}`.
  Use when calling from automation that needs the metadata wrapper.
  `OWA_AGENT=1` applies the same envelope without a per-call flag.
- **Reserved-key (`ok`) safety**: the `--agent` wrapper nests the raw
  payload under `data`, so a Graph response containing `ok` never
  collides with the hugr discriminator.
- **No `--pretty` on action commands**: `--pretty` is wired on data
  commands only (`messages`, `show`, `folders`, `events`, etc.).
- **Destructive gating**: `--confirm` (or interactive TTY) is required
  for `delete`, `rm`. Non-interactive refusal is enforced, not advisory.
- **Token flow**: each binary calls `owa-piggy token --audience <aud>`
  at startup to borrow an access token. If owa-piggy is unavailable,
  exit 10 (auth-expired).
- **Redaction**: `owa_core.secrets.redact()` scrubs JWT shapes,
  Bearer headers, and mail/event body fields from all stderr output.

## Cross-component touchpoints

| component | how owa-tools talks to it |
|---|---|
| owa-piggy | shells out to `owa-piggy token --audience <aud>` for access tokens |
| hugr | hugr calls owa-tools via subprocess; owa-tools never calls hugr |
| YAAMS | no direct dependency |

## Pointers

- Full verb table with all flags: `references/cli-surface.md`
- CONVENTIONS.md slices + owa-tools divergences: `references/conventions.md`
- Common failures (token expiry, destructive gating, Graph errors): `references/troubleshooting.md`
- Suite hub and router: `[[hugr-suite-hugr]]`
- Auth broker (token source): `[[hugr-suite-owa-piggy]]`
