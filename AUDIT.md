# Conformance audit (Phase 2a)

**Audit date**: 2026-05-12
**Last reconciled**: 2026-05-24
**Auditor**: read-only scan of source under `~/code/{YAAMS,
cognitive-ledger, owa-piggy, owa-tools}` against
[CONVENTIONS.md](CONVENTIONS.md) v1.

Each gap below is one issue to file against the named repo before
the Phase 2b/2c migration starts. The hugr repo does not file these
issues itself - that is a human action that touches shared state
(GitHub).

Severity legend:
- **block**: violates a hard invariant; the suite contract breaks if
  not fixed.
- **major**: required for `hugr` to ship, but not invariant-breaking.
- **minor**: stylistic or surface-area gap that can land any time
  before Phase 3a.

> Resolved items have been removed during the 2026-05-24 reconciliation
> pass. YAAMS, cognitive-ledger, and owa-piggy have shipped their
> Phase 2b/2c work; only the items below remain.

---

## YAAMS (`damsleth/yaams`, v0.1.x)

**Target**: v0.2.0 in Phase 2b.

### minor
1. **Stderr deprecation warning** when stdout is a TTY and the
   user gets legacy default human output that flips in 0.2.x.
   Migration-window requirement; not a permanent contract.

---

## cognitive-ledger (`damsleth/cognitive-ledger`, v0.2.x)

**Target**: v0.3.0 in Phase 2b, same week as YAAMS.

### minor
1. **`sheep` subcommand `--json` / `--pretty` is partial.** `status`,
   `lint`, and `sleep` still wrap human-readable lines into a payload
   rather than emitting structured fields; `index` and `sync` already
   return proper envelopes. Tighten the three remaining commands so
   every sheep subcommand returns structured data under `--json`.

---

## owa-tools (`damsleth/owa-tools`, v0.2.1)

**Target**: v0.2.0 in Phase 2c (shipped). Nine binaries:
`owa`, `owa-cal`, `owa-mail`, `owa-graph`, `owa-doctor`,
`owa-people`, `owa-sched`, `owa-drive`, `owa-todo`.

> **Reconciled 2026-05-27.** This section was written against the
> 2026-05-12 snapshot, before owa-tools' Phase 2c work landed. During
> that work owa-tools chose - and documented in its `AGENTS.md` - a
> richer envelope/error model than the bare hugr CONVENTIONS.md
> contract, deliberately diverging on two of the three "block" items.
> The divergence is intentional and signed off; the items below are
> reclassified accordingly rather than left as open gaps. The
> contract surface owa-tools *does* share with the suite (the
> `--doctor` payload, the 0-5 doctor taxonomy, `redact()`) is
> vendored into `owa_core/conventions.py` - see cross-cutting for
> the 2026-05-28 reversal away from a shared runtime package.

### block

1. **No action envelopes** - **WON'T FIX (deliberate divergence).**
   owa-tools' stable automation contract is the `--agent` /
   `OWA_AGENT=1` envelope - `{"_owa": {suite,tool,version,
   schema_version,command,profile}, "data": <result>}` - applied
   uniformly to every command's JSON stdout by
   `owa_core/modes.py:run_with_output_modes`. AGENTS.md documents
   this as a permanent contract. owa-tools deliberately does not emit
   the hugr per-command `{tool,version,command,ok,duration_ms,...}`
   action envelope; the `--agent` wrapper is its equivalent and is
   richer (carries suite/schema_version/profile). The
   `action_envelope()` helpers are kept (now vendored in
   `owa_core/conventions.py`) for the `--doctor` surface and any
   future opt-in, not as the command-path default.

2. **Destructive gating** - **DONE.** `owa_core/tty.py:
   require_confirm_or_tty()` raises `UsageError` ("... refuses to run
   non-interactively without --confirm") when neither `--confirm`/
   `--yes` nor an interactive TTY is present. Wired into `owa-cal
   delete`, `owa-mail delete`, `owa-drive rm`, etc. Non-interactive
   refusal is enforced, not schema-only.

3. **Exit codes** - **WON'T FIX (deliberate divergence).** owa-tools
   keeps its own `0/2/10-15/20` taxonomy (`owa_core/errors.py:
   ExitCode`) because it distinguishes network / auth-expired /
   scope / not-found / rate-limited / conflict / internal - detail
   the flat hugr 0-5 set cannot express. AGENTS.md confines the hugr
   0-5 taxonomy to the `--doctor` surface and states command paths
   must raise an `owa_core.errors` subclass, not return a
   `conventions.EXIT_*` constant. Signed off.

### major

4. **Explicit `--json` flag** - **N/A by design.** owa-tools is
   JSON-by-default and never flips output on isatty heuristics, so
   the hugr "assert I want JSON" need is moot; `--agent` is the
   explicit machine-mode toggle. `--json` is accepted on the
   `--help` / `--doctor` surfaces only.
5. **NDJSON streaming on `owa-graph batch`** - **DONE 2026-05-27.**
   `owa-graph batch --ndjson` streams one sub-response per line
   (mirrors the verb commands; mutually exclusive with `--pretty`).
6. **Reserved-key (`ok`) on Graph passthrough** - **resolved by
   envelope.** The `--agent` wrapper nests the raw Graph payload
   under `data`, so a top-level `ok` in a Graph response never
   collides with the discriminator. Raw (non-`--agent`) passthrough
   does not claim hugr reserved-key compliance by design.
7. **`--pretty` on action commands** - **by design / low priority.**
   `--pretty` is wired on data commands (`messages`, `show`,
   `folders`). Action commands return a compact JSON result; owa-tools
   does not promise a human renderer for them.

### minor
8. **Redaction sentinel test** for message bodies in `owa-mail
   send/reply/forward` failure paths - **DONE 2026-05-27, and it
   caught a real bug.** Adding the fixture (`tests/mail/
   test_redaction.py`, driving the real `owa_core.http` layer)
   revealed that `owa_core.secrets.redact()` scrubbed only secret
   *shapes*, not message-content fields - so `--debug`/`MAIL_DEBUG`
   printed full email/event/task bodies to stderr suite-wide. Fixed
   by adding body/content/text field redaction to `redact()` per
   CONVENTIONS.md; covered by `tests/security/test_secrets.py` and the
   new mail fixture.
9. **`owa-doctor` aggregator JSON shape** vs per-binary payloads -
   **PARTIAL.** `tests/doctor/test_cli_report.py` covers the
   aggregate `build_report()` shape; an explicit cross-check that the
   aggregated `siblings[]` entries match each binary's own `--doctor`
   payload schema is still worth adding.

---

## hugr (`damsleth/hugr`, this repo)

**Target**: 0.1.0 in Phase 3a.

This repo is greenfield. Phase 1 deliverables (README, SUITE,
CONVENTIONS) are in place. No code yet; the router lands in 3a.

The conformance table at the bottom of CONVENTIONS.md defines what
`hugr` itself must implement; nothing to audit retroactively.

---

## Cross-cutting issues

These are not per-repo but apply to the suite as a whole.

### Shared contract: spec, not package (2026-05-28 reversal)

CONVENTIONS.md is the spec. Each tool carries its own self-contained
`conventions.py` implementation of that spec - **no shared runtime
package, no cross-component install-time coupling**. Loose coupling
between suite components is an axiom: yaams, cognitive-ledger,
owa-piggy, owa-tools, and hugr each install and run on their own.

The short-lived `hugr-conventions` PyPI package (introduced
2026-05-27) was reversed:

- **owa-tools** caught it first: v0.3.0 wheel was uninstallable
  because `hugr-conventions` was never on PyPI, and the package
  shape violated owa-tools' "no third-party runtime dependency"
  rule. v0.3.1 vendored the contract back into
  `owa_core/conventions.py`. See `owa-tools/CHANGELOG.md`.
- **yaams, cognitive-ledger, owa-piggy** followed 2026-05-28:
  `hugr-conventions>=0.1` removed from `pyproject.toml`,
  `conventions.py` rewritten as self-contained. Tool-specific bits
  preserved (ledger's `tool=` override for `sheep` and in-tree
  `__version__` resolution; owa-piggy's omission of stream helpers).
- **hugr** itself: `packages/hugr-conventions/` deleted from this
  repo. `src/hugr/conventions.py` is now self-contained too. The
  spec stays in `CONVENTIONS.md`; new tools copy from any existing
  sibling.

Test results post-reversal: yaams 347, cognitive-ledger 720,
owa-piggy 291, owa-tools 1055+ (already shipped 2026-05-27), hugr's
conventions module 17/17.

### Resolved items (kept for history)

1. ~~**Shared `redact()` utility.**~~ **VENDORED 2026-05-28** (was
   "shared package 2026-05-27"). Each tool carries its own
   `redact()`; the spec in CONVENTIONS.md is what they share, not a
   runtime import.
2. ~~**Doctor schema.**~~ **VENDORED 2026-05-28.**
   `DoctorFinding` / `DoctorPayload` live inside each tool's
   `conventions.py`.
3. ~~**Action envelope helpers.**~~ **VENDORED 2026-05-28.**
   `action_envelope` / `emit_action` / `data_error` /
   `emit_data_error` and the NDJSON `stream_*` helpers live inside
   each tool's `conventions.py`.

### Drift handling

Contract drift is now managed by spec review of CONVENTIONS.md
plus a per-tool re-vendor pass when the spec changes. The accepted
tradeoff: contract evolution requires a touch in N repos instead of
one, in exchange for each tool staying independently installable
and free of cross-component runtime dependencies. The owa-tools
divergences (`--agent` envelope, `0/2/10-15/20` exit-code taxonomy)
remain signed-off deliberate departures from the shared `--doctor`
surface.
