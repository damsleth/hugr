# hugr documentation

`hugr` is a single CLI over four memory + M365 tools. Start here.

## Reading order

| Doc | Why |
| --- | --- |
| [installation.md](installation.md) | Install the suite, run the first-time wizard, confirm health. |
| [quickstart.md](quickstart.md) | Five-minute tour: recall, find, inbox, remember. |
| [cli-reference.md](cli-reference.md) | Every command, every flag, with examples. |
| [recall.md](recall.md) | `hugr recall`, `find`, `inbox` - the fused query verbs. |
| [mutations.md](mutations.md) | `send mail`, `send invite`, `book`, `remember`. Confirmation rules. |
| [sessions.md](sessions.md) | `$HUGR_HOME/sessions/<id>/`, working sets, follow-up queries. |
| [surfaces.md](surfaces.md) | TUI (`hugr tui`), web UI (`hugr web`), MCP (`hugr mcp`), `hugr server`. |
| [sync.md](sync.md) | `hugr sync init/push/pull/status` over git + age. |
| [config.md](config.md) | Master config, env vars, per-tool config adoption. |
| [troubleshooting.md](troubleshooting.md) | Common errors and how to fix them. |
| [init.md](init.md) | Deep dive on what `hugr init` does and doesn't touch. |

## Reference (in the repo root)

- [SUITE.md](../SUITE.md) - architecture diagram, data flow.
- [CONVENTIONS.md](../CONVENTIONS.md) - the contract every tool in the suite conforms to. Exit codes, action envelopes, NDJSON streaming.
- [AUDIT.md](../AUDIT.md) - open conformance gaps per tool.
- [deploy/docs/deploy.md](../deploy/docs/deploy.md) - Docker / systemd / Cloudflare / tailscale recipes for `hugr server`.

## Project layout (for the curious)

```
hugr/
├── src/hugr/
│   ├── api/         # in-process Python API (recall, find, send, ...)
│   ├── commands/    # Click subcommands (doctor, init, version, ...)
│   ├── mcp/         # MCP server (stdio + Streamable HTTP)
│   ├── server/      # FastAPI server runtime
│   ├── sync/        # git + age cross-device state sync
│   ├── tui/         # Textual terminal UI
│   ├── web/         # FastAPI web UI + JSON mirror + SSE
│   ├── cli.py       # the click root
│   ├── config.py    # master config + per-tool resolution
│   ├── conventions.py  # CONVENTIONS helpers (action envelope, exit codes)
│   ├── doctor.py    # cross-tool health check (in commands/)
│   ├── router.py    # translation table: hugr verb -> tool argv
│   ├── session.py   # session storage primitives
│   └── sources.py   # source detection + cache
├── deploy/          # Dockerfile, compose, systemd, deploy docs
└── docs/            # you are here
```
