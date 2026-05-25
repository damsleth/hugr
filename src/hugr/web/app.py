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
import html
import json
from typing import Any, AsyncIterator

import hugr.api as api
from hugr import session as session_mod


def _wants_json(accept: str | None) -> bool:
  return bool(accept and "application/json" in accept.lower())


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
  proc = await asyncio.create_subprocess_exec(
    "hugr", "ingest", *args, "--json",
    stdout=asyncio.subprocess.PIPE,
    stderr=asyncio.subprocess.PIPE,
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


def create_app():
  try:
    from fastapi import FastAPI, Header, Request
    from fastapi.responses import HTMLResponse, JSONResponse, StreamingResponse
  except ImportError as exc:  # pragma: no cover - exercised by CLI fallback
    raise RuntimeError(
      'web extra not installed; pipx install "hugr-cli[web]"'
    ) from exc

  app = FastAPI(title="hugr", version="0.1")

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

  from fastapi import Query

  @app.get("/api/stream/ingest")
  async def api_stream_ingest(arg: list[str] = Query(default_factory=list)):
    return StreamingResponse(_stream_ingest(arg), media_type="text/event-stream")

  return app
