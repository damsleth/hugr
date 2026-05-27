"""FastAPI web surface for hugr.

The web layer is a thin serializer over ``hugr.api``. It owns HTTP and
HTML rendering only; suite orchestration stays in the API module.

Routes:
  GET  /                 ask form / result
  GET  /recall?q=...     fused recall result
  POST /recall           form-driven recall
  GET  /inbox            inbox view
  GET  /find?kind=&q=    typed find
  GET  /doctor           doctor report
  GET  /session/{id}     session detail
  GET  /healthz          liveness probe

JSON parity: any GET/POST returns JSON when ``Accept: application/json``
is sent. ``/api/*`` mirrors the same handlers with JSON-only output.

SSE streaming (plan 03.4): ``GET /api/stream/ingest`` proxies hugr
ingest NDJSON as text/event-stream frames for HTMX hx-sse / EventSource
clients.
"""

from __future__ import annotations

import asyncio
import hmac
import html
import json
from typing import Any, AsyncIterator
from urllib.parse import urlsplit

import hugr.api as api
from hugr import session as session_mod

try:
  from fastapi import FastAPI, Header, Query, Request
  from fastapi.responses import HTMLResponse, JSONResponse, StreamingResponse
  _FASTAPI_AVAILABLE = True
except ImportError:  # pragma: no cover - exercised by CLI fallback
  _FASTAPI_AVAILABLE = False


def _wants_json(accept: str | None) -> bool:
  return bool(accept and "application/json" in accept.lower())


def _bearer_token(request: "Request") -> str | None:
  """Extract the bearer token from the Authorization header, if any."""
  header = request.headers.get("authorization") or ""
  scheme, _, value = header.partition(" ")
  if scheme.lower() != "bearer":
    return None
  return value.strip() or None


def _origin_ok(request: "Request") -> bool:
  """Reject cross-site mutations while allowing same-origin / non-browser.

  Browsers attach an ``Origin`` (and usually ``Referer``) header to
  cross-site form POSTs; the same-origin policy lets the request be sent
  but not its response read, so ``confirm=on`` alone does not stop a
  drive-by form targeting loopback. We compare the stated origin host to
  the request's own host and refuse on mismatch. Non-browser clients
  (curl, the CLI, API consumers) send neither header and are allowed -
  they are not the CSRF threat.
  """
  host = request.headers.get("host")
  for header in ("origin", "referer"):
    value = request.headers.get(header)
    if not value:
      continue
    if urlsplit(value).netloc != host:
      return False
  return True


def _html_page(title: str, body: str) -> str:
  return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{html.escape(title)} - hugr</title>
  <style>
    body {{ font-family: system-ui, sans-serif; margin: 2rem; line-height: 1.45; }}
    nav a {{ margin-right: 1rem; }}
    input, select, button {{ font: inherit; padding: .45rem .55rem; }}
    pre {{ background: #f6f6f6; padding: 1rem; overflow: auto; }}
  </style>
</head>
<body>
  <nav>
    <a href="/">Ask</a>
    <a href="/inbox">Inbox</a>
    <a href="/find">Find</a>
    <a href="/doctor">Doctor</a>
    <a href="/session">Session</a>
  </nav>
  {body}
</body>
</html>"""


def _doc_html(title: str, doc: Any) -> str:
  escaped = html.escape(json.dumps(doc, ensure_ascii=False, indent=2, default=str))
  return _html_page(title, f"<h1>{html.escape(title)}</h1><pre>{escaped}</pre>")


async def _stream_ingest(args: list[str]) -> AsyncIterator[str]:
  """Run hugr ingest and yield NDJSON lines as SSE frames.

  Uses asyncio.create_subprocess_exec so the event loop stays
  responsive. The child writes one JSON document per line per the
  CONVENTIONS streaming contract.
  """
  # stderr is discarded rather than PIPE'd: we only forward stdout NDJSON,
  # and an unread stderr pipe would let a noisy child fill its buffer and
  # block on write forever (see passthrough.py for the drained variant).
  proc = await asyncio.create_subprocess_exec(
    "hugr", "ingest", *args, "--json",
    stdout=asyncio.subprocess.PIPE,
    stderr=asyncio.subprocess.DEVNULL,
  )
  try:
    assert proc.stdout is not None
    async for raw in proc.stdout:
      line = raw.decode("utf-8", errors="replace").rstrip()
      if not line:
        continue
      yield f"data: {line}\n\n"
  finally:
    await proc.wait()
  yield f"event: done\ndata: {{\"exit_code\": {proc.returncode}}}\n\n"


def create_app(*, token: str | None = None):
  if not _FASTAPI_AVAILABLE:  # pragma: no cover - exercised by CLI fallback
    raise RuntimeError('web extra not installed; pipx install "hugr-cli[web]"')

  app = FastAPI(title="hugr", version="0.1")

  # When a token is configured (``hugr web --public`` with HUGR_WEB_TOKEN),
  # every route except the liveness probe requires a matching bearer
  # token. Loopback mode passes token=None and stays unauthenticated.
  if token:
    @app.middleware("http")
    async def _require_token(request: Request, call_next):
      if request.url.path == "/healthz":
        return await call_next(request)
      presented = _bearer_token(request) or ""
      # Constant-time compare so a wrong token can't be timed out byte by byte.
      if not hmac.compare_digest(presented, token):
        return JSONResponse(
          {
            "tool": "hugr",
            "ok": False,
            "exit_code": 1,
            "error": {
              "code": "unauthorized",
              "message": "missing or invalid bearer token",
              "hint": "Send Authorization: Bearer <HUGR_WEB_TOKEN>.",
            },
          },
          status_code=401,
        )
      return await call_next(request)

  @app.get("/healthz")
  def healthz():
    return {"ok": True, "tool": "hugr"}

  @app.get("/", response_class=HTMLResponse)
  def root(q: str = "", accept: str | None = Header(default=None)):
    if q:
      doc = api.recall(q)
      if _wants_json(accept):
        return JSONResponse(doc)
      return HTMLResponse(_doc_html("Ask", doc))
    return HTMLResponse(_html_page(
      "Ask",
      """
      <h1>Ask</h1>
      <form action="/recall" method="get">
        <input name="q" autofocus placeholder="Ask hugr">
        <button type="submit">Ask</button>
      </form>
      """,
    ))

  @app.get("/recall")
  def recall(q: str, accept: str | None = Header(default=None)):
    doc = api.recall(q)
    if _wants_json(accept):
      return JSONResponse(doc)
    return HTMLResponse(_doc_html("Ask", doc))

  @app.post("/recall")
  async def recall_post(request: Request, accept: str | None = Header(default=None)):
    form = await request.form()
    q = str(form.get("q") or "")
    doc = api.recall(q)
    if _wants_json(accept):
      return JSONResponse(doc)
    return HTMLResponse(_doc_html("Ask", doc))

  @app.get("/inbox")
  def inbox(accept: str | None = Header(default=None)):
    doc = api.inbox()
    if _wants_json(accept):
      return JSONResponse(doc)
    return HTMLResponse(_doc_html("Inbox", doc))

  @app.get("/find")
  def find(kind: str = "message", q: str = "", accept: str | None = Header(default=None)):
    if not q:
      return HTMLResponse(_html_page(
        "Find",
        """
        <h1>Find</h1>
        <form action="/find" method="get">
          <select name="kind">
            <option>person</option>
            <option>event</option>
            <option selected>message</option>
            <option>note</option>
            <option>file</option>
          </select>
          <input name="q" placeholder="Search">
          <button type="submit">Find</button>
        </form>
        """,
      ))
    doc = api.find(kind, q)
    if _wants_json(accept):
      return JSONResponse(doc)
    return HTMLResponse(_doc_html("Find", doc))

  @app.get("/doctor")
  def doctor(accept: str | None = Header(default=None)):
    result = api.doctor()
    if isinstance(result, tuple):
      doc, exit_code = result
      payload = {"exit_code": exit_code, **doc} if isinstance(doc, dict) else {"exit_code": exit_code, "doc": doc}
    else:
      payload = result
    if _wants_json(accept):
      return JSONResponse(payload)
    return HTMLResponse(_doc_html("Doctor", payload))

  # --- Mutation panels (plan 03.5) ------------------------------------
  # All mutations require an explicit ``confirm=on`` field in the POST
  # body. The matching GET endpoint renders the form with a visible
  # confirmation checkbox; the JSON-only /api endpoints require
  # ``confirm=true`` in the body. Without it, the handler returns 412
  # Precondition Failed with the same envelope shape the CLI emits.

  def _confirmation_required(command: str):
    return {
      "tool": "hugr",
      "command": command,
      "ok": False,
      "exit_code": 1,
      "error": {
        "code": "confirmation_required",
        "message": f"hugr {command} mutates state; include confirm=on/true.",
        "hint": "Tick the confirm box in the form, or include confirm=true in the POST body.",
      },
    }

  def _cross_origin_blocked(command: str):
    return {
      "tool": "hugr",
      "command": command,
      "ok": False,
      "exit_code": 1,
      "error": {
        "code": "cross_origin_blocked",
        "message": f"hugr {command} refused: cross-origin request.",
        "hint": "Submit the form from the hugr web UI on the same origin.",
      },
    }

  def _reject_cross_origin(request: Request, command: str, title: str, accept: str | None):
    """Return a 403 response when a mutation comes from another origin, else None."""
    if _origin_ok(request):
      return None
    doc = _cross_origin_blocked(command)
    if _wants_json(accept):
      return JSONResponse(doc, status_code=403)
    return HTMLResponse(_doc_html(title, doc), status_code=403)

  def _form_truthy(value: Any) -> bool:
    if isinstance(value, bool):
      return value
    if value is None:
      return False
    return str(value).strip().lower() in {"on", "true", "1", "yes"}

  def _send_form(action: str, fields: str) -> str:
    return _html_page(
      f"Send {action}",
      f"""
      <h1>Send {action}</h1>
      <form action="/send/{action}" method="post">
        {fields}
        <label><input type="checkbox" name="confirm" value="on" required> I confirm</label>
        <button type="submit">Send</button>
      </form>
      """,
    )

  @app.get("/send/mail")
  def send_mail_form():
    return HTMLResponse(_send_form(
      "mail",
      """
      <label>To (comma-separated)<br><input name="to" required></label><br><br>
      <label>Subject<br><input name="subject" required></label><br><br>
      <label>Body<br><textarea name="body" rows="6" required></textarea></label><br><br>
      <label>CC (optional)<br><input name="cc"></label><br><br>
      <label>BCC (optional)<br><input name="bcc"></label><br><br>
      <label><input type="checkbox" name="html"> Body is HTML</label><br><br>
      """,
    ))

  @app.post("/send/mail")
  async def send_mail_post(request: Request, accept: str | None = Header(default=None)):
    blocked = _reject_cross_origin(request, "send mail", "Send mail", accept)
    if blocked is not None:
      return blocked
    form = await request.form()
    if not _form_truthy(form.get("confirm")):
      doc = _confirmation_required("send mail")
      if _wants_json(accept):
        return JSONResponse(doc, status_code=412)
      return HTMLResponse(_doc_html("Send mail", doc), status_code=412)
    to_raw = str(form.get("to") or "")
    cc_raw = str(form.get("cc") or "")
    bcc_raw = str(form.get("bcc") or "")
    doc = api.send_mail(
      [s.strip() for s in to_raw.split(",") if s.strip()],
      str(form.get("subject") or ""),
      str(form.get("body") or ""),
      cc=[s.strip() for s in cc_raw.split(",") if s.strip()],
      bcc=[s.strip() for s in bcc_raw.split(",") if s.strip()],
      html=_form_truthy(form.get("html")),
    )
    status = 200 if doc.get("ok") else 502
    if _wants_json(accept):
      return JSONResponse(doc, status_code=status)
    return HTMLResponse(_doc_html("Send mail", doc), status_code=status)

  @app.get("/send/invite")
  def send_invite_form():
    return HTMLResponse(_send_form(
      "invite",
      """
      <label>Subject<br><input name="subject" required></label><br><br>
      <label>Date (today / tomorrow / YYYY-MM-DD)<br><input name="date"></label><br><br>
      <label>Start (HH:MM)<br><input name="start"></label><br><br>
      <label>End (HH:MM)<br><input name="end"></label><br><br>
      <label>Location<br><input name="location"></label><br><br>
      <label>Body<br><textarea name="body" rows="4"></textarea></label><br><br>
      <label>Category<br><input name="category"></label><br><br>
      """,
    ))

  @app.post("/send/invite")
  async def send_invite_post(request: Request, accept: str | None = Header(default=None)):
    blocked = _reject_cross_origin(request, "send invite", "Send invite", accept)
    if blocked is not None:
      return blocked
    form = await request.form()
    if not _form_truthy(form.get("confirm")):
      doc = _confirmation_required("send invite")
      if _wants_json(accept):
        return JSONResponse(doc, status_code=412)
      return HTMLResponse(_doc_html("Send invite", doc), status_code=412)

    def _opt(field: str) -> str | None:
      value = form.get(field)
      if value is None:
        return None
      text = str(value).strip()
      return text or None

    doc = api.send_invite(
      str(form.get("subject") or ""),
      date=_opt("date"),
      start=_opt("start"),
      end=_opt("end"),
      location=_opt("location"),
      body=_opt("body"),
      category=_opt("category"),
    )
    status = 200 if doc.get("ok") else 502
    if _wants_json(accept):
      return JSONResponse(doc, status_code=status)
    return HTMLResponse(_doc_html("Send invite", doc), status_code=status)

  @app.get("/remember")
  def remember_form():
    return HTMLResponse(_html_page(
      "Remember",
      """
      <h1>Remember</h1>
      <form action="/remember" method="post">
        <label>Fact<br><textarea name="fact" rows="3" required></textarea></label><br><br>
        <label>Type<br><input name="type" value="fact"></label><br><br>
        <label>Links (comma-separated)<br><input name="links"></label><br><br>
        <label><input type="checkbox" name="confirm" value="on" required> I confirm</label>
        <button type="submit">Remember</button>
      </form>
      """,
    ))

  @app.post("/remember")
  async def remember_post(request: Request, accept: str | None = Header(default=None)):
    blocked = _reject_cross_origin(request, "remember", "Remember", accept)
    if blocked is not None:
      return blocked
    form = await request.form()
    if not _form_truthy(form.get("confirm")):
      doc = _confirmation_required("remember")
      if _wants_json(accept):
        return JSONResponse(doc, status_code=412)
      return HTMLResponse(_doc_html("Remember", doc), status_code=412)
    links_raw = str(form.get("links") or "")
    doc = api.remember(
      str(form.get("fact") or ""),
      note_type=str(form.get("type") or "fact"),
      links=[s.strip() for s in links_raw.split(",") if s.strip()],
      yes=True,
    )
    status = 200 if doc.get("ok") else 502
    if _wants_json(accept):
      return JSONResponse(doc, status_code=status)
    return HTMLResponse(_doc_html("Remember", doc), status_code=status)

  @app.get("/session")
  def session_index(accept: str | None = Header(default=None)):
    doc = session_mod.status()
    if _wants_json(accept):
      return JSONResponse(doc)
    return HTMLResponse(_doc_html("Sessions", doc))

  @app.get("/session/{session_id}")
  def session_detail(session_id: str, accept: str | None = Header(default=None)):
    meta = session_mod.read_meta(session_id)
    doc = {
      "tool": "hugr",
      "command": "session detail",
      "ok": meta is not None,
      "session_id": session_id,
      "meta": meta.as_dict() if meta else None,
      "last_recall": session_mod.read_last_recall(session_id),
      "working_set": session_mod.read_working_set(session_id),
    }
    if _wants_json(accept):
      return JSONResponse(doc, status_code=200 if meta else 404)
    return HTMLResponse(_doc_html(f"Session {session_id}", doc), status_code=200 if meta else 404)

  # --- /api/* JSON-only mirror ----------------------------------------

  @app.get("/api/recall")
  def api_recall(q: str):
    return JSONResponse(api.recall(q))

  @app.get("/api/inbox")
  def api_inbox():
    return JSONResponse(api.inbox())

  @app.get("/api/find")
  def api_find(kind: str, q: str):
    return JSONResponse(api.find(kind, q))

  @app.get("/api/doctor")
  def api_doctor():
    result = api.doctor()
    if isinstance(result, tuple):
      doc, exit_code = result
      payload = {"exit_code": exit_code, **doc} if isinstance(doc, dict) else {"exit_code": exit_code, "doc": doc}
    else:
      payload = result
    return JSONResponse(payload)

  @app.get("/api/session")
  def api_session():
    return JSONResponse(session_mod.status())

  @app.get("/api/session/{session_id}")
  def api_session_detail(session_id: str):
    meta = session_mod.read_meta(session_id)
    doc = {
      "tool": "hugr",
      "command": "session detail",
      "ok": meta is not None,
      "session_id": session_id,
      "meta": meta.as_dict() if meta else None,
      "last_recall": session_mod.read_last_recall(session_id),
      "working_set": session_mod.read_working_set(session_id),
    }
    return JSONResponse(doc, status_code=200 if meta else 404)

  @app.get("/api/stream/ingest")
  async def api_stream_ingest(arg: list[str] = Query(default_factory=list)):
    return StreamingResponse(_stream_ingest(arg), media_type="text/event-stream")

  return app
