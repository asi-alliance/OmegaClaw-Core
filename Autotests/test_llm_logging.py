"""Unit tests for gated/redacted raw LLM response logging (Issue #3).

Pure-Python: no Docker. ``lib_llm_ext`` imports ``openai``, which is not installed
on the host/CI runner, so we stub it before import. Runs under pytest and as a
standalone script (``python3 Autotests/test_llm_logging.py``).
"""
import io
import json
import os
import sys
import tempfile
import types
from contextlib import redirect_stdout

_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
# `lib_llm_ext` moved into the providers/ package during the upstream plugin migration; add both
# providers/ (so `import lib_llm_ext` resolves) and the repo root (so its `from src.*` imports work).
_PROVIDERS = os.path.join(_REPO_ROOT, "providers")
for _p in (_PROVIDERS, _REPO_ROOT):
    if _p not in sys.path:
        sys.path.insert(0, _p)

# Stub openai so `import lib_llm_ext` works without the real dependency.
# `openai.OpenAI` is referenced in a type annotation evaluated at import time.
if "openai" not in sys.modules:
    _openai_stub = types.ModuleType("openai")
    _openai_stub.OpenAI = object  # satisfies `Optional[openai.OpenAI]`
    sys.modules["openai"] = _openai_stub

import lib_llm_ext as llm  # noqa: E402

# A response mixing normal prose with several secret shapes.
GH_TOKEN = "ghp_" + "A1b2C3d4E5f6G7h8I9j0" + "KLMNOP"
GH_PAT = "github_pat_" + "11ABCDEFG0" + "abcdefghijklmnopqrstuv"
OPENAI_KEY = "sk-" + "A1b2C3d4E5f6G7h8I9j0K1l2"
ANTHROPIC_KEY = "sk-ant-" + "api03-" + "ZyXwVuTsRqPoNmLkJiHg"
BEARER = "Bearer abcDEF123456ghiJKL789"
AWS_KEY = "AKIAIOSFODNN7EXAMPLE"
B64_SECRET = "QUJDREVGR0hJSktMTU5PUFFSU1RVVldYWVowMTIzNDU2Nzg5"  # >=40
SECRETS = [GH_TOKEN, GH_PAT, OPENAI_KEY, ANTHROPIC_KEY, "abcDEF123456ghiJKL789", AWS_KEY, B64_SECRET]

RESPONSE = (
    "Sure, here is the plan. Use this GitHub token " + GH_TOKEN + " and PAT " + GH_PAT +
    ". OpenAI key " + OPENAI_KEY + ", Anthropic " + ANTHROPIC_KEY +
    ". Auth header: " + BEARER + ". AWS " + AWS_KEY + ". blob=" + B64_SECRET + ". Done."
)
NORMAL_SENTINEL = "here is the plan"


def _capture_log(**env):
    """Run _log_raw under a temporary env and return captured stdout."""
    saved = {k: os.environ.get(k) for k in ("OMEGACLAW_DEBUG_LLM_RAW", "OMEGACLAW_LLM_LOG_PATH")}
    for k in saved:
        os.environ.pop(k, None)
    os.environ.update({k: v for k, v in env.items() if v is not None})
    buf = io.StringIO()
    try:
        with redirect_stdout(buf):
            llm._log_raw("OpenAI", "gpt-test", RESPONSE)
    finally:
        for k, v in saved.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v
    return buf.getvalue()


# --- default (no raw) ----------------------------------------------------

def test_default_logs_metadata_not_raw():
    out = _capture_log()
    assert "[LLM_RAW]" in out
    assert "provider=OpenAI" in out and "model=gpt-test" in out
    assert "chars=%d" % len(RESPONSE) in out
    assert "trace=" in out
    assert "<redacted; set OMEGACLAW_DEBUG_LLM_RAW=1>" in out
    # The raw body and its secrets must NOT appear.
    assert NORMAL_SENTINEL not in out
    for s in SECRETS:
        assert s not in out, f"secret leaked by default: {s!r}"


def test_default_never_leaks_github_token():
    out = _capture_log()
    assert GH_TOKEN not in out and GH_PAT not in out


# --- debug (raw, redacted) ----------------------------------------------

def test_debug_shows_redacted_raw():
    out = _capture_log(OMEGACLAW_DEBUG_LLM_RAW="1")
    # raw context is present (normal prose shows through)...
    assert NORMAL_SENTINEL in out
    # ...but no secret appears verbatim.
    for s in SECRETS:
        assert s not in out, f"secret leaked in debug mode: {s!r}"
    assert "[REDACTED:" in out


def test_debug_truthy_values():
    for val in ("1", "true", "YES", "on"):
        out = _capture_log(OMEGACLAW_DEBUG_LLM_RAW=val)
        assert NORMAL_SENTINEL in out, f"{val} should enable raw"
    # a falsey value stays default
    out = _capture_log(OMEGACLAW_DEBUG_LLM_RAW="0")
    assert NORMAL_SENTINEL not in out


# --- redact_secrets unit -------------------------------------------------

def test_redact_each_pattern():
    cases = {
        "openai": OPENAI_KEY,
        "anthropic": ANTHROPIC_KEY,
        "github_ghp": GH_TOKEN,
        "github_pat": GH_PAT,
        "aws": AWS_KEY,
        "base64": B64_SECRET,
    }
    for name, secret in cases.items():
        red = llm.redact_secrets(f"value is {secret} end")
        assert secret not in red, f"{name} not redacted: {red}"
        assert "[REDACTED:" in red


def test_redact_bearer_keeps_scheme():
    red = llm.redact_secrets("Authorization: " + BEARER)
    assert "abcDEF123456ghiJKL789" not in red
    assert "Bearer" in red and "[REDACTED:bearer]" in red


def test_redact_preserves_normal_text():
    text = "The quick brown fox jumps over the lazy dog 42 times."
    assert llm.redact_secrets(text) == text


# --- JSONL log -----------------------------------------------------------

def test_jsonl_metadata_only_by_default():
    with tempfile.NamedTemporaryFile("r", suffix=".jsonl", delete=False) as f:
        path = f.name
    try:
        _capture_log(OMEGACLAW_LLM_LOG_PATH=path)
        with open(path) as fh:
            rec = json.loads(fh.readline())
        assert rec["provider"] == "OpenAI" and rec["chars"] == len(RESPONSE) and "trace" in rec
        assert "raw" not in rec  # no raw by default
    finally:
        os.unlink(path)


def test_jsonl_includes_redacted_raw_in_debug():
    with tempfile.NamedTemporaryFile("r", suffix=".jsonl", delete=False) as f:
        path = f.name
    try:
        _capture_log(OMEGACLAW_DEBUG_LLM_RAW="1", OMEGACLAW_LLM_LOG_PATH=path)
        with open(path) as fh:
            rec = json.loads(fh.readline())
        assert "raw" in rec
        for s in SECRETS:
            assert s not in rec["raw"], f"secret leaked in JSONL: {s!r}"
    finally:
        os.unlink(path)


def _run_standalone():
    failures = 0
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            try:
                fn()
                print(f"PASS {name}")
            except AssertionError as exc:
                failures += 1
                print(f"FAIL {name}: {exc}")
    if failures:
        print(f"\n{failures} test(s) failed")
        sys.exit(1)
    print("\nall llm logging tests passed")


if __name__ == "__main__":
    _run_standalone()
