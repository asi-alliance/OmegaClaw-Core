"""In-process unit tests for channels/telegram.py send-queueing.

Sends issued before the poll loop has connected (or before a chat is bound)
used to be dropped silently; now they are queued (bounded) and flushed in
order once the adapter is ready.

No container, no network, no token — same pattern as
mock_websocket/test_wschat_unit.py: the module is loaded by file path and its
`_api_call` layer is stubbed.
"""
import importlib.util
import logging
import os
import sys

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
    return _load_telegram()


def _capture_sends(module):
    sent = []
    module._api_call = (
        lambda method, params=None, timeout=30, use_post=False: sent.append(params["text"])
    )
    return sent


def _make_ready(module):
    module._connected = True
    module._chat_id = "12345"


def test_send_before_connect_is_queued_not_dropped(tg, caplog):
    caplog.set_level(logging.INFO)
    sent = _capture_sends(tg)

    tg.send_message("hello")

    assert sent == []
    assert len(tg._pending) == 1
    assert "[SEND_QUEUE] queued chars=5" in caplog.text


def test_connected_but_unbound_still_queues(tg, caplog):
    caplog.set_level(logging.INFO)
    sent = _capture_sends(tg)
    tg._connected = True  # polling up, no chat bound yet (auto-bind mode)

    tg.send_message("hello")

    assert sent == []
    assert len(tg._pending) == 1


def test_queue_flushes_in_order_once_ready(tg, caplog):
    caplog.set_level(logging.INFO)
    sent = _capture_sends(tg)

    tg.send_message("first")
    tg.send_message("second")
    _make_ready(tg)
    tg._flush_pending()

    assert sent == ["first", "second"]
    assert len(tg._pending) == 0
    assert "[SEND_FLUSH]" in caplog.text


def test_new_send_delivers_queued_messages_first(tg, caplog):
    caplog.set_level(logging.INFO)
    sent = _capture_sends(tg)

    tg.send_message("queued-early")
    _make_ready(tg)
    tg.send_message("sent-later")

    assert sent == ["queued-early", "sent-later"]
    assert len(tg._pending) == 0


def test_full_queue_drops_oldest_with_warning(tg, caplog):
    caplog.set_level(logging.INFO)
    sent = _capture_sends(tg)
    tg._PENDING_MAX = 3

    for msg in ["m1", "m2", "m3", "m4"]:
        tg.send_message(msg)

    assert len(tg._pending) == 3
    assert "[SEND_QUEUE] full (3): dropped oldest" in caplog.text

    _make_ready(tg)
    tg._flush_pending()
    assert sent == ["m2", "m3", "m4"]


def test_flush_stops_draining_when_delivery_fails(tg, caplog):
    caplog.set_level(logging.INFO)
    sent = []

    def failing_second(method, params=None, timeout=30, use_post=False):
        sent.append(params["text"])
        if len(sent) == 2:
            raise RuntimeError("boom")

    tg._api_call = failing_second
    tg.send_message("first")
    tg.send_message("second")
    tg.send_message("third")
    _make_ready(tg)

    tg._flush_pending()

    assert sent == ["first", "second"], "third must not be attempted in the failing drain"
    assert list(tg._pending) == ["third"], "undrained message stays queued for the next cycle"
    assert "[SEND_FLUSH] delivery failed, stopping drain (1 still queued)" in caplog.text


def test_ready_send_queues_behind_undrained_messages(tg, caplog):
    caplog.set_level(logging.INFO)
    sent = []

    def failing_second(method, params=None, timeout=30, use_post=False):
        sent.append(params["text"])
        if len(sent) == 2:
            raise RuntimeError("boom")

    tg._api_call = failing_second
    for m in ["m1", "m2", "m3", "m4"]:
        tg.send_message(m)
    _make_ready(tg)

    tg.send_message("m5")

    assert sent == ["m1", "m2"], "drain stopped at the failure"
    assert list(tg._pending) == ["m3", "m4", "m5"], "ready send joins the queue, no overtaking"

    tg._flush_pending()
    assert sent == ["m1", "m2", "m3", "m4", "m5"], "next drain delivers in original order"


def test_flush_stops_when_connection_lost_midway(tg, caplog):
    caplog.set_level(logging.INFO)
    sent = []

    def api_then_disconnect(method, params=None, timeout=30, use_post=False):
        sent.append(params["text"])
        tg._connected = False  # connection drops after the first delivery

    tg._api_call = api_then_disconnect
    tg.send_message("first")
    tg.send_message("second")
    _make_ready(tg)

    tg._flush_pending()

    assert sent == ["first"]
    assert list(tg._pending) == ["second"], "undelivered message stays queued"
