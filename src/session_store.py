"""Session persistence, transcript search & resumable snapshots (Issue #16).

OmegaClaw has raw logs + `history.metta`, but no user-facing session database to ask "where did
we leave off?", search prior decisions, compare runs, or resume interrupted work without parsing
logs. This adds a queryable **SQLite** store with **full-text search** and **resumable
snapshots**.

Design:
- stdlib ``sqlite3``; a small schema (sessions / messages / tool_calls / snapshots) plus an FTS5
  search index (transparent LIKE fallback if FTS5 is unavailable).
- Two ingestion paths:
  1. a live **recording API** (``begin_session`` / ``record_message`` / ``record_tool_call`` /
     ``record_snapshot`` / ``end_session``) — the integration surface the reasoning loop calls to
     record a session as it runs (wiring lands as a follow-up; see the PR notes);
  2. ``ingest_trace``, which backfills from the reasoning-trace JSONL emitted by ``src.tracing``.
     That module is introduced by PR #270 (``contrib/reasoning-trace``); this PR is stacked on it,
     so ``ingest_trace`` becomes live once #270 merges. Until then the store is exercised directly
     via the recording API (see the unit tests).
- **Resume** returns the latest snapshot + recent context — reconstructed state independent of
  the raw prompt log.

DB path: ``OMEGACLAW_SESSION_DB`` (default ``<repo>/memory/sessions.db``, a runtime file).
"""

from __future__ import annotations

import json
import os
import sqlite3
import time
from typing import Any, Dict, List, Optional

_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

_SCHEMA = """
CREATE TABLE IF NOT EXISTS sessions (
    id TEXT PRIMARY KEY, started_at REAL, ended_at REAL, provider TEXT, channel TEXT,
    task TEXT, status TEXT, turns INTEGER DEFAULT 0, meta TEXT
);
CREATE TABLE IF NOT EXISTS messages (
    id INTEGER PRIMARY KEY AUTOINCREMENT, session_id TEXT, turn INTEGER, role TEXT,
    text TEXT, ts REAL
);
CREATE TABLE IF NOT EXISTS tool_calls (
    id INTEGER PRIMARY KEY AUTOINCREMENT, session_id TEXT, turn INTEGER, tool TEXT,
    args TEXT, result TEXT, ok INTEGER, ts REAL
);
CREATE TABLE IF NOT EXISTS snapshots (
    id INTEGER PRIMARY KEY AUTOINCREMENT, session_id TEXT, turn INTEGER, state TEXT, ts REAL
);
CREATE INDEX IF NOT EXISTS idx_messages_session ON messages(session_id);
CREATE INDEX IF NOT EXISTS idx_tool_session ON tool_calls(session_id);
CREATE INDEX IF NOT EXISTS idx_snap_session ON snapshots(session_id);
"""


def db_path() -> str:
    env = os.environ.get("OMEGACLAW_SESSION_DB")
    if env:
        return env if os.path.isabs(env) else os.path.join(_REPO_ROOT, env)
    return os.path.join(_REPO_ROOT, "memory", "sessions.db")


_HAS_FTS: Dict[str, bool] = {}


def connect(path: Optional[str] = None) -> sqlite3.Connection:
    p = path or db_path()
    if p != ":memory:":
        os.makedirs(os.path.dirname(p), exist_ok=True)
    conn = sqlite3.connect(p)
    conn.row_factory = sqlite3.Row
    conn.executescript(_SCHEMA)
    # FTS5 search index over all searchable content; LIKE fallback if unavailable.
    if p not in _HAS_FTS:
        try:
            conn.execute("CREATE VIRTUAL TABLE IF NOT EXISTS search_fts USING fts5("
                         "session_id UNINDEXED, kind UNINDEXED, content)")
            _HAS_FTS[p] = True
        except sqlite3.OperationalError:
            conn.execute("CREATE TABLE IF NOT EXISTS search_like ("
                         "session_id TEXT, kind TEXT, content TEXT)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_like_session ON search_like(session_id)")
            _HAS_FTS[p] = False
    conn.commit()
    return conn


def _has_fts(conn: sqlite3.Connection) -> bool:
    return _HAS_FTS.get(_conn_path(conn), True)


def _conn_path(conn: sqlite3.Connection) -> str:
    try:
        for _seq, name, fname in conn.execute("PRAGMA database_list"):
            if name == "main":
                return fname or ":memory:"
    except sqlite3.Error:
        pass
    return db_path()


def _clear_session_rows(conn: sqlite3.Connection, session_id: str) -> None:
    """Drop all dependent rows for a session id (messages/tool_calls/snapshots/search index).

    There are no FK cascades, so a reused/collided id must be cleared explicitly — otherwise
    stale transcript/search content bleeds into the new session (a correctness + privacy issue,
    PR #40 review)."""
    for tbl in ("messages", "tool_calls", "snapshots"):
        conn.execute("DELETE FROM {} WHERE session_id=?".format(tbl), (session_id,))
    if _has_fts(conn):
        # FTS5 ignores DELETE ... WHERE <unindexed col>; delete by rowid instead.
        rowids = [r[0] for r in conn.execute(
            "SELECT rowid FROM search_fts WHERE session_id=?", (session_id,)).fetchall()]
        for rid in rowids:
            conn.execute("DELETE FROM search_fts WHERE rowid=?", (rid,))
    else:
        conn.execute("DELETE FROM search_like WHERE session_id=?", (session_id,))


def _index(conn: sqlite3.Connection, session_id: str, kind: str, content: str) -> None:
    content = content or ""
    if _has_fts(conn):
        conn.execute("INSERT INTO search_fts(session_id, kind, content) VALUES (?,?,?)",
                     (session_id, kind, content))
    else:
        conn.execute("INSERT INTO search_like(session_id, kind, content) VALUES (?,?,?)",
                     (session_id, kind, content))


# --------------------------------------------------------------------------- recording API

def begin_session(session_id: str, *, provider: str = "", channel: str = "", task: str = "",
                  meta: Optional[Dict[str, Any]] = None, conn: Optional[sqlite3.Connection] = None) -> str:
    own = conn is None
    conn = conn or connect()
    try:
        # begin = a FRESH session: clear any prior rows for a reused/collided id so stale
        # transcript/search content can't bleed in (replace semantics), transactionally.
        _clear_session_rows(conn, session_id)
        meta_str = json.dumps(meta or {}, ensure_ascii=False)
        conn.execute(
            "INSERT OR REPLACE INTO sessions(id, started_at, ended_at, provider, channel, task, "
            "status, turns, meta) VALUES (?,?,?,?,?,?,?,?,?)",
            (session_id, time.time(), None, provider, channel, task or "",
             "active", 0, meta_str))
        _index(conn, session_id, "task", task or "")
        conn.commit()
    finally:
        if own:
            conn.close()
    return session_id


def record_message(session_id: str, turn: int, role: str, text: str,
                   conn: Optional[sqlite3.Connection] = None) -> None:
    own = conn is None
    conn = conn or connect()
    try:
        conn.execute("INSERT INTO messages(session_id, turn, role, text, ts) VALUES (?,?,?,?,?)",
                     (session_id, turn, role, text or "", time.time()))
        _index(conn, session_id, "message", "{}: {}".format(role, text or ""))
        conn.execute("UPDATE sessions SET turns = MAX(turns, ?) WHERE id=?", (turn, session_id))
        conn.commit()
    finally:
        if own:
            conn.close()


def record_tool_call(session_id: str, turn: int, tool: str, args: str = "", result: str = "",
                     ok: bool = True, conn: Optional[sqlite3.Connection] = None) -> None:
    own = conn is None
    conn = conn or connect()
    try:
        conn.execute("INSERT INTO tool_calls(session_id, turn, tool, args, result, ok, ts) "
                     "VALUES (?,?,?,?,?,?,?)",
                     (session_id, turn, tool, args or "",
                      result or "", 1 if ok else 0, time.time()))
        _index(conn, session_id, "tool", "{} {} {}".format(tool, args or "", result or ""))
        conn.commit()
    finally:
        if own:
            conn.close()


def record_snapshot(session_id: str, turn: int, state: Dict[str, Any],
                    conn: Optional[sqlite3.Connection] = None) -> None:
    """Persist a resumable context snapshot. Independent of raw prompt logs."""
    own = conn is None
    conn = conn or connect()
    try:
        blob = json.dumps(state, ensure_ascii=False)
        conn.execute("INSERT INTO snapshots(session_id, turn, state, ts) VALUES (?,?,?,?)",
                     (session_id, turn, blob, time.time()))
        conn.commit()
    finally:
        if own:
            conn.close()


def end_session(session_id: str, status: str = "done", conn: Optional[sqlite3.Connection] = None) -> None:
    own = conn is None
    conn = conn or connect()
    try:
        conn.execute("UPDATE sessions SET ended_at=?, status=? WHERE id=?",
                     (time.time(), status, session_id))
        conn.commit()
    finally:
        if own:
            conn.close()


# --------------------------------------------------------------------------- query API

def list_sessions(limit: int = 50, conn: Optional[sqlite3.Connection] = None) -> List[Dict[str, Any]]:
    own = conn is None
    conn = conn or connect()
    try:
        rows = conn.execute(
            "SELECT id, started_at, ended_at, provider, channel, task, status, turns "
            "FROM sessions ORDER BY started_at DESC LIMIT ?", (limit,)).fetchall()
        return [dict(r) for r in rows]
    finally:
        if own:
            conn.close()


def search(query: str, limit: int = 5, conn: Optional[sqlite3.Connection] = None) -> List[Dict[str, Any]]:
    """Full-text search over sessions; returns the most relevant sessions (id + task + snippet)."""
    own = conn is None
    conn = conn or connect()
    try:
        results: List[Dict[str, Any]] = []
        seen = set()
        if _has_fts(conn):
            try:
                rows = conn.execute(
                    "SELECT session_id, content FROM search_fts WHERE search_fts MATCH ? "
                    "ORDER BY rank LIMIT ?", (_fts_query(query), limit * 4)).fetchall()
            except sqlite3.OperationalError:
                rows = []
        else:
            rows = conn.execute(
                "SELECT session_id, content FROM search_like WHERE content LIKE ? LIMIT ?",
                ("%" + query + "%", limit * 4)).fetchall()
        for r in rows:
            sid = r["session_id"]
            if sid in seen:
                continue
            seen.add(sid)
            srow = conn.execute("SELECT id, task, status, started_at FROM sessions WHERE id=?",
                                (sid,)).fetchone()
            if srow:
                results.append({"session_id": sid, "task": srow["task"], "status": srow["status"],
                                "snippet": (r["content"] or "")[:160]})
            if len(results) >= limit:
                break
        return results
    finally:
        if own:
            conn.close()


def _fts_query(query: str) -> str:
    """Turn a free-text query into a safe FTS5 MATCH (prefix-OR of the terms)."""
    terms = [t for t in "".join(c if (c.isalnum() or c.isspace()) else " " for c in query).split() if t]
    if not terms:
        return '""'
    return " OR ".join('"{}"*'.format(t) for t in terms)


def show(session_id: str, conn: Optional[sqlite3.Connection] = None) -> Dict[str, Any]:
    own = conn is None
    conn = conn or connect()
    try:
        s = conn.execute("SELECT * FROM sessions WHERE id=?", (session_id,)).fetchone()
        if not s:
            return {"ok": False, "error": "no such session: {}".format(session_id)}
        msgs = conn.execute("SELECT turn, role, text FROM messages WHERE session_id=? ORDER BY id",
                            (session_id,)).fetchall()
        tools = conn.execute("SELECT turn, tool, args, result, ok FROM tool_calls WHERE session_id=? "
                             "ORDER BY id", (session_id,)).fetchall()
        return {"ok": True, "session": dict(s), "messages": [dict(m) for m in msgs],
                "tool_calls": [dict(t) for t in tools]}
    finally:
        if own:
            conn.close()


def resume(session_id: str, recent: int = 5, conn: Optional[sqlite3.Connection] = None) -> Dict[str, Any]:
    """Reconstruct enough state to continue: the latest snapshot + recent messages/tool calls."""
    own = conn is None
    conn = conn or connect()
    try:
        s = conn.execute("SELECT id, task, status, turns FROM sessions WHERE id=?",
                         (session_id,)).fetchone()
        if not s:
            return {"ok": False, "error": "no such session: {}".format(session_id)}
        snap = conn.execute("SELECT turn, state FROM snapshots WHERE session_id=? "
                            "ORDER BY id DESC LIMIT 1", (session_id,)).fetchone()
        msgs = conn.execute("SELECT turn, role, text FROM messages WHERE session_id=? "
                            "ORDER BY id DESC LIMIT ?", (session_id, recent)).fetchall()
        tools = conn.execute("SELECT turn, tool, result, ok FROM tool_calls WHERE session_id=? "
                             "ORDER BY id DESC LIMIT ?", (session_id, recent)).fetchall()
        state = None
        if snap:
            try:
                state = json.loads(snap["state"])
            except (ValueError, TypeError):
                state = {"raw": snap["state"]}
        return {"ok": True, "session_id": session_id, "task": s["task"], "status": s["status"],
                "turns": s["turns"], "latest_snapshot": state,
                "resume_turn": snap["turn"] if snap else (s["turns"] or 0),
                "recent_messages": [dict(m) for m in reversed(msgs)],
                "recent_tool_calls": [dict(t) for t in reversed(tools)]}
    finally:
        if own:
            conn.close()


def export(session_id: str, conn: Optional[sqlite3.Connection] = None) -> Dict[str, Any]:
    """Full session export (JSON-serializable)."""
    data = show(session_id, conn=conn)
    if not data.get("ok"):
        return data
    own = conn is None
    conn = conn or connect()
    try:
        snaps = conn.execute("SELECT turn, state, ts FROM snapshots WHERE session_id=? ORDER BY id",
                             (session_id,)).fetchall()
        data["snapshots"] = [dict(s) for s in snaps]
        return data
    finally:
        if own:
            conn.close()


# --------------------------------------------------------------------------- trace ingest

def ingest_trace(path: str, conn: Optional[sqlite3.Connection] = None) -> Dict[str, Any]:
    """Backfill sessions from a reasoning-trace JSONL (the format ``src.tracing`` emits).

    ``src.tracing`` is introduced by PR #270 (``contrib/reasoning-trace``); this function reads the
    JSONL that module writes, so it is only reachable end-to-end once #270 is merged underneath.

    Maps the ACTUAL tracing phases — ``iteration_start`` / ``llm_call`` / ``action_parse`` /
    ``policy_decision`` / ``iteration_result`` / ``error`` / ``iteration_end`` — into messages +
    tool calls. Produces useful **searchable summaries even without bodies** (tool names,
    provider/model, result size, error codes); when ``OMEGACLAW_TRACE_BODIES`` was set, the
    prompt/response/result/failed-action bodies are ingested too. Best-effort per line.
    """
    own = conn is None
    conn = conn or connect()
    ingested = set()
    n = 0
    try:
        with open(path, encoding="utf-8", errors="replace") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    ev = json.loads(line)
                except ValueError:
                    continue
                sid = ev.get("session_id")
                if not sid:
                    continue
                if sid not in ingested:
                    begin_session(sid, task="(ingested from trace)", conn=conn)
                    ingested.add(sid)
                turn = ev.get("iteration") or ev.get("turn_id") or 0
                phase = ev.get("phase")

                if phase in ("llm_call", "llm"):
                    provider, model = ev.get("provider") or "", ev.get("model") or ""
                    if provider:
                        conn.execute("UPDATE sessions SET provider=? WHERE id=? AND (provider IS NULL OR provider='')",
                                     (provider, sid))
                    body = ev.get("response_body") or ev.get("response")
                    text = body or "llm_call provider={} model={} response_chars={}".format(
                        provider or "?", model or "?", ev.get("response_chars", "?"))
                    record_message(sid, turn, "assistant", text, conn=conn)
                elif phase in ("iteration_start", "input"):
                    body = ev.get("input_body") or ev.get("input")
                    if body:
                        record_message(sid, turn, "user", body, conn=conn)
                elif phase == "action_parse":
                    tools = ev.get("tools") or []
                    record_message(sid, turn, "system", "action_parse source={} ok={} tools={}".format(
                        ev.get("source"), ev.get("ok"), ",".join(str(t) for t in tools)), conn=conn)
                    for t in tools:                       # one tool_call per parsed tool (searchable)
                        record_tool_call(sid, turn, str(t), "", "(parsed)", ev.get("ok") is not False, conn=conn)
                elif phase == "policy_decision":
                    record_tool_call(sid, turn, ev.get("tool") or "policy",
                                     "risk={}".format(ev.get("risk")), ev.get("reason") or "",
                                     ev.get("allowed") is not False, conn=conn)
                elif phase in ("iteration_result", "result"):
                    body = ev.get("result_body") or ev.get("result_text")
                    record_tool_call(sid, turn, "result", "",
                                     body or "result_chars={}".format(ev.get("result_chars", "?")),
                                     True, conn=conn)
                elif phase == "error":
                    record_tool_call(sid, turn, ev.get("code") or ev.get("error_type") or "error",
                                     ev.get("failed_action") or "",
                                     ev.get("repair_hint") or ev.get("message") or "", False, conn=conn)
                n += 1
        for sid in ingested:
            end_session(sid, "ingested", conn=conn)
        conn.commit()
        return {"ok": True, "sessions": len(ingested), "events": n}
    except OSError as e:
        return {"ok": False, "error": str(e)}
    finally:
        if own:
            conn.close()


def reset(path: Optional[str] = None) -> None:
    """Test helper: delete the on-disk DB (and clear the FTS-availability cache)."""
    p = path or db_path()
    _HAS_FTS.pop(p, None)
    if p != ":memory:" and os.path.exists(p):
        os.remove(p)


# --------------------------------------------------------------------------- selftest

def _selftest() -> None:
    import tempfile

    dbp = os.path.join(tempfile.mkdtemp(prefix="session_store_selftest_"), "s.db")
    os.environ["OMEGACLAW_SESSION_DB"] = dbp
    reset(dbp)

    begin_session("s1", provider="Test", channel="irc", task="deploy the widget service")
    record_message("s1", 1, "user", "please deploy the widget service to staging")
    record_message("s1", 1, "assistant", "starting deploy; running build")
    record_tool_call("s1", 1, "shell", "make build", "build ok", True)
    record_snapshot("s1", 1, {"task": "deploy widget", "step": "build done", "next": "run deploy"})
    end_session("s1", "interrupted")

    begin_session("s2", task="write the quarterly report")
    record_message("s2", 1, "user", "draft the quarterly finance report")
    end_session("s2", "done")

    # search finds the right session
    hits = search("widget deploy")
    assert hits and hits[0]["session_id"] == "s1", hits
    assert search("quarterly")[0]["session_id"] == "s2"

    # resume reconstructs state
    r = resume("s1")
    assert r["ok"] and r["latest_snapshot"]["next"] == "run deploy" and r["resume_turn"] == 1
    assert any("deploy" in m["text"] for m in r["recent_messages"])

    # show + export
    assert show("s1")["session"]["status"] == "interrupted"
    assert export("s1")["snapshots"][0]["turn"] == 1

    # content is persisted verbatim (no redaction at rest) and round-trips through show/export
    begin_session("s3", task="use the api")
    record_message("s3", 1, "assistant", "the plan is to ship the deploy tonight")
    record_tool_call("s3", 1, "shell", "echo hello", "done")
    assert "ship the deploy tonight" in json.dumps(show("s3"))

    # ingest a trace JSONL
    trace = os.path.join(tempfile.mkdtemp(), "t.jsonl")
    with open(trace, "w", encoding="utf-8") as f:
        f.write(json.dumps({"session_id": "tr1", "iteration": 1, "phase": "llm", "response": "hello world"}) + "\n")
        f.write(json.dumps({"session_id": "tr1", "iteration": 1, "phase": "result", "result_text": "sent"}) + "\n")
    ing = ingest_trace(trace)
    assert ing["ok"] and ing["sessions"] == 1 and show("tr1")["ok"]

    del os.environ["OMEGACLAW_SESSION_DB"]
    print("session_store self-tests passed")


if __name__ == "__main__":
    _selftest()
