"""Structured reasoning-trace logging (Issue #7).

Emits one JSON object per event to a JSONL trace file so a single loop iteration's
input -> LLM call -> action parse -> policy decision -> result are all linkable by a shared
``trace_id``. Generalizes the per-call JSONL logging from Issue #3 (``lib_llm_ext._log_raw``)
into a cross-component trace with a ``contextvars``-based current-trace context, so the Python
components (``plugin.llmProviderChat``, ``action_protocol.parse_and_render_metta``,
``tool_policy.log_denial``) emit under the current iteration's id without threading it through
MeTTa signatures.

Privacy (mirrors Issue #3): **on by default, metadata/hashes only** — prompt/state/result
bodies are written only when ``OMEGACLAW_TRACE_BODIES`` (or ``OMEGACLAW_DEBUG_LLM_RAW``) is set,
and even then are scrubbed through ``redaction.redact_secrets`` so tokens / API keys /
``Authorization`` headers never reach the durable trace. IO is best-effort and never breaks
the loop.

Env:
- ``OMEGACLAW_TRACE_PATH``    trace file (default ``<repo>/memory/traces/YYYYMMDD.jsonl``).
- ``OMEGACLAW_TRACE_DISABLE`` truthy -> emit nothing.
- ``OMEGACLAW_TRACE_BODIES``  truthy -> include prompt/result bodies (else hashes only).
"""

import contextvars
import datetime
import hashlib
import json
import os
import time
import uuid

try:  # bare import when ``src`` is on sys.path, package import otherwise
    from redaction import redact_secrets
except ImportError:  # pragma: no cover - import-path fallback
    from src.redaction import redact_secrets

_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# Per-iteration trace context (single MeTTa loop thread; ContextVar keeps it safe if the
# process later runs concurrent tasks). session_id is process-wide.
_ctx = contextvars.ContextVar("omegaclaw_trace_ctx", default=None)
_session = {"id": None}


# --------------------------------------------------------------------------- config

def _truthy(v):
    return (v or "").strip().lower() in {"1", "true", "yes", "on"}


def _disabled():
    return _truthy(os.environ.get("OMEGACLAW_TRACE_DISABLE"))


def _bodies_enabled():
    return _truthy(os.environ.get("OMEGACLAW_TRACE_BODIES")) or _truthy(os.environ.get("OMEGACLAW_DEBUG_LLM_RAW"))


def trace_path():
    """Active trace file path (env override or dated default)."""
    p = os.environ.get("OMEGACLAW_TRACE_PATH")
    if p:
        return p
    day = datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%d")
    return os.path.join(_REPO_ROOT, "memory", "traces", "{}.jsonl".format(day))


# --------------------------------------------------------------------------- helpers

def new_id():
    return uuid.uuid4().hex[:8]


def _sha256(text):
    return hashlib.sha256((text or "").encode("utf-8", "ignore")).hexdigest()


def _coerce_int(x):
    try:
        return int(x)
    except (TypeError, ValueError):
        return x


def _ctx_get():
    c = _ctx.get()
    if c is None:
        c = {"trace_id": None, "session_id": _session["id"], "turn_id": None,
             "iteration": None, "input_state_hash": None}
        _ctx.set(c)
    return c


def _body(text):
    """Redacted body when bodies are enabled, else None (metadata-only default).

    Even in bodies mode the text is passed through ``redact_secrets`` so tokens / API
    keys / ``Authorization`` headers do not land in the durable trace.
    """
    if text is None:
        return None
    return redact_secrets(text) if _bodies_enabled() else None


# --------------------------------------------------------------------------- context API

def begin_session(session_id=None):
    """Mint (or set) the process-wide session id. Call once per run/game."""
    _session["id"] = session_id or new_id()
    _ctx_get()["session_id"] = _session["id"]
    return _session["id"]


def begin_iteration(iteration=None, input_text=None, state_hash=None):
    """Start a new trace for a loop iteration: mint trace_id, emit an ``iteration_start``."""
    trace_id = new_id()
    _ctx.set({
        "trace_id": trace_id,
        "session_id": _session["id"],
        "turn_id": None,
        "iteration": _coerce_int(iteration),
        "input_state_hash": state_hash or (_sha256(input_text) if input_text else None),
    })
    emit("iteration_start", input_chars=(len(input_text) if input_text else None))
    return trace_id


def set_context(session_id=None, turn_id=None, state_hash=None):
    """Enrich the current trace context — used by producers (e.g. the FreeCiv runner) to
    attach session_id / turn_id / input_state_hash when a game is active."""
    c = _ctx_get()
    if session_id is not None:
        c["session_id"] = session_id
        _session["id"] = session_id
    if turn_id is not None:
        c["turn_id"] = _coerce_int(turn_id)
    if state_hash is not None:
        c["input_state_hash"] = state_hash
    return ""


def current():
    """Snapshot of the current trace context (dict)."""
    return dict(_ctx_get())


def reset():
    """Test helper: clear session + iteration context."""
    _session["id"] = None
    _ctx.set(None)


# --------------------------------------------------------------------------- emit

def emit(kind, **fields):
    """Write one JSONL trace event of ``kind`` under the current context. None fields dropped.

    Fully best-effort: emit is invoked from the MeTTa loop via ``py-call`` (parse / policy /
    error hooks), so it must never raise — any failure degrades to a no-op returning ``""``.
    """
    try:
        if _disabled():
            return ""
        c = _ctx_get()
        record = {
            "ts": time.strftime("%Y-%m-%d %H:%M:%S", time.gmtime()),
            "trace_id": c.get("trace_id"),
            "session_id": c.get("session_id"),
            "turn_id": c.get("turn_id"),
            "iteration": c.get("iteration"),
            "phase": kind,
            "input_state_hash": c.get("input_state_hash"),
        }
        for k, v in fields.items():
            if v is not None:
                record[k] = v
        _write(record)
        return record.get("trace_id") or ""
    except Exception:  # a trace failure must never break the loop
        return ""


def _write(record):
    path = trace_path()
    try:
        d = os.path.dirname(path)
        if d:
            os.makedirs(d, exist_ok=True)
        with open(path, "a", encoding="utf-8") as f:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")
    except OSError as exc:  # best-effort; a trace failure must never break the loop
        print("[tracing] WARNING could not write trace ({}): {}".format(path, exc), flush=True)


# --------------------------------------------------------------------------- typed events

def trace_llm(provider="", model="", prompt="", response="", latency_ms=None):
    return emit("llm_call", provider=provider or None, model=model or None,
                prompt_sha=_sha256(prompt), prompt_chars=len(prompt or ""),
                response_chars=len(response or ""), latency_ms=latency_ms,
                prompt_body=_body(prompt), response_body=_body(response))


def trace_parse(ok=None, source=None, version=None, tools=None, error_codes=None):
    return emit("action_parse", ok=ok, source=source, version=version,
                tools=(tools or None), error_codes=(error_codes or None))


def trace_policy(tool="", allowed=None, reason=None, risk=None):
    return emit("policy_decision", tool=tool or None, allowed=allowed,
                reason=(reason or None), risk=(risk or None))


def trace_error(stage="", code=None, message=None, error_type=None,
                failed_action=None, repair_hint=None, retryable=None):
    """Structured error recovery event (Issue #10).

    The classification fields — ``error_type`` (category), the original protocol
    ``code`` (e.g. ``missing_arg``), ``retryable`` and ``repair_hint`` — are not
    sensitive and are ALWAYS emitted, so downstream analytics can recover the full
    schema from the durable trace. The failed action is body-like content (it can
    embed file contents or echoed user text), so it follows the same privacy gate
    as prompt/result bodies: ``failed_action_sha`` + ``failed_action_chars`` are
    always emitted (correlatable by default), and the ``failed_action``
    body only when ``OMEGACLAW_TRACE_BODIES`` is set.
    """
    fa = None
    if failed_action is not None:
        fa = failed_action if isinstance(failed_action, str) else json.dumps(
            failed_action, ensure_ascii=False, default=str)
    return emit("error", stage=stage or None,
                error_type=(error_type or None),
                code=(code or None),
                retryable=retryable,
                repair_hint=(repair_hint or None),
                message=(message if message else None),
                failed_action_sha=(_sha256(fa) if fa else None),
                failed_action_chars=(len(fa) if fa is not None else None),
                failed_action=(_body(fa) if fa else None))


def trace_result(result_text=""):
    return emit("iteration_result", result_chars=len(result_text or ""),
                result_sha=_sha256(result_text), result_body=_body(result_text))


def end_iteration(result_text=""):
    """Close the current iteration trace (records the final result), emit ``iteration_end``."""
    if result_text:
        trace_result(result_text)
    return emit("iteration_end")


# --------------------------------------------------------------------------- self-test

def _selftest():
    """Lightweight self-tests runnable without pytest/Docker."""
    import tempfile

    with tempfile.TemporaryDirectory() as d:
        path = os.path.join(d, "trace.jsonl")
        os.environ["OMEGACLAW_TRACE_PATH"] = path
        os.environ.pop("OMEGACLAW_TRACE_BODIES", None)
        os.environ.pop("OMEGACLAW_DEBUG_LLM_RAW", None)
        os.environ.pop("OMEGACLAW_TRACE_DISABLE", None)
        reset()

        sid = begin_session()
        tid = begin_iteration(1, input_text="PROMPT: hello")
        assert sid and tid
        trace_llm("SNET", "gpt-oss-120b", prompt="Bearer abcdef123456ghijkl secret", response="ok")
        trace_parse(ok=True, source="json", version=1, tools=["send"])
        trace_policy("shell", allowed=False, reason="disabled", risk="high")
        end_iteration("RESULTS: done")

        events = [json.loads(x) for x in open(path, encoding="utf-8") if x.strip()]
        kinds = [e["phase"] for e in events]
        assert kinds == ["iteration_start", "llm_call", "action_parse", "policy_decision",
                         "iteration_result", "iteration_end"], kinds
        # all events in one iteration share the trace_id (linkage)
        assert len({e["trace_id"] for e in events}) == 1
        assert all(e["session_id"] == sid for e in events)
        # metadata-only default: no bodies, but hashes present
        llm = next(e for e in events if e["phase"] == "llm_call")
        assert "prompt_body" not in llm and llm["prompt_sha"] and llm["prompt_chars"] > 0

        # bodies mode: full body appears
        os.environ["OMEGACLAW_TRACE_BODIES"] = "1"
        path2 = os.path.join(d, "trace2.jsonl")
        os.environ["OMEGACLAW_TRACE_PATH"] = path2
        reset(); begin_iteration(2)
        trace_llm("X", "y", prompt="tok Bearer abcdef123456ghijkl", response="r")
        ev = [json.loads(x) for x in open(path2, encoding="utf-8") if x.strip()]
        body = next(e for e in ev if e["phase"] == "llm_call")["prompt_body"]
        # bodies are present but scrubbed: the bearer token must not leak
        assert body.startswith("tok Bearer ") and "abcdef123456ghijkl" not in body, body

        # disable gate
        os.environ["OMEGACLAW_TRACE_DISABLE"] = "1"
        path3 = os.path.join(d, "trace3.jsonl")
        os.environ["OMEGACLAW_TRACE_PATH"] = path3
        reset(); begin_iteration(3); emit("llm_call")
        assert not os.path.exists(path3)

        for k in ("OMEGACLAW_TRACE_PATH", "OMEGACLAW_TRACE_BODIES", "OMEGACLAW_TRACE_DISABLE"):
            os.environ.pop(k, None)
        reset()
    print("tracing self-tests passed")


if __name__ == "__main__":
    _selftest()
