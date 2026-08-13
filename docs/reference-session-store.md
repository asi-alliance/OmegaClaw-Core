# Session Store — `omegaclaw-sessions`

OmegaClaw keeps raw logs and `history.metta`, but neither answers questions like *"where did we
leave off?"*, *"what did we decide about X last week?"*, or *"resume that interrupted run."* The
**session store** adds a durable, queryable **SQLite** database of sessions, messages, and tool
calls, with full-text search and resumable snapshots.

- Module: `src/session_store.py`
- CLI: `scripts/omegaclaw-sessions`
- DB path: `OMEGACLAW_SESSION_DB` (default `<repo>/memory/sessions.db`, a runtime file)

## Schema

| Table | Holds |
|---|---|
| `sessions` | one row per run — provider, channel, task, status, turn count, metadata |
| `messages` | per-turn user/assistant text |
| `tool_calls` | per-turn tool name, args, result, ok/failed |
| `snapshots` | reconstructable state checkpoints for `resume` |

Search uses SQLite **FTS5** when available and falls back transparently to `LIKE`.

## How data gets in

There are two ingestion paths:

1. **Recording API** — `begin_session` / `record_message` / `record_tool_call` /
   `record_snapshot` / `end_session`. This is the surface the reasoning loop calls to record a
   session live as it runs. Live wiring into the loop lands as a follow-up; today the API is
   covered by unit tests and is the supported way to populate the store directly.
2. **`ingest_trace(path)`** — backfills the store from a reasoning-trace JSONL. It maps the
   tracing phases (`iteration_start` / `llm_call` / `action_parse` / `policy_decision` /
   `iteration_result` / `error` / `iteration_end`) into messages and tool calls, producing
   searchable summaries even when bodies weren't recorded.

> **Dependency:** the trace JSONL is emitted by `src.tracing`, introduced in
> [PR #270](https://github.com/asi-alliance/OmegaClaw-Core/pull/270) (`contrib/reasoning-trace`).
> This feature is stacked on that PR — `ingest_trace` becomes reachable end-to-end once #270 is
> merged underneath.

## CLI

```
omegaclaw-sessions list                     # list recent sessions
omegaclaw-sessions search "<query>"         # full-text search across sessions/messages/tools
omegaclaw-sessions show <id>                # full transcript of a session
omegaclaw-sessions resume <id>              # reconstruct enough state to continue a run
omegaclaw-sessions export <id>              # full JSON export
omegaclaw-sessions ingest <trace.jsonl>     # backfill from a reasoning-trace JSONL
```

Add `--json` to any command for machine-readable output.

## Tests

`Autotests/unit/test_session_store.py` (pure-Python, stdlib `sqlite3`, host-runnable; registered
in `run_mandatory`) covers begin/record/show/resume/export round-trips, search by
content/tool/provider, list + missing-session handling, and `ingest_trace` against a
directly-written trace JSONL (kept independent of the tracing module).

```
cd Autotests/unit && python3 test_session_store.py
```
