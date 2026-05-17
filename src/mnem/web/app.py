"""FastAPI web surface for mnem.

The web layer is a thin serializer over ``mnem.api``. It owns HTTP and
HTML rendering only; suite orchestration stays in the API module.
"""

from __future__ import annotations

import html
from typing import Any

import mnem.api as api


def _wants_json(accept: str | None) -> bool:
  return bool(accept and "application/json" in accept.lower())


def _html_page(title: str, body: str) -> str:
  return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{html.escape(title)} - mnem</title>
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
  </nav>
  {body}
</body>
</html>"""


def _doc_html(title: str, doc: dict[str, Any]) -> str:
  import json

  escaped = html.escape(json.dumps(doc, ensure_ascii=False, indent=2))
  return _html_page(title, f"<h1>{html.escape(title)}</h1><pre>{escaped}</pre>")


def create_app():
  try:
    from fastapi import FastAPI, Header, Request
    from fastapi.responses import HTMLResponse, JSONResponse
  except ImportError as exc:  # pragma: no cover - exercised by CLI fallback
    raise RuntimeError(
      'web extra not installed; pipx install "mnem-suite[web]"'
    ) from exc

  app = FastAPI(title="mnem", version="0.1")

  @app.get("/healthz")
  def healthz():
    return {"ok": True, "tool": "mnem"}

  @app.get("/", response_class=HTMLResponse)
  def root(q: str = "", accept: str | None = Header(default=None)):
    if q:
      doc = api.ask(q)
      if _wants_json(accept):
        return JSONResponse(doc)
      return HTMLResponse(_doc_html("Ask", doc))
    return HTMLResponse(_html_page(
      "Ask",
      """
      <h1>Ask</h1>
      <form action="/ask" method="get">
        <input name="q" autofocus placeholder="Ask mnem">
        <button type="submit">Ask</button>
      </form>
      """,
    ))

  @app.get("/ask")
  def ask(q: str, accept: str | None = Header(default=None)):
    doc = api.ask(q)
    if _wants_json(accept):
      return JSONResponse(doc)
    return HTMLResponse(_doc_html("Ask", doc))

  @app.post("/ask")
  async def ask_post(request: Request, accept: str | None = Header(default=None)):
    form = await request.form()
    q = str(form.get("q") or "")
    doc = api.ask(q)
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
    doc, exit_code = api.doctor()
    payload = {"exit_code": exit_code, **doc}
    if _wants_json(accept):
      return JSONResponse(payload)
    return HTMLResponse(_doc_html("Doctor", payload))

  @app.get("/session/{session_id}")
  def session(session_id: str, accept: str | None = Header(default=None)):
    doc = {"tool": "mnem", "command": "session", "session_id": session_id, "status": "not_implemented"}
    if _wants_json(accept):
      return JSONResponse(doc)
    return HTMLResponse(_doc_html("Session", doc))

  return app
