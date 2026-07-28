"""
In-process unit tests for the WebSocket channel logic (channels/wschat.py).

These drive the channel's pure functions directly on the host: no container, no
running agent, no `-t websocket`, and no `websockets` library (wschat imports it
lazily, only when actually connecting). That makes them CI-eligible in the same
job as test_comm / test_llm / test_rpc — they catch regressions in the dedup,
A | B | C merge, outbox and frame-parsing logic on every run.

The end-to-end wiring (channels.metta websocket dispatch, send skill ->
agent_message, real drain -> LLM) is covered separately by the
test_*_ws_mock.py integration suite, which needs a `-t websocket` container.
"""
import importlib.util
import json
import os
import uuid

import pytest

_WSCHAT_PATH = os.path.normpath(
    os.path.join(os.path.dirname(__file__), "..", "..", "channels", "wschat.py")
)


def _load_wschat():
    spec = importlib.util.spec_from_file_location("wschat_under_test", _WSCHAT_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def wschat():
    module = _load_wschat()
    module._inbox.clear()
    module._outbox.clear()
    module._last_seen_seq = None
    module._connected = False
    module._ws = None
    module._running = False
    return module


def _user_message(seq, text):
    return json.dumps({"type": "user_message", "seq": seq, "text": text})


def test_enqueue_join_and_last_seen(wschat):
    wschat._handle_frame(_user_message(1, "A"))
    wschat._handle_frame(_user_message(2, "B"))
    wschat._handle_frame(_user_message(3, "C"))
    assert wschat.getLastMessage() == "A | B | C"
    assert wschat._last_seen_seq == 3
    assert wschat.getLastMessage() == ""


def test_dedup_by_last_seen_seq(wschat):
    wschat._handle_frame(_user_message(1, "A"))
    wschat._handle_frame(_user_message(2, "B"))
    assert wschat.getLastMessage() == "A | B"
    assert wschat._last_seen_seq == 2

    wschat._handle_frame(_user_message(2, "replay-2"))
    wschat._handle_frame(_user_message(1, "replay-1"))
    assert wschat.getLastMessage() == ""


def test_dedup_by_inbox_order(wschat):
    wschat._handle_frame(_user_message(5, "X"))
    wschat._handle_frame(_user_message(5, "Y"))
    wschat._handle_frame(_user_message(4, "Z"))
    assert wschat.getLastMessage() == "X"
    assert wschat._last_seen_seq == 5


def test_frame_robustness(wschat):
    wschat._handle_frame("this is not json <<<{")
    wschat._handle_frame(json.dumps(["not", "a", "dict"]))
    wschat._handle_frame(json.dumps({"type": "user_message", "seq": "x", "text": "t"}))
    wschat._handle_frame(json.dumps({"type": "user_message", "seq": 1, "text": 123}))
    wschat._handle_frame(json.dumps({"type": "totally_unknown"}))
    wschat._handle_frame(json.dumps({"type": "ack", "seq": 1, "client_seq": "abc"}))
    wschat._handle_frame(json.dumps({"type": "error", "code": "E", "message": "boom"}))
    assert len(wschat._inbox) == 0

    wschat._handle_frame(_user_message(1, "OK"))
    assert wschat.getLastMessage() == "OK"


def test_outbox_buffers_while_disconnected_and_flushes(wschat):
    wschat._connected = False
    wschat._ws = None

    wschat.send_message("buffered-1")
    assert len(wschat._outbox) == 1
    payload = wschat._outbox[0]
    assert payload["type"] == "agent_message"
    assert payload["text"] == "buffered-1"
    uuid.UUID(hex=payload["client_seq"])
    original_client_seq = payload["client_seq"]

    sent = []

    class _FakeWs:
        def send(self, message):
            sent.append(message)

    wschat._drain_outbox(_FakeWs())
    assert len(wschat._outbox) == 0
    assert len(sent) == 1
    flushed = json.loads(sent[0])
    assert flushed["type"] == "agent_message"
    assert flushed["text"] == "buffered-1"
    assert flushed["client_seq"] == original_client_seq


def test_resume_frame_reflects_last_seen(wschat):
    assert wschat._build_resume_frame() == {"type": "resume", "last_seen_seq": None}
    wschat._last_seen_seq = 7
    assert wschat._build_resume_frame() == {"type": "resume", "last_seen_seq": 7}
