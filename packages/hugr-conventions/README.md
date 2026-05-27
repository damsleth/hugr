# hugr-conventions

Shared CLI-contract primitives for the [hugr](https://github.com/damsleth/hugr)
memory suite — the executable form of the wire contract specified in
[`CONVENTIONS.md`](https://github.com/damsleth/hugr/blob/main/CONVENTIONS.md).

Every JSON-capable binary in the suite (`yaams`, `ledger`, `sheep`,
`owa-piggy`, the eight `owa-*` tools, and `hugr` itself) emits the
same shapes:

- **Action envelope** — `{tool, version, command, ok, duration_ms, stats, warnings, error}`
- **Data-class error envelope** — the minimal `{tool, version, command, ok: false, error}` a data command switches to on failure
- **NDJSON streaming** — `progress` / `warning` / terminal `result` lines for long-running actions
- **Doctor payload** — `{tool, version, config_path, data_path, auth, models, findings[]}`
- **Exit codes** — the `0`–`5` taxonomy (`EXIT_OK` … `EXIT_PARTIAL`)
- **`redact()`** — the suite-wide stderr/log redactor (JWTs, bearer tokens, secret fields, message bodies)

Previously each repo carried a hand-copied `conventions.py`. This
package is the single source of truth they depend on instead, so the
contract drifts in one place or none.

## Usage

Bind once to your tool name and version, then emit:

```python
from hugr_conventions import bind

C = bind("owa-mail", lambda: __version__)  # version may be str or callable

# action command
C.emit_action(C.action_envelope(command="send", ok=True, stats={"to": 1}))

# data command failure
C.emit_data_error(C.data_error(
    command="messages", code="auth_expired",
    message="M365 access token expired", hint="Run: hugr auth setup",
))

# doctor
import sys
rc = C.emit_doctor(C.doctor_payload(config_path="..."), as_json=True)
sys.exit(rc)
```

A `lambda: __version__` version avoids importing your package's
`__version__` until an envelope is actually emitted, sidestepping
import cycles.

The module-level functions (`action_envelope`, `data_error`,
`DoctorPayload`, …) take `tool` and `version` explicitly if you'd
rather not bind — useful for an aggregator emitting on behalf of
several tools.

## Versioning

This package follows the `CONVENTIONS.md` major version. A change to
the wire contract is a breaking change here.
