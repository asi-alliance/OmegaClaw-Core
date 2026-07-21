"""Unit tests for structured reasoning-trace logging (Issue #7).

Pure-Python, no Docker/LLM/MeTTa. Runs under pytest and standalone
(`python3 Autotests/test_tracing.py`). Covers: trace schema + trace_id linkage across an
iteration's events, metadata-only default vs full bodies, the disable gate, the
action-pipeline + policy-denial emission hooks, and the trace-summary aggregator.
"""
import importlib.machinery
import importlib.util
import json
import os
import sys
import tempfile

_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_SRC = os.path.join(_REPO_ROOT, "src")
for _p in (_SRC, _REPO_ROOT):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import tracing  # noqa: E402


def _read(path):
    with open(path, encoding="utf-8") as f:
        return [json.loads(x) for x in f if x.strip()]


def _fresh(tmp, name="t.jsonl"):
    path = os.path.join(tmp, name)
    os.environ["OMEGACLAW_TRACE_PATH"] = path
    for k in ("OMEGACLAW_TRACE_DISABLE", "OMEGACLAW_TRACE_BODIES", "OMEGACLAW_DEBUG_LLM_RAW"):
        os.environ.pop(k, None)
    tracing.reset()
    return path


# --- schema + linkage ------------------------------------------------------

def test_iteration_events_share_trace_id_and_schema():
    with tempfile.TemporaryDirectory() as d:
        path = _fresh(d)
        sid = tracing.begin_session()
        tid = tracing.begin_iteration(1, input_text="PROMPT: hi")
        tracing.trace_llm("Test", "mock", prompt="hi", response="ok", latency_ms=42)
        tracing.trace_parse(ok=True, source="json", version=1, tools=["send"], error_codes=[])
        tracing.end_iteration("done")
        events = _read(path)
        assert [e["phase"] for e in events] == [
            "iteration_start", "llm_call", "action_parse", "iteration_result", "iteration_end"]
        assert len({e["trace_id"] for e in events}) == 1 and events[0]["trace_id"] == tid
        for e in events:  # every event carries the required top-level fields
            for k in ("ts", "trace_id", "session_id", "iteration", "phase"):
                assert k in e, (k, e)
            assert e["session_id"] == sid and e["iteration"] == 1


def test_set_context_populates_turn_and_state_hash():
    with tempfile.TemporaryDirectory() as d:
        path = _fresh(d)
        tracing.begin_session("game-1")
        tracing.begin_iteration(5)
        tracing.set_context(turn_id=42, state_hash="abc123")
        tracing.trace_llm("Test", "mock", prompt="p", response="r")
        llm = [e for e in _read(path) if e["phase"] == "llm_call"][0]
        assert llm["turn_id"] == 42 and llm["input_state_hash"] == "abc123" and llm["session_id"] == "game-1"


# --- privacy ---------------------------------------------------------------

def test_metadata_only_by_default_no_bodies():
    with tempfile.TemporaryDirectory() as d:
        path = _fresh(d)
        tracing.begin_iteration(1)
        tracing.trace_llm("Test", "mock", prompt="Bearer abcdef123456ghijkl", response="secret-ish")
        llm = [e for e in _read(path) if e["phase"] == "llm_call"][0]
        assert "prompt_body" not in llm and "response_body" not in llm
        assert llm["prompt_sha"] and llm["prompt_chars"] > 0  # hashes/metadata still present


def test_bodies_mode_includes_bodies():
    with tempfile.TemporaryDirectory() as d:
        path = _fresh(d)
        os.environ["OMEGACLAW_TRACE_BODIES"] = "1"
        tracing.begin_iteration(1)
        tracing.trace_llm("Test", "mock", prompt="tok Bearer abcdef123456ghijkl", response="r")
        llm = [e for e in _read(path) if e["phase"] == "llm_call"][0]
        assert llm["prompt_body"] == "tok Bearer abcdef123456ghijkl"
        os.environ.pop("OMEGACLAW_TRACE_BODIES", None)


def test_disable_gate_writes_nothing():
    with tempfile.TemporaryDirectory() as d:
        path = _fresh(d)
        os.environ["OMEGACLAW_TRACE_DISABLE"] = "1"
        tracing.begin_iteration(1)
        tracing.trace_llm("Test", "mock", prompt="p", response="r")
        tracing.end_iteration("x")
        assert not os.path.exists(path)
        os.environ.pop("OMEGACLAW_TRACE_DISABLE", None)


# NOTE: the action-pipeline / policy-denial emission-hook test lives with those producer
# modules (action_protocol / tool_policy), which are not part of this tracing-infra change.

# --- summary aggregator ----------------------------------------------------

def _load_summary_module():
    loader = importlib.machinery.SourceFileLoader(
        "trace_summary", os.path.join(_REPO_ROOT, "scripts", "omegaclaw-trace-summary"))
    mod = importlib.util.module_from_spec(importlib.util.spec_from_loader("trace_summary", loader))
    loader.exec_module(mod)
    return mod


def test_summary_aggregates_metrics():
    ts = _load_summary_module()
    with tempfile.TemporaryDirectory() as d:
        path = _fresh(d)
        tracing.begin_session()
        for i in range(3):
            tracing.begin_iteration(i)
            tracing.trace_llm("Test", "mock", prompt="p", response="r", latency_ms=100 + i)
            tracing.trace_parse(ok=(i != 1), source="json", version=1,
                                tools=(["send"] if i != 1 else []), error_codes=([] if i != 1 else ["unknown_tool"]))
            if i == 2:
                tracing.trace_policy("shell", allowed=False, reason="disabled", risk="high")
            tracing.end_iteration("done")
        events, malformed = ts.load_events(path)
        s = ts.summarize(events, malformed)
        assert s["iterations"] == 3 and s["fully_linked_iterations"] == 3 and s["linkage_rate"] == 1.0
        assert s["parse_errors"] == 1 and s["invalid_actions"] == 1 and s["policy_denials"] == 1
        assert s["actions_by_type"].get("send") == 2 and s["avg_llm_latency_ms"] == 101.0


if __name__ == "__main__":
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_") and callable(v)]
    for fn in fns:
        fn()
        print("ok:", fn.__name__)
    print("\nAll {} tracing tests passed".format(len(fns)))
