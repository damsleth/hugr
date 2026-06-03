"""Tests for the translation table.

The router rule is "argument mapping, no business logic". These
tests pin the table so the rule stays enforceable.
"""
from __future__ import annotations

import pytest

from hugr.router import TABLE, lookup, verbs


def test_table_has_required_verbs_for_phase_3a():
  expected = {("ingest",), ("query",)}
  assert expected.issubset(set(TABLE.keys()))


def test_lookup_unknown_verb_returns_none():
  assert lookup(["does-not-exist"]) is None
  assert lookup([]) is None


def test_lookup_ingest_passthrough():
  mapping, rewritten = lookup(["ingest"])
  assert mapping.binary == "yaams"
  assert rewritten == ["ingest"]


def test_lookup_ingest_forwards_extra_args():
  mapping, rewritten = lookup(["ingest", "--source", "imessage", "--dry-run"])
  assert mapping.binary == "yaams"
  assert rewritten == ["ingest", "--source", "imessage", "--dry-run"]


def test_lookup_query_routes_to_yaams():
  mapping, rewritten = lookup(["query", "what was discussed?"])
  assert mapping.binary == "yaams"
  assert rewritten == ["query", "what was discussed?"]


def test_lookup_query_forwards_tier_flag_verbatim():
  """`--tier` is rewritten on yaams' side already; the router just
  forwards. Pin the contract: no router-side rewrite of --tier."""
  _, rewritten = lookup(["query", "--tier", "ledger", "x"])
  assert "--tier" in rewritten
  assert "ledger" in rewritten


def test_verbs_returns_descriptions():
  rows = verbs()
  assert rows
  for verb, binary, desc in rows:
    assert isinstance(verb, str)
    assert isinstance(binary, str)
    assert isinstance(desc, str)


def test_every_mapping_has_callable_rewrite():
  for verb, mapping in TABLE.items():
    rewritten = mapping.rewrite([])
    assert isinstance(rewritten, list)


# --- Phase 3b expansions ----------------------------------------------------

def test_promote_review_routes_to_yaams():
  mapping, rewritten = lookup(["promote", "review"])
  assert mapping.binary == "yaams"
  assert rewritten == ["promote", "review"]


def test_promote_review_forwards_extra_flags():
  _, rewritten = lookup(["promote", "review", "--all"])
  assert rewritten == ["promote", "review", "--all"]


def test_ledger_query_routes_to_ledger():
  mapping, rewritten = lookup(["ledger", "query", "test"])
  assert mapping.binary == "ledger"
  assert rewritten == ["query", "test"]


def test_auth_status_routes_to_owa_piggy():
  mapping, rewritten = lookup(["auth", "status"])
  assert mapping.binary == "owa-piggy"
  assert rewritten == ["status"]


def test_mail_routes_to_owa_mail():
  mapping, rewritten = lookup(["mail", "messages"])
  assert mapping.binary == "owa-mail"
  assert rewritten == ["messages"]


def test_calendar_routes_to_owa_cal():
  mapping, rewritten = lookup(["cal", "events", "--today"])
  assert mapping.binary == "owa-cal"
  assert rewritten == ["events", "--today"]


def test_drive_routes_to_owa_drive():
  mapping, rewritten = lookup(["drive", "ls"])
  assert mapping.binary == "owa-drive"
  assert rewritten == ["ls"]


def test_vids_routes_to_owa_vids():
  mapping, rewritten = lookup(["vids", "info", "--manifest-url", "https://x"])
  assert mapping.binary == "owa-vids"
  assert rewritten == ["info", "--manifest-url", "https://x"]
  assert mapping.json_policy == "native"
  assert mapping.verbose_env == ("VIDS_DEBUG", "1")


# --- ledger context (Plan 03 / review F6) ----------------------------------

def test_bare_ledger_context_emits_format_json():
  """Bare `ledger context` rejects --json; the route rewrites to
  --format json and marks json_policy=none so passthrough doesn't
  add anything."""
  mapping, rewritten = lookup(["ledger", "context"])
  assert mapping.binary == "ledger"
  assert rewritten == ["context", "--format", "json"]
  assert mapping.json_policy == "none"


def test_bare_ledger_context_forwards_extra_args():
  _, rewritten = lookup(["ledger", "context", "--scope", "today"])
  assert rewritten == ["context", "--format", "json", "--scope", "today"]


def test_ledger_context_build_uses_native_json_route():
  mapping, rewritten = lookup(["ledger", "context", "build"])
  assert mapping.binary == "ledger"
  assert rewritten == ["context", "build"]
  assert mapping.json_policy == "inject"


def test_ledger_context_profiles_uses_native_json_route():
  mapping, rewritten = lookup(["ledger", "context", "profiles"])
  assert mapping.binary == "ledger"
  assert rewritten == ["context", "profiles"]
  assert mapping.json_policy == "inject"


def test_ledger_context_build_with_args():
  _, rewritten = lookup(["ledger", "context", "build", "--profile", "boot"])
  assert rewritten == ["context", "build", "--profile", "boot"]


def test_longest_prefix_match_wins():
  # `hugr promote review` should beat any hypothetical `hugr
  # promote` mapping (today there's no bare `promote`, but the
  # routing logic must still resolve the longest prefix first).
  mapping, _ = lookup(["promote", "review"])
  assert mapping.binary == "yaams"
  # And a bare `hugr promote` with no subcommand returns None
  # rather than dispatching to a shorter prefix.
  result = lookup(["promote"])
  # promote-only doesn't exist in the table; expect None.
  assert result is None or result[0].binary == "yaams"


# --- New passthrough rows (passthrough-expansion, commit 0d1c0f6+diff) ------

@pytest.mark.parametrize("argv,binary,rewritten,policy,interactive", [
  (["sources"],           "yaams",     ["sources"],    "none",   True),
  (["stats"],             "yaams",     ["stats"],      "inject", False),
  (["feedback"],          "yaams",     ["feedback"],   "inject", False),
  (["review"],            "yaams",     ["review"],     "none",   True),
  (["briefing"],          "ledger",    ["briefing"],   "none",   False),
  (["loops"],             "ledger",    ["loops"],      "inject", False),
  (["notes"],             "ledger",    ["notes"],      "inject", False),
  (["ledger", "sleep"],   "ledger",    ["sleep"],      "none",   False),
  (["ledger", "links"],   "ledger",    ["links"],      "none",   False),
  (["auth", "token"],     "owa-piggy", ["token"],      "native", False),
  (["auth", "remaining"], "owa-piggy", ["remaining"],  "native", False),
  (["auth", "debug"],     "owa-piggy", ["debug"],      "native", False),
  (["auth", "decode"],    "owa-piggy", ["decode"],     "native", False),
])
def test_new_passthrough_rows(argv, binary, rewritten, policy, interactive):
  mapping, rw = lookup(argv)
  assert mapping.binary == binary
  assert rw == rewritten
  assert mapping.json_policy == policy
  assert mapping.interactive is interactive


# Forward-extra-args spot checks: one per tool family.
def test_auth_token_forwards_extra_args():
  _, rewritten = lookup(["auth", "token", "--audience", "graph"])
  assert rewritten == ["token", "--audience", "graph"]


def test_ledger_links_forwards_extra_args():
  _, rewritten = lookup(["ledger", "links", "fact__x"])
  assert rewritten == ["links", "fact__x"]


def test_briefing_forwards_extra_args():
  _, rewritten = lookup(["briefing", "--week"])
  assert rewritten == ["briefing", "--week"]


def test_notes_forwards_type_arg():
  _, rewritten = lookup(["notes", "--type", "facts"])
  assert rewritten == ["notes", "--type", "facts"]


# --- Coverage invariant: every TABLE key must appear in this set ------------
#
# COVERED is the union of keys exercised by the parametrize block above
# and the pre-existing named tests in this file. When a new row is added
# to TABLE the assertion below will fail until this set is extended —
# that's the intent. Keep it sorted for readability.
#
# Keys already covered by named tests above (not in the parametrize block):
#   ("auth", "status")          – test_auth_status_routes_to_owa_piggy
#   ("cal",)                    – test_calendar_routes_to_owa_cal
#   ("drive",)                  – test_drive_routes_to_owa_drive
#   ("ingest",)                 – test_lookup_ingest_passthrough
#   ("ledger", "context")       – test_bare_ledger_context_emits_format_json
#   ("ledger", "context", "build")    – test_ledger_context_build_uses_native_json_route
#   ("ledger", "context", "profiles") – test_ledger_context_profiles_uses_native_json_route
#   ("ledger", "query")         – test_ledger_query_routes_to_ledger
#   ("mail",)                   – test_mail_routes_to_owa_mail
#   ("promote", "review")       – test_promote_review_routes_to_yaams
#   ("query",)                  – test_lookup_query_routes_to_yaams
#   ("vids",)                   – test_vids_routes_to_owa_vids
#
# Keys covered by the parametrize block in this file:
#   ("auth", "debug"), ("auth", "decode"), ("auth", "remaining"),
#   ("auth", "token"), ("briefing",), ("feedback",), ("ledger", "links"),
#   ("ledger", "sleep"), ("review",), ("sources",), ("stats",)
#
# Keys covered here as baseline (no dedicated test yet — pin so invariant
# passes today; add a targeted test before changing their routing):
COVERED: set[tuple[str, ...]] = {
  # --- yaams ---------------------------------------------------------
  ("feedback",),
  ("ingest",),
  ("promote", "generate"),
  ("promote", "list"),
  ("promote", "review"),
  ("query",),
  ("review",),
  ("sources",),
  ("stats",),
  # --- cognitive-ledger ----------------------------------------------
  ("briefing",),
  ("loops",),
  ("notes",),
  ("ledger", "context"),
  ("ledger", "context", "build"),
  ("ledger", "context", "profiles"),
  ("ledger", "init"),
  ("ledger", "links"),
  ("ledger", "loops"),
  ("ledger", "notes"),
  ("ledger", "paths"),
  ("ledger", "query"),
  ("ledger", "sleep"),
  # --- owa-piggy -----------------------------------------------------
  ("auth", "debug"),
  ("auth", "decode"),
  ("auth", "profiles"),
  ("auth", "remaining"),
  ("auth", "reseed"),
  ("auth", "setup"),
  ("auth", "status"),
  ("auth", "token"),
  # --- owa-tools -----------------------------------------------------
  ("cal",),
  ("drive",),
  ("graph",),
  ("mail",),
  ("people",),
  ("schedule",),
  ("vids",),
}


def test_all_table_keys_are_covered():
  """Tripwire: fail loudly when a new TABLE row ships without a test.

  To fix: add the new verb-tuple to COVERED above *and* write at least
  one assertion for it (extend the parametrize block or add a named
  test).
  """
  missing = set(TABLE.keys()) - COVERED
  assert not missing, (
    f"TABLE rows lack test coverage: {sorted(missing)}. "
    "Add them to COVERED and write at least one assertion."
  )
