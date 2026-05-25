<p align="center">
  <img src="hugr.png" alt="hugr logo" style="max-height: 200px;" height="200">
</p>

# ᚼᚢᚴᛦ - (/ˈhuɡr/)
[![License: MIT](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)
![status](https://img.shields.io/badge/status-pre--release-orange)

**A local-first memory suite for AI agents.** One install gets you a
two-tier memory store, an M365 read/write surface, and a single CLI
that ties them together. Your data stays on your machine.

`hugr` is the umbrella over four independent tools that already work
on their own. The umbrella adds one verb surface, one install
command, and one place to find what is in the box.

The name `hugr` is from Old Norse, where it means "mind, thought,
sense" - and in the Norse conception of self, specifically the part
of the mind that can travel outside the body to see and act on
distant things. The wordmark in Younger Futhark is ᚼᚢᚴᛦ:
hagall, úr, kaun, yr.

```
                            hugr (meta-CLI + suite hub)
                                       |
              +------------------------+------------------------+
              |               |                |                |
            YAAMS    cognitive-ledger    owa-piggy        owa-tools
         (Tier 1 raw) (Tier 2 curated)  (M365 auth)   (M365 read/write)
```

## What's in the box

| Tool | Purpose | Binaries |
| --- | --- | --- |
| [**YAAMS**](https://github.com/damsleth/yaams) | Tier 1 raw memory store - every iMessage, mail, calendar event, GitHub issue, ingested and queryable from a single SQLite file. | `yaams` |
| [**cognitive ledger**](https://github.com/damsleth/cognitive-ledger) | Tier 2 curated atomic notes engine - the gems you promote out of YAAMS and keep forever as markdown with frontmatter. | `ledger`, `ledger-obsidian`, `sheep` |
| [**owa piggy**](https://github.com/damsleth/owa-piggy) | Microsoft 365 auth broker - turns your existing Outlook Web session into a reusable token. No app registration. | `owa-piggy` |
| [**owa tools**](https://github.com/damsleth/owa-tools) | M365 read/write CLI suite - calendar, mail, Graph, OneDrive, scheduling, people lookup, all JSON-by-default. | `owa`, `owa-cal`, `owa-mail`, `owa-graph`, `owa-doctor`, `owa-people`, `owa-sched`, `owa-drive` |

`hugr` itself adds one more binary that routes the verbs above into
a single user-facing surface.

## Install

```bash
brew install damsleth/tap/hugr
hugr init --quick
hugr hello
```

Or via pipx (Python):

```bash
pipx install "hugr-cli[all]"   # CLI + TUI + web + server + MCP
hugr init --quick
```

Full install + setup story in [`docs/installation.md`](docs/installation.md).

## A taste of what it does

```bash
hugr recall "what did we decide at the brand kickoff?"
hugr find person nina
hugr inbox                                # unread mail + today + loops + promotions
hugr remember "Nina prefers early flights" --yes
hugr send mail --to a@example.com --subject "lunch" --body "12:00?" --yes
hugr book propose "Standup" --who vibeke@example.com --duration 30 --date tomorrow
hugr book commit  "Standup" --who vibeke@example.com --duration 30 --date tomorrow --slot 0 --yes
hugr tui                                  # Textual TUI
hugr web                                  # FastAPI web on 127.0.0.1:7777
hugr server --mcp                         # deploy-ready, mounts /mcp HTTP transport
hugr sync push --yes                      # encrypted state to a private GitHub repo
```

Every JSON-capable command accepts `--json` (machine mode) and
`--pretty` (human rendering). Exit codes follow
[CONVENTIONS.md](CONVENTIONS.md):
`0` ok, `1` user error, `2` transient, `3` auth, `4` not found,
`5` partial success.

## Documentation

Start with [`docs/`](docs/):

| Doc | What it covers |
| --- | --- |
| [`docs/installation.md`](docs/installation.md) | Install + first-time wizard |
| [`docs/quickstart.md`](docs/quickstart.md) | Five-minute tour of the verbs |
| [`docs/cli-reference.md`](docs/cli-reference.md) | Every command and flag, with examples |
| [`docs/recall.md`](docs/recall.md) | `recall`, `find`, `inbox` - the fused query verbs |
| [`docs/mutations.md`](docs/mutations.md) | `send`, `book`, `remember`, confirmation rules |
| [`docs/sessions.md`](docs/sessions.md) | Session model + working sets |
| [`docs/surfaces.md`](docs/surfaces.md) | TUI, web UI, MCP, `hugr server` |
| [`docs/sync.md`](docs/sync.md) | Cross-device state sync over git + age |
| [`docs/config.md`](docs/config.md) | Master config + env vars |
| [`docs/troubleshooting.md`](docs/troubleshooting.md) | Common errors and fixes |

Architecture and contract:

- [`SUITE.md`](SUITE.md) - data flow and architecture diagram.
- [`CONVENTIONS.md`](CONVENTIONS.md) - the CLI contract every tool in
  the suite conforms to.
- [`deploy/docs/deploy.md`](deploy/docs/deploy.md) - Docker / systemd /
  Cloudflare / tailscale recipes for `hugr server`.

## Skills

Two agent skill repos sit on top of `hugr`:

- [`damsleth/SKILLS`](https://github.com/damsleth/SKILLS) - public,
  reusable agent skills. Includes `/memory`, which routes through
  `hugr`.
- `damsleth/SKILLS-private` - personal-infra `cj-*` skills (timereg,
  did, weekly review). Same installer pattern; private repo.

Skills wrap `hugr`. `hugr` does not call skills. One direction, no
circular dependencies.

## License

MIT. See [LICENSE](LICENSE).
