"""Unit tests for the session store (Issue #16).

Pure-Python; imports src/session_store.py directly against a temp SQLite DB. Runs under pytest
and standalone.
"""
import json
import os
import sys
import tempfile

_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_SRC = os.path.join(_REPO_ROOT, "src")
for _p in (_SRC, _REPO_ROOT):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import session_store as ss  # noqa: E402


def _db():
    d = tempfile.mkdtemp(prefix="ss_")
    p = os.path.join(d, "s.db")
    os.environ["OMEGACLAW_SESSION_DB"] = p
    ss.reset(p)
    return p


def _clean():
    os.environ.pop("OMEGACLAW_SESSION_DB", None)


def test_record_and_show():
    _db()
    try:
        ss.begin_session("s1", provider="Test", channel="irc", task="deploy widget")
        ss.record_message("s1", 1, "user", "deploy the widget service")
        ss.record_tool_call("s1", 1, "shell", "make build", "build ok", True)
        ss.end_session("s1", "done")
        r = ss.show("s1")
        assert r["ok"] and r["session"]["task"] == "deploy widget"
        assert len(r["messages"]) == 1 and len(r["tool_calls"]) == 1
    finally:
        _clean()


def test_search_finds_relevant_session():
    _db()
    try:
        ss.begin_session("s1", task="deploy the widget service")
        ss.record_message("s1", 1, "user", "widget deployment to staging")
        ss.begin_session("s2", task="write quarterly report")
        ss.record_message("s2", 1, "user", "finance numbers")
        assert ss.search("widget")[0]["session_id"] == "s1"
        assert ss.search("quarterly")[0]["session_id"] == "s2"
        assert ss.search("nonexistent-term-xyz") == []
    finally:
        _clean()


def test_resume_reconstructs_state():
    _db()
    try:
        ss.begin_session("s1", task="deploy widget")
        ss.record_message("s1", 2, "assistant", "build finished, deploying next")
        ss.record_snapshot("s1", 2, {"task": "deploy widget", "step": "built", "next": "deploy"})
        ss.end_session("s1", "interrupted")
        r = ss.resume("s1")
        assert r["ok"] and r["latest_snapshot"]["next"] == "deploy" and r["resume_turn"] == 2
        assert any("deploying" in m["text"] for m in r["recent_messages"])
    finally:
        _clean()


def test_content_persisted_verbatim_in_search_show_export():
    _db()
    try:
        ss.begin_session("s1", task="use the deploy pipeline")
        ss.record_message("s1", 1, "assistant", "message body alpha")
        ss.record_tool_call("s1", 1, "shell", "echo alpha", "done")
        ss.record_snapshot("s1", 1, {"note": "snapshot beta"})
        blob = json.dumps(ss.export("s1")) + json.dumps(ss.show("s1")) + json.dumps(ss.search("deploy"))
        for kept in ("message body alpha", "echo alpha", "snapshot beta"):
            assert kept in blob, kept
    finally:
        _clean()


def test_ingest_trace():
    _db()
    try:
        trace = os.path.join(tempfile.mkdtemp(), "t.jsonl")
        with open(trace, "w", encoding="utf-8") as f:
            f.write(json.dumps({"session_id": "tr1", "iteration": 1, "phase": "input", "input": "do X"}) + "\n")
            f.write(json.dumps({"session_id": "tr1", "iteration": 1, "phase": "llm", "response": "doing X"}) + "\n")
            f.write(json.dumps({"session_id": "tr1", "iteration": 1, "phase": "result", "result_text": "X done"}) + "\n")
        r = ss.ingest_trace(trace)
        assert r["ok"] and r["sessions"] == 1
        assert ss.show("tr1")["ok"] and ss.search("doing X")[0]["session_id"] == "tr1"
    finally:
        _clean()


def test_meta_persisted_in_show_and_export():
    """begin_session meta is persisted + exported verbatim and round-trips through show/export."""
    _db()
    try:
        ss.begin_session("s1", task="t", meta={
            "env": "prod",
            "nested": {"region": "eu-west"}})
        blob = json.dumps(ss.export("s1")) + json.dumps(ss.show("s1"))
        assert "prod" in blob and "eu-west" in blob
    finally:
        _clean()


def test_reused_session_id_clears_stale_rows():
    """Regression (PR #40 review): a reused/collided session id must not carry stale
    transcript/search content into the new session (no FK cascades)."""
    _db()
    try:
        ss.begin_session("same", task="old")
        ss.record_message("same", 1, "user", "zebrafishtoken")
        ss.record_tool_call("same", 1, "shell", "oldcmd", "oldresult", True)
        ss.record_snapshot("same", 1, {"old": "state"})
        # restart the same id
        ss.begin_session("same", task="new")
        ss.record_message("same", 1, "user", "dolphincontent")
        shown = ss.show("same")
        assert [m["text"] for m in shown["messages"]] == ["dolphincontent"]
        assert shown["tool_calls"] == []                       # old tool call gone
        assert ss.resume("same")["latest_snapshot"] is None    # old snapshot gone
        assert ss.search("zebrafishtoken") == []               # old search row gone
        assert ss.search("dolphincontent")[0]["session_id"] == "same"
    finally:
        _clean()


def test_ingest_real_tracing_trace():
    """Ingest must handle the reasoning-trace JSONL phases (iteration_start / llm_call /
    action_parse / policy_decision / iteration_result), producing searchable summaries even
    without bodies. The trace JSONL is written directly here (matching the documented format
    src.tracing emits) so this test stays independent of the separate tracing module."""
    d = tempfile.mkdtemp()
    trace = os.path.join(d, "tr.jsonl")
    _db()
    try:
        records = [
            {"session_id": "run-1", "iteration": 1, "phase": "iteration_start", "input_body": "deploy the widget service"},
            {"session_id": "run-1", "iteration": 1, "phase": "llm_call", "provider": "Anthropic", "model": "claude-opus", "response_chars": 1},
            {"session_id": "run-1", "iteration": 1, "phase": "action_parse", "source": "json", "ok": True, "tools": ["shell", "send"]},
            {"session_id": "run-1", "iteration": 1, "phase": "policy_decision", "tool": "shell", "risk": "high", "reason": "ok", "allowed": True},
            {"session_id": "run-1", "iteration": 1, "phase": "iteration_result", "result_chars": 16},
        ]
        with open(trace, "w", encoding="utf-8") as f:
            for rec in records:
                f.write(json.dumps(rec) + "\n")

        r = ss.ingest_trace(trace)
        assert r["ok"] and r["sessions"] == 1
        shown = ss.show("run-1")
        assert shown["ok"] and shown["messages"], "ingest produced no messages"
        assert shown["tool_calls"], "ingest produced no tool calls"
        # searchable by tool name and provider even though bodies were not recorded
        assert ss.search("shell")[0]["session_id"] == "run-1"
        assert ss.search("Anthropic")[0]["session_id"] == "run-1"
        assert shown["session"]["provider"] == "Anthropic"
    finally:
        _clean()


def test_list_and_missing_session():
    _db()
    try:
        ss.begin_session("s1", task="a")
        ss.begin_session("s2", task="b")
        assert {s["id"] for s in ss.list_sessions()} == {"s1", "s2"}
        assert ss.show("nope")["ok"] is False and ss.resume("nope")["ok"] is False
    finally:
        _clean()


if __name__ == "__main__":
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_") and callable(v)]
    failed = 0
    for fn in fns:
        try:
            fn()
            print("ok:", fn.__name__)
        except AssertionError as e:
            failed += 1
            print("FAIL:", fn.__name__, e)
    if failed:
        sys.exit(1)
    print(f"\nAll {len(fns)} session_store tests passed")
