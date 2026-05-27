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

## owa-tools (`damsleth/owa-tools`, v0.1.x)

**Target**: v0.2.0 in Phase 2c. Eight binaries:
`owa`, `owa-cal`, `owa-mail`, `owa-graph`, `owa-doctor`,
`owa-people`, `owa-sched`, `owa-drive`.

### block
1. **No action envelopes** on any action-class command (`owa-cal
   create/update/delete`, `owa-mail send/reply/forward/delete/move/
   mark`, `owa-graph post/put/patch/delete/batch`, `owa-drive
   get/put/rm`, `owa-* refresh`). Helpers exist in
   `owa_core/conventions.py` but are not wired into the CLI
   implementations - they still emit raw data.
2. **Destructive gating is schema-only.** `owa-cal delete`,
   `owa-mail delete`, `owa-graph delete`, `owa-drive rm` advertise
   the destructive flag in the schema and use TTY confirmation
   prompts (e.g. `owa_mail/cli.py:474-507`), but do not enforce
   `--yes` / `--confirm` per the envelope contract.
3. **Exit codes** - the suite still uses the pre-hugr taxonomy
   (`0/2/10-15/20`). The hugr 2/3/4/5 codes are defined in
   `conventions.py` but only flow out of `--doctor`. Action
   commands need to adopt them too.

### major
4. **Explicit `--json` flag missing.** owa-tools is JSON-by-default,
   but the explicit no-op `--json` alias (that also blocks isatty
   heuristics) is not accepted on action subcommands.
5. **NDJSON streaming on `owa-graph batch`** is not implemented.
   Batch is the one long-running action and needs the streaming
   contract under `--json`.
6. **Reserved-key compliance on Graph passthrough.** Raw Graph
   responses can contain a top-level `ok` field. Audit and wrap.
7. **`--pretty` is documented but not wired.** Help text mentions
   it and the schema references it, but there is no actual
   `--pretty` flag on action commands - output is JSON-only with no
   human-readable switch.

### minor
8. **Redaction sentinel test** specifically for message bodies in
   `owa-mail send/reply/forward` failure paths. The generic
   conventions sentinel test exists, but the body-redaction fixture
   does not.
9. **`owa-doctor` aggregator JSON shape** is not explicitly tested
   against the per-binary doctor payloads that `hugr doctor` will
   consume.

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

Remaining follow-up (per-repo, tracked against each sibling): swap
each tool's copy-pasted `conventions.py` for a dependency on
`hugr-conventions`, binding via `bind(tool, version)`. This is the
mechanism that closes owa-tools block items 1 and 3 (the helpers
exist there but were never wired into the CLIs) and the
cognitive-ledger `sheep` JSON gap. As of 2026-05-27 no sibling has
adopted the package yet.
