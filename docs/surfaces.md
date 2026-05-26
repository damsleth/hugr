# Surfaces

`hugr` exposes the same `hugr.api` Python module through several
surfaces (`hugr server` is the web surface in deploy mode):

| Surface | Binary | Best for |
| --- | --- | --- |
| CLI | `hugr` | Day-to-day terminal use. Always installed. |
| TUI | `hugr tui` | Keyboard-driven exploration. Requires `[tui]` extra. |
| Web | `hugr web` | Phone / tablet / laptop browser. Requires `[web]` extra. |
| Server | `hugr server` | VPS / Docker deploy. Requires `[server]` extra. |

They all consume the same backend, so a result you see in the TUI is
byte-equivalent to what `hugr recall ... --json` produces.

## TUI - `hugr tui`

```bash
pipx install "hugr-cli[tui]"
hugr tui
```

Screens:

| Key | Screen | What it does |
| --- | --- | --- |
| `a` | Ask | Default screen. Calls `hugr.api.recall` on Enter. |
| `f` | Find | Pick a kind (person/event/message/note/file), enter a query. |
| `i` | Inbox | Cross-tool triage: unread mail + today + loops + promotions. |
| `d` | Doctor | Doctor report rendered as a tree. |
| `s` | Session | Active session + working set summary. |
| `r` | Remember | Capture a fact. Tick the confirm box before Enter. |
| `q` | quit | |

`r` (refresh) on Inbox / Doctor / Session re-runs the underlying api
call. Each screen runs its api call in a worker thread so the UI
stays responsive.

The TUI uses Textual (https://textual.textualize.io). Snapshot tests
live under `tests/test_tui_*.py`.

## Web UI - `hugr web` and `hugr server`

```bash
pipx install "hugr-cli[web]"
hugr web                       # 127.0.0.1:7777
hugr web --host 0.0.0.0 --public  # requires HUGR_WEB_TOKEN
```

For deploy-friendly invocations, use `hugr server`:

```bash
pipx install "hugr-cli[server]"
hugr server --host 127.0.0.1 --port 7777
```

Non-loopback binds require one of:

- `HUGR_AUTH_PROXY=cloudflare`
- `HUGR_AUTH_PROXY=tailscale`
- `--insecure` (opt-in; noisy on stderr while running)

See [deploy/docs/deploy.md](../deploy/docs/deploy.md) for the full
deployment story.

### Routes

| Method | Path | What it does |
| --- | --- | --- |
| GET | `/` | Ask form / result page |
| GET | `/recall?q=...` | Fused recall (HTML or JSON via `Accept`) |
| POST | `/recall` | Form-driven recall |
| GET | `/inbox` | Inbox view |
| GET | `/find?kind=...&q=...` | Typed search |
| GET | `/doctor` | Doctor report |
| GET | `/session` | Sessions index |
| GET | `/session/{id}` | One session's meta + last_recall + working_set |
| GET | `/send/mail`, `/send/invite`, `/remember` | Mutation forms |
| POST | `/send/mail`, `/send/invite`, `/remember` | Mutation submit (requires `confirm=on`) |
| GET | `/healthz` | `{ok: true, tool: "hugr"}` |
| GET | `/api/recall`, `/api/inbox`, `/api/find`, `/api/doctor`, `/api/session`, `/api/session/{id}` | JSON-only mirrors of the GET pages above |
| GET | `/api/stream/ingest?arg=...` | SSE wrapper around `hugr ingest --json` |

### JSON parity

Every HTML page that wraps an `hugr.api` function returns the same
payload when called with `Accept: application/json` - so this:

```bash
curl -sS 'http://127.0.0.1:7777/find?kind=person&q=nina' -H 'Accept: application/json' | jq
```

is byte-equivalent (modulo whitespace) to:

```bash
hugr find person nina --json | jq
```

### SSE for ingest

Long-running ingests stream NDJSON. The web layer wraps that as
`text/event-stream` so HTMX / EventSource clients can render progress
in place:

```bash
curl -N 'http://127.0.0.1:7777/api/stream/ingest?arg=--source&arg=imessage'
# event-stream frames:
# data: {"type":"progress","done":1,"total":3}
# data: {"type":"progress","done":2,"total":3}
# data: {"type":"result","ok":true,"exit_code":0}
# event: done
# data: {"exit_code": 0}
```

In HTMX:

```html
<div hx-ext="sse"
     sse-connect="/api/stream/ingest?arg=--source&arg=imessage"
     sse-swap="message">
  <p>Ingest progress streams in here.</p>
</div>
```

### Mutation forms

The `/send/mail`, `/send/invite`, `/remember` routes have a paired
GET (form) and POST (submit). Each form includes a visible "I
confirm" checkbox; without it the POST returns 412:

```bash
curl -i -sS http://127.0.0.1:7777/send/mail \
  -H 'Accept: application/json' \
  -d to=a@example.com -d subject=test -d body=hi
# HTTP/1.1 412 Precondition Failed
# {"tool":"hugr","command":"send mail","ok":false,
#  "exit_code":1,
#  "error":{"code":"confirmation_required", ...}}
```

See [mutations.md](mutations.md).

## Surface parity guarantee

Every TUI screen and every web route is backed by an `hugr.api`
function. There's no business logic in the surfaces themselves - they
serialize and prompt; the api does the work. If you add a new fused
verb, it shows up in all surfaces (CLI, TUI, web) as soon
as you wire one Click subcommand, one TUI screen, and one route.
