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
> `--doctor` payload, the 0-5 doctor taxonomy, `redact()`) now comes
> from the shared `hugr-conventions` package (see cross-cutting).

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
   `action_envelope()` helpers are kept (now via `hugr-conventions`)
   for the `--doctor` surface and any future opt-in, not as the
   command-path default.

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

These are not per-repo but apply to the suite as a whole:

1. ~~**Shared `redact()` utility.**~~ **RESOLVED 2026-05-27.** Lives
   in `hugr-conventions` (`redact()`); each tool drops its hand-rolled
   copy and depends on the package.
2. ~~**Doctor schema package.**~~ **RESOLVED 2026-05-27.**
   `DoctorFinding` / `DoctorPayload` / `emit_doctor` ship from
   `hugr-conventions`.
3. ~~**Action envelope helpers.**~~ **RESOLVED 2026-05-27.**
   `action_envelope` / `emit_action` / `data_error` / `emit_data_error`
   and the NDJSON `stream_*` helpers ship from `hugr-conventions`.

Recommendation (DONE): `hugr-conventions` is published from this repo
under `packages/hugr-conventions/` (importable as `hugr_conventions`,
zero runtime deps). `hugr` itself now depends on it - `src/hugr/
conventions.py` is a thin tool-bound shim over `hugr_conventions.bind`.

Per-repo adoption (DONE 2026-05-27): every sibling carrying a
copy-pasted `conventions.py` now depends on `hugr-conventions` and
binds via the package instead. Each kept its tool-specific bits and
its full test suite stayed green:

- **owa-tools** — binds suite version + owa's richer `redact()` (it
  also scrubs attachment paths); keeps the `--doctor` redaction-
  sentinel default payload. 1055 passed.
- **cognitive-ledger** — keeps the `tool=` override (`sheep` stamps
  its own name) and the in-tree `__version__` preference. 715 passed.
- **yaams** — straight bind to tool name + `__version__`. 347 passed.
- **owa-piggy** — binds tool name + version; no stream helpers (the
  auth broker has no streaming actions). 283 passed.

Note: adoption swaps the helper *source* for the shared `--doctor`
surface; it does not (and is not meant to) impose the hugr action
envelope on owa-tools' command paths. The owa-tools "block" items
were reconciled on 2026-05-27 (see that section): blocks 1 and 3 are
won't-fix deliberate divergences documented in owa-tools' AGENTS.md
(the `--agent` envelope and the `0/2/10-15/20` taxonomy), and block 2
was already implemented. No per-command owa-tools work is outstanding
from this audit.
