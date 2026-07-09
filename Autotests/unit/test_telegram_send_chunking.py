"""In-process unit tests for channels/telegram.py send_message chunking +
delivery-status logging.

No container, no network, no token — same pattern as
mock_websocket/test_wschat_unit.py: the module is loaded by file path and its
`_api_call` layer is stubbed. That makes these CI-eligible alongside
test_comm / test_llm / test_rpc.

Covers the send-hardening behavior:
  - a failed chunk does NOT abort the remaining chunks of a multi-chunk message
  - a failed chunk pauses 1s before the remaining chunks (rate-limit relief)
  - per-chunk [SEND_FAIL] lines and a [SEND_OK]/[SEND_PARTIAL]/[SEND_FAIL]
    summary line make delivery status greppable in the log
  - unbound/disconnected sends log [SEND_SKIP] instead of dropping silently
"""
import importlib.util
import logging
import os
import sys
import types

import pytest

_REPO_ROOT = os.path.normpath(os.path.join(os.path.dirname(__file__), "..", ".."))
_CHANNELS_DIR = os.path.join(_REPO_ROOT, "channels")
_TELEGRAM_PATH = os.path.join(_CHANNELS_DIR, "telegram.py")

# telegram.py does `import auth` (a channels/ sibling) and
# `from src.logger import get_logger` (repo-root package) at import time.
for _p in (_REPO_ROOT, _CHANNELS_DIR):
    if _p not in sys.path:
        sys.path.insert(0, _p)


def _load_telegram():
    spec = importlib.util.spec_from_file_location("telegram_under_test", _TELEGRAM_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def tg():
    module = _load_telegram()
    module._connected = True
    module._chat_id = "12345"
    return module


def _capture_sends(module):
    sent = []
    module._api_call = (
        lambda method, params=None, timeout=30, use_post=False: sent.append(params["text"])
    )
    return sent


def _capture_sleeps(module):
    sleeps = []
    module.time = types.SimpleNamespace(sleep=sleeps.append)
    return sleeps


def test_single_chunk_ok_logs_send_ok(tg, caplog):
    caplog.set_level(logging.INFO)
    sent = _capture_sends(tg)

    tg.send_message("hello")

    assert sent == ["hello"]
    assert "[SEND_OK] chunks=1 chars=5" in caplog.text
    assert "[SEND_FAIL]" not in caplog.text


def test_long_text_is_chunked(tg, caplog):
    caplog.set_level(logging.INFO)
    sent = _capture_sends(tg)

    tg.send_message("a" * 3900 + "b" * 3900 + "c" * 10)

    assert [len(c) for c in sent] == [3900, 3900, 10]
    assert "[SEND_OK] chunks=3 chars=7810" in caplog.text


def test_failed_chunk_does_not_abort_remaining_chunks(tg, caplog):
    caplog.set_level(logging.INFO)
    sent = []

    def flaky(method, params=None, timeout=30, use_post=False):
        sent.append(params["text"])
        if len(sent) == 2:
            raise RuntimeError("boom")

    tg._api_call = flaky
    sleeps = _capture_sleeps(tg)

    tg.send_message("a" * 3900 + "b" * 3900 + "c" * 3900)

    assert len(sent) == 3, "chunk 3 must still be attempted after chunk 2 fails"
    assert sleeps == [1], "one rate-limit pause after the mid-message failure"
    assert "[SEND_FAIL] chunk=2/3" in caplog.text
    assert "[SEND_PARTIAL] ok=2 fail=1" in caplog.text


def test_all_chunks_failing_logs_send_fail_summary(tg, caplog):
    caplog.set_level(logging.INFO)

    def broken(method, params=None, timeout=30, use_post=False):
        raise RuntimeError("boom")

    tg._api_call = broken
    sleeps = _capture_sleeps(tg)

    tg.send_message("a" * 3900 + "b" * 3900)

    assert sleeps == [1], "no pause after the final chunk"
    assert "[SEND_FAIL] chunk=1/2" in caplog.text
    assert "[SEND_FAIL] chunk=2/2" in caplog.text
    assert "[SEND_FAIL] ok=0 fail=2" in caplog.text
    assert "[SEND_PARTIAL]" not in caplog.text


def test_unbound_or_disconnected_skips_with_log(tg, caplog):
    caplog.set_level(logging.INFO)
    sent = _capture_sends(tg)
    tg._connected = False

    tg.send_message("hello")

    assert sent == []
    assert "[SEND_SKIP] connected=False bound=True chars=5" in caplog.text
    assert "[SEND_OK]" not in caplog.text and "[SEND_FAIL]" not in caplog.text
