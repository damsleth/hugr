# owa-tools CLI surface

_Source: CONVENTIONS.md conformance table + AUDIT.md._

owa-tools is JSON-by-default. No `--json` needed for machine output.
Use `--agent` (or `OWA_AGENT=1`) for the metadata-wrapped envelope.

## Global flags (all binaries)

- `--version` — `{"tool":"owa-<name>","version":"x.y.z"}`
- `--doctor` — health check
- `--help` — command help
- `--profile <name>` — override active auth profile
- `--agent` — wrap output in `{"_owa":{...},"data":<result>}`

---

## `owa-cal`

### `owa-cal events [OPTIONS]`
- `--today` / `--week` / `--from <iso> --to <iso>`
- `--profile <name>`
- class: data; exit: 0, 2, 10-15

### `owa-cal events-webcal`
- class: data; exit: 0, 2

### `owa-cal create --title T [--when W] [--duration N] [--attendees A,...]`
- class: action; exit: 0, 2, 10-15

### `owa-cal update --id I [--title T] [--when W] [--duration N]`
- class: action; exit: 0, 2, 10-15

### `owa-cal delete --id I --confirm`
- class: action + destructive; `--confirm` required non-interactively
- exit: 0, 2, 10-12, 14

### `owa-cal categories`
- class: data; exit: 0, 2, 10-13

### `owa-cal profiles`
- class: data; exit: 0

### `owa-cal config`
- class: data; exit: 0

### `owa-cal refresh [--profile <name>]`
- class: action; exit: 0, 10

---

## `owa-mail`

### `owa-mail messages [--folder F] [--unread] [--limit N] [--search Q]`
- class: data; exit: 0, 2, 10-13

### `owa-mail show --id I`
- class: data; exit: 0, 2, 10-12

### `owa-mail send --to A [--cc C] --subject S --body B [--attach FILE]`
- class: action; exit: 0, 2, 10-13

### `owa-mail reply --id I --body B`
- class: action; exit: 0, 2, 10-12

### `owa-mail reply-all --id I --body B`
- class: action; exit: 0, 2, 10-12

### `owa-mail forward --id I --to A`
- class: action; exit: 0, 2, 10-12

### `owa-mail delete --id I --confirm`
- class: action + destructive; exit: 0, 2, 10-12

### `owa-mail move --id I --folder F`
- class: action; exit: 0, 2, 10-12

### `owa-mail mark --id I --read | --unread`
- class: action; exit: 0, 2, 10-12

### `owa-mail folders`
- class: data; exit: 0, 2, 10-13

### `owa-mail config` / `owa-mail refresh`
- class: data / action; exit: 0, 10

---

## `owa-graph`

Raw Microsoft Graph API access. Paths are relative to
`https://graph.microsoft.com/v1.0/`.

### `owa-graph get <path> [--select F,F] [--top N]`
- class: data; exit: 0, 2, 10-12

### `owa-graph post <path> --body <json>`
- class: action; exit: 0, 2, 10-14

### `owa-graph put <path> --body <json>`
- class: action; exit: 0, 2, 10-14

### `owa-graph patch <path> --body <json>`
- class: action; exit: 0, 2, 10-14

### `owa-graph delete <path> --confirm`
- class: action + destructive; exit: 0, 2, 10-12

### `owa-graph batch --requests <json> [--ndjson]`
`--ndjson` streams one sub-response per line (NDJSON).
- class: action; exit: 0, 2, 10-13, 20

### `owa-graph config` / `owa-graph refresh`
- class: data / action; exit: 0, 10

---

## `owa-people`

### `owa-people find "<query>" [--limit N]`
- class: data; exit: 0, 2, 10-13

### `owa-people directory [--limit N]`
- class: data; exit: 0, 2, 10-13

### `owa-people show --id I | --email E`
- class: data; exit: 0, 2, 10-12

### `owa-people me`
- class: data; exit: 0, 10

### `owa-people contacts [--limit N]`
- class: data; exit: 0, 2, 10-13

### `owa-people config` / `owa-people refresh`
- class: data / action; exit: 0, 10

---

## `owa-sched`

### `owa-sched availability --who <email>[,<email>] [--from X] [--to Y] [--duration N]`
- class: data; exit: 0, 2, 10-13

### `owa-sched find-time --who <email>[,<email>] --duration N [--from X] [--to Y] [--limit N]`
- class: data; exit: 0, 2, 10-13

### `owa-sched config` / `owa-sched refresh`
- class: data / action; exit: 0, 10

---

## `owa-drive`

### `owa-drive ls [<path>] [--limit N]`
- class: data; exit: 0, 2, 10-12

### `owa-drive show <path>`
- class: data; exit: 0, 2, 10-12

### `owa-drive get <path> --out <local-file>`
- class: action; exit: 0, 2, 10-12

### `owa-drive put <local-file> --to <path>`
- class: action; exit: 0, 2, 10-13

### `owa-drive rm <path> --confirm`
- class: action + destructive; exit: 0, 2, 10-12

### `owa-drive config` / `owa-drive refresh`
- class: data / action; exit: 0, 10

---

## `owa-doctor`

Aggregated health check across all owa-tools binaries.
Uses the hugr 0-5 exit code taxonomy (exception to command-path 0/2/10-20).

```json
{
  "tool": "owa-doctor",
  "version": "0.2.1",
  "siblings": [...],
  "findings": [{"id":"...","severity":"error|warning|info","message":"...","hint":"..."}]
}
```

---

## Exit code summary (command paths)

| code | meaning |
|---|---|
| 0 | success |
| 2 | transient / retryable (network timeout) |
| 10 | auth expired |
| 11 | scope missing |
| 12 | not found |
| 13 | rate limited |
| 14 | conflict |
| 15 | bad request |
| 20 | internal error |

`--doctor` surface uses hugr 0-5: 0 ok, 1 user-fixable, 2 transient, 3 auth.
