"""Translation table from ``hugr <verb>`` to ``<underlying-tool> <args>``.

The router rule: argument mapping (flag rename, subcommand rename,
default-value injection) is allowed; business logic is not. If a
mapping needs more than rewriting argv, the logic belongs in the
underlying tool first.

`hugr doctor` and `hugr version` compose multiple tools and live in
the command modules rather than the table.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Literal, Sequence


_LEDGER_SOURCE_ID = "tier2_ledger"


# JSON injection policy per row.
#
# - "inject": append --json to argv if not already present. Used for
#   tools that expect an explicit machine-mode flag (yaams, ledger).
# - "native": underlying tool emits JSON by default; --json is either
#   unknown or only accepted at the top level. The OWA tools fit here:
#   `owa-mail config --json` rejects --json as an unknown flag. Don't
#   inject.
# - "none": never inject. Used for interactive children (the
#   interactive=True flag also gates stdio capture) and for rewrites
#   that produce the final argv shape themselves (e.g. bare
#   `ledger context` -> `--format json`).
JsonPolicy = Literal["inject", "native", "none"]


@dataclass(frozen=True)
class Mapping:
  """A single translation-table row."""
  binary: str  # underlying binary name (e.g. "yaams")
  rewrite: Callable[[Sequence[str]], list[str]]  # hugr-args -> underlying-args
  description: str  # one-line summary for `hugr hello`
  # Interactive verbs prompt the human directly. hugr must NOT inject
  # --json into their argv (the underlying tool will reject it per
  # CONVENTIONS.md) and must NOT capture stdio - the child needs the
  # real terminal so prompts and TTY tricks work.
  interactive: bool = False
  # See JsonPolicy above. Default "inject" preserves the historical
  # passthrough behavior for yaams/ledger.
  json_policy: JsonPolicy = "inject"
  # --- verbose forwarding ---------------------------------------------
  # When the user runs hugr with -v/--verbose/--debug, hugr forwards
  # that intent to the child so you can see what's happening under the
  # hood. The mechanism differs per tool, so it is declared per row:
  #
  # - verbose_env: an (NAME, VALUE) env var the child honors. This is
  #   position-independent and works for every subcommand, so it is the
  #   preferred mechanism where the tool supports one (every owa-* tool
  #   reads <TOOL>_DEBUG=1).
  # - verbose_flag: a flag appended to the rewritten argv. Used only for
  #   tools with no debug env var (yaams -v, ledger --verbose). MUST only
  #   be set on rows whose underlying subcommand actually accepts the
  #   flag — appending it to a subcommand that rejects unknown options
  #   would turn a normal run into a usage error.
  #
  # A row may set neither (no verbose mechanism exists upstream, e.g.
  # owa-piggy), one, or both.
  verbose_env: tuple[str, str] | None = None
  verbose_flag: str | None = None


def _passthrough(extra: Sequence[str] = ()) -> Callable[[Sequence[str]], list[str]]:
  """Append hugr-args verbatim to the static command head."""
  head = list(extra)

  def rewrite(args: Sequence[str]) -> list[str]:
    return head + list(args)

  return rewrite


def _query_rewrite(args: Sequence[str]) -> list[str]:
  """`hugr query` is a thin passthrough to `yaams query`.

  Earlier drafts of CONVENTIONS.md described hugr rewriting
  `--tier ledger` into `--source ledger` here. That rewrite became
  unnecessary in Phase 2b when yaams gained native `--tier
  raw|ledger|both` support (the alias rewrite happens inside yaams
  now). Per the router rule "argument mapping allowed, business
  logic forbidden", anything yaams handles natively stays as a
  passthrough.
  """
  return ["query", *list(args)]


# Keep the table flat. One row per hugr verb. Subcommand-shaped verbs
# (e.g. `hugr promote review`) match by exact head and forward the
# tail verbatim.
TABLE: dict[tuple[str, ...], Mapping] = {
  # --- YAAMS (Tier 1 raw) ---------------------------------------------
  ("ingest",): Mapping(
    binary="yaams",
    rewrite=_passthrough(["ingest"]),
    description="Ingest all configured sources into YAAMS",
    verbose_flag="-v",  # yaams ingest streams DEBUG logs to stderr with -v
  ),
  ("sources",): Mapping(
    binary="yaams",
    rewrite=_passthrough(["sources"]),
    description="Toggle which ingest sources are enabled (interactive)",
    interactive=True,
    json_policy="none",
  ),
  ("stats",): Mapping(
    binary="yaams",
    rewrite=_passthrough(["stats"]),
    description="Show YAAMS store stats (counts, sizes, last ingest)",
  ),
  ("feedback",): Mapping(
    binary="yaams",
    rewrite=_passthrough(["feedback"]),
    description="Log retrieval feedback for a query (hit/miss/correction/...)",
  ),
  ("review",): Mapping(
    binary="yaams",
    rewrite=_passthrough(["review"]),
    description="Walk the unjudged-query queue (interactive TUI)",
    interactive=True,
    json_policy="none",
  ),
  # Top-level `briefing` is ledger-backed but surfaced flat: it is a
  # daily ritual verb in the README, not a ledger-internal one.
  ("briefing",): Mapping(
    binary="ledger",
    rewrite=_passthrough(["briefing"]),
    description="Daily or weekly briefing from the cognitive ledger",
    json_policy="none",
  ),
  # Daily ritual verbs, surfaced flat (ledger-backed, like briefing).
  ("loops",): Mapping(
    binary="ledger",
    rewrite=_passthrough(["loops"]),
    description="List open loops from the cognitive ledger",
    verbose_flag="--verbose",
  ),
  ("notes",): Mapping(
    binary="ledger",
    rewrite=_passthrough(["notes"]),
    description="List ledger notes by type (requires --type)",
    verbose_flag="--verbose",
  ),
  ("query",): Mapping(
    binary="yaams",
    rewrite=_query_rewrite,
    description="Query the suite (Tier 1 raw + Tier 2 curated)",
  ),
  ("promote", "review"): Mapping(
    binary="yaams",
    rewrite=_passthrough(["promote", "review"]),
    description="Review promotion candidates interactively",
    interactive=True,
  ),
  ("promote", "generate"): Mapping(
    binary="yaams",
    rewrite=_passthrough(["promote", "generate"]),
    description="Generate fresh promotion candidates",
  ),
  ("promote", "list"): Mapping(
    binary="yaams",
    rewrite=_passthrough(["promote", "list"]),
    description="List existing promotion candidates",
  ),
  # --- cognitive-ledger (Tier 2 curated) ------------------------------
  ("ledger", "init"): Mapping(
    binary="ledger",
    rewrite=_passthrough(["init"]),
    description="Bootstrap a new cognitive ledger",
  ),
  ("ledger", "paths"): Mapping(
    binary="ledger",
    rewrite=_passthrough(["paths"]),
    description="Show resolved ledger paths",
  ),
  ("ledger", "query"): Mapping(
    binary="ledger",
    rewrite=_passthrough(["query"]),
    description="Query the curated atomic-notes layer directly",
  ),
  ("ledger", "loops"): Mapping(
    binary="ledger",
    rewrite=_passthrough(["loops"]),
    description="List open loops from the ledger",
    verbose_flag="--verbose",
  ),
  ("ledger", "notes"): Mapping(
    binary="ledger",
    rewrite=_passthrough(["notes"]),
    description="List ledger notes by type",
    verbose_flag="--verbose",
  ),
  ("ledger", "sleep"): Mapping(
    binary="ledger",
    rewrite=_passthrough(["sleep"]),
    description="Electric Sheep maintenance (sleep, lint, index, status, sync)",
    json_policy="none",
  ),
  ("ledger", "links"): Mapping(
    binary="ledger",
    rewrite=_passthrough(["links"]),
    description="Show ledger link graph (or links for a single note)",
    json_policy="none",
  ),
  # Bare `ledger context` exposes --format boot|identity|json (not
  # --json) at the cognitive-ledger layer. We translate to
  # `context --format json` and mark json_policy=none so passthrough
  # does not append --json on top. Subcommands `context build` and
  # `context profiles` use their own --json natively, so they live on
  # separate rows with the default inject policy. Longest-prefix
  # match in `lookup()` ensures the 3-tuple keys resolve first.
  ("ledger", "context"): Mapping(
    binary="ledger",
    rewrite=lambda a: ["context", "--format", "json", *list(a)],
    description="Output boot context (JSON)",
    json_policy="none",
  ),
  ("ledger", "context", "build"): Mapping(
    binary="ledger",
    rewrite=_passthrough(["context", "build"]),
    description="Build curated context files",
  ),
  ("ledger", "context", "profiles"): Mapping(
    binary="ledger",
    rewrite=_passthrough(["context", "profiles"]),
    description="List ledger context profiles",
  ),
  # --- owa-piggy (auth) -----------------------------------------------
  # owa-piggy is JSON-by-default like the rest of the OWA suite, so we
  # do not inject --json. The shared run_with_output_modes() layer
  # only consumes --json for the top-level --doctor probe.
  ("auth", "status"): Mapping(
    binary="owa-piggy",
    rewrite=_passthrough(["status"]),
    description="Show M365 auth status (all profiles)",
    json_policy="native",
  ),
  ("auth", "setup"): Mapping(
    binary="owa-piggy",
    rewrite=_passthrough(["setup"]),
    description="Interactive first-time M365 auth setup",
    interactive=True,
    json_policy="none",
  ),
  ("auth", "reseed"): Mapping(
    binary="owa-piggy",
    rewrite=_passthrough(["reseed"]),
    description="Refresh expired tokens from the Edge sidecar",
    json_policy="native",
  ),
  ("auth", "profiles"): Mapping(
    binary="owa-piggy",
    rewrite=_passthrough(["profiles"]),
    description="List / manage M365 profiles",
    json_policy="native",
  ),
  ("auth", "token"): Mapping(
    binary="owa-piggy",
    rewrite=_passthrough(["token"]),
    description="Print an M365 access token (audience-aware)",
    json_policy="native",
  ),
  ("auth", "remaining"): Mapping(
    binary="owa-piggy",
    rewrite=_passthrough(["remaining"]),
    description="Minutes left on the current access token",
    json_policy="native",
  ),
  ("auth", "debug"): Mapping(
    binary="owa-piggy",
    rewrite=_passthrough(["debug"]),
    description="Full owa-piggy diagnostics (token, profile, sidecar)",
    json_policy="native",
  ),
  ("auth", "decode"): Mapping(
    binary="owa-piggy",
    rewrite=_passthrough(["decode"]),
    description="Decode JWT header + payload of the current token",
    json_policy="native",
  ),
  # --- owa-tools (M365 read/write) ------------------------------------
  # OWA tools emit JSON by default; their subcommand parsers reject
  # --json as an unknown flag. json_policy="native" keeps the argv
  # clean and unblocks hugr mail/cal/graph/people/schedule/drive.
  ("mail",): Mapping(
    binary="owa-mail",
    rewrite=_passthrough([]),
    description="Outlook mail (messages, send, reply, search, ...)",
    json_policy="native",
    verbose_env=("MAIL_DEBUG", "1"),
  ),
  ("cal",): Mapping(
    binary="owa-cal",
    rewrite=_passthrough([]),
    description="Outlook calendar (events, create, update, ...)",
    json_policy="native",
    verbose_env=("CAL_DEBUG", "1"),
  ),
  ("graph",): Mapping(
    binary="owa-graph",
    rewrite=_passthrough([]),
    description="Generic Microsoft Graph CLI (GET/POST/PATCH/DELETE)",
    json_policy="native",
    verbose_env=("GRAPH_DEBUG", "1"),
  ),
  ("people",): Mapping(
    binary="owa-people",
    rewrite=_passthrough([]),
    description="People / directory lookup",
    json_policy="native",
    verbose_env=("PEOPLE_DEBUG", "1"),
  ),
  ("schedule",): Mapping(
    binary="owa-sched",
    rewrite=_passthrough([]),
    description="Free/busy and find-time scheduling helpers",
    json_policy="native",
    verbose_env=("SCHED_DEBUG", "1"),
  ),
  ("drive",): Mapping(
    binary="owa-drive",
    rewrite=_passthrough([]),
    description="OneDrive (ls, get, put, rm, ...)",
    json_policy="native",
    verbose_env=("DRIVE_DEBUG", "1"),
  ),
  ("vids",): Mapping(
    binary="owa-vids",
    rewrite=_passthrough([]),
    description="Download Teams / OneDrive meeting-recap DASH streams to MP4",
    json_policy="native",
    verbose_env=("VIDS_DEBUG", "1"),
  ),
}


def lookup(args: Sequence[str]) -> tuple[Mapping, list[str]] | None:
  """Resolve a hugr argv into (mapping, rewritten-argv).

  Returns None if no mapping matches the head.
  """
  args = list(args)
  if not args:
    return None
  # Try longest prefix match first. Today every hugr verb is a
  # single token, but `hugr promote review` etc will arrive in 3b.
  for n in range(min(len(args), 3), 0, -1):
    head = tuple(args[:n])
    mapping = TABLE.get(head)
    if mapping is not None:
      tail = args[n:]
      rewritten = mapping.rewrite(tail)
      return mapping, rewritten
  return None


def verbose_overlay(mapping: Mapping) -> tuple[dict[str, str], list[str]]:
  """Translate a row's verbose strategy into concrete forwarding.

  Returns ``(env_overlay, extra_argv)`` to apply when the user asked
  for verbose output:

  - ``env_overlay`` merges into the child's environment (preferred:
    position-independent, every subcommand honors it).
  - ``extra_argv`` is appended to the child argv (for tools with no
    debug env var, gated per row to subcommands that accept the flag).

  Both may be empty when the row declares no verbose mechanism.
  """
  env: dict[str, str] = {}
  if mapping.verbose_env:
    env[mapping.verbose_env[0]] = mapping.verbose_env[1]
  flag = [mapping.verbose_flag] if mapping.verbose_flag else []
  return env, flag


def verbs() -> list[tuple[str, str, str]]:
  """Return (hugr-verb, binary, description) rows for `hugr hello`."""
  return [
    (" ".join(verb), m.binary, m.description)
    for verb, m in TABLE.items()
  ]
