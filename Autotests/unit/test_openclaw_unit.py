"""In-process unit tests for plugins/openclaw/openclaw.py.

The module is loaded by file path and runs without a container, a network, or
a Gateway, the same way unit/test_fileio_verified_writes.py does. `config` and
`requests` are stubbed before the import, so this file needs nothing beyond
pytest and is safe to keep in run_mandatory.
"""
import importlib.util
import json
import os
import sys
import threading
import types

import pytest

_REPO_ROOT = os.path.normpath(os.path.join(os.path.dirname(__file__), "..", ".."))
_OPENCLAW_PATH = os.path.join(_REPO_ROOT, "plugins", "openclaw", "openclaw.py")

if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)


class _Response:
    def __init__(self, status_code=200, payload=None, reason="", headers=None, ok=None):
        self.status_code = status_code
        self._payload = payload
        self.reason = reason
        self.headers = headers or {}
        self.ok = (status_code < 400) if ok is None else ok

    def json(self):
        if isinstance(self._payload, Exception):
            raise self._payload
        return self._payload


def _install_stubs():
    config_stub = types.ModuleType("config")
    config_stub.config_get_by_key = lambda key, default=None: None
    sys.modules["config"] = config_stub

    if "requests" not in sys.modules:
        try:
            import requests  # noqa: F401
        except ImportError:
            requests_stub = types.ModuleType("requests")

            class _RequestException(Exception):
                pass

            requests_stub.RequestException = _RequestException
            requests_stub.Session = object
            requests_stub.Response = _Response
            sys.modules["requests"] = requests_stub


def _load_openclaw():
    _install_stubs()
    spec = importlib.util.spec_from_file_location("openclaw_under_test", _OPENCLAW_PATH)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def oc():
    module = _load_openclaw()
    module._completed = []
    module._in_flight = 0
    module._seq = 0
    yield module
    module._completed = []
    module._in_flight = 0


def test_empty_message_is_refused_without_a_worker(oc):
    for message in ("", "   ", "\n\t "):
        result = json.loads(oc.send(message, "http://gw", "main"))
        assert result["status"] == "error"
        assert result["type"] == "invalid_input"
    assert oc._in_flight == 0
    assert oc.take_completed() == ""


def test_accepted_envelope_carries_id_and_task_echo(oc, monkeypatch):
    monkeypatch.setattr(oc, "_run", lambda *a, **k: json.dumps({"status": "ok", "reply": "r"}))
    accepted = json.loads(oc.send("a task worth doing", "http://gw", "main"))
    assert accepted["status"] == "accepted"
    assert accepted["id"] == "oc-1"
    assert accepted["task"] == "a task worth doing"

    long_task = "y" * (oc.TASK_ECHO_CHARS + 50)
    accepted = json.loads(oc.send(long_task, "http://gw", "main"))
    assert accepted["id"] == "oc-2"
    assert len(accepted["task"]) == oc.TASK_ECHO_CHARS


def test_busy_once_max_in_flight_is_reached(oc, monkeypatch):
    release = threading.Event()
    monkeypatch.setattr(
        oc, "_run",
        lambda *a, **k: (release.wait(10), json.dumps({"status": "ok", "reply": "r"}))[1],
    )
    accepted = [json.loads(oc.send(f"task {i}", "http://gw", "main"))
                for i in range(oc.MAX_IN_FLIGHT)]
    assert [a["status"] for a in accepted] == ["accepted"] * oc.MAX_IN_FLIGHT

    refused = json.loads(oc.send("one too many", "http://gw", "main"))
    assert refused["status"] == "error"
    assert refused["type"] == "busy"
    assert oc._in_flight == oc.MAX_IN_FLIGHT

    release.set()
    for _ in range(100):
        if oc._in_flight == 0:
            break
        threading.Event().wait(0.1)
    assert oc._in_flight == 0
    assert len(oc.take_completed().splitlines()) == oc.MAX_IN_FLIGHT
    assert oc.take_completed() == ""


def test_worker_crash_still_produces_a_record(oc, monkeypatch):
    def _boom(*a, **k):
        raise RuntimeError("worker exploded")

    monkeypatch.setattr(oc, "_run", _boom)
    oc.send("a task", "http://gw", "main")
    for _ in range(100):
        if oc._in_flight == 0:
            break
        threading.Event().wait(0.1)
    record = oc.take_completed()
    assert "OPENCLAW_RESULT id=oc-1" in record
    assert "status=error" in record
    assert "worker exploded" in record


def test_record_is_a_single_quote_free_line(oc):
    result = json.dumps({"status": "ok", "responseId": "resp_1", "reply": 'he said "hi"\nand left'})
    record = oc._record("oc-7", 'a "quoted"\ntask', result)
    assert record.startswith("OPENCLAW_RESULT id=oc-7 ")
    assert "status=ok" in record
    assert "responseId=resp_1" in record
    assert '"' not in record
    assert "\n" not in record


def test_record_survives_an_unparsable_result(oc):
    record = oc._record("oc-8", "task", "not json at all")
    assert "status=error" in record
    assert "not json at all" in record


def test_reply_is_truncated_to_max_reply_chars(oc):
    huge = "z" * (oc.MAX_REPLY_CHARS * 2)
    record = oc._record("oc-9", "task", json.dumps({"status": "ok", "reply": huge}))
    assert record.count("z") == oc.MAX_REPLY_CHARS


def test_flatten_collapses_whitespace_and_quotes(oc):
    assert oc._flatten('a  "b"\n\tc', 100) == "a 'b' c"
    assert oc._flatten("abcdef", 3) == "abc"
    assert oc._flatten(None, 100) == "None"


def test_extract_reply_reads_message_items_only(oc):
    payload = {
        "id": "resp_42",
        "output": [
            {"type": "reasoning", "summary": []},
            {"type": "message", "content": [
                {"type": "output_text", "text": "first"},
                {"type": "refusal", "text": "ignored"},
            ]},
            {"type": "message", "content": [{"type": "output_text", "text": "second"}]},
        ],
    }
    result = json.loads(oc._extract_reply(payload))
    assert result["status"] == "ok"
    assert result["responseId"] == "resp_42"
    assert result["reply"] == "first\nsecond"


@pytest.mark.parametrize("payload", [
    {"output": []},
    {"output": [{"type": "reasoning", "summary": []}]},
    {"output": [{"type": "message", "content": [{"type": "output_text", "text": "   "}]}]},
    {},
])
def test_extract_reply_rejects_a_reply_without_text(oc, payload):
    with pytest.raises(oc.OpenClawError):
        oc._extract_reply(payload)


def test_http_error_maps_503_to_a_retryable_startup_error(oc):
    response = _Response(503, {"error": {"message": "booting", "type": "server_starting"}},
                         headers={"Retry-After": "7"})
    error = oc._http_error(response)
    assert isinstance(error, oc.OpenClawStartupError)
    assert error.retry_after == 7.0
    assert "booting" in error.msg

    response = _Response(503, {"error": {"message": "booting"}}, headers={"Retry-After": "soon"})
    assert oc._http_error(response).retry_after == 1.0


def test_http_error_maps_other_codes_to_a_plain_error(oc):
    response = _Response(401, {"error": {"message": "bad token", "type": "invalid_token"}})
    error = oc._http_error(response)
    assert not isinstance(error, oc.OpenClawStartupError)
    assert "401" in error.msg and "bad token" in error.msg

    response = _Response(500, ValueError("not json"), reason="Server Error")
    assert "Server Error" in oc._http_error(response).msg


def test_endpoint_rewrites_websocket_schemes(oc):
    assert oc._endpoint("http://gw:1/") == "http://gw:1" + oc.RESPONSES_PATH
    assert oc._endpoint("  https://gw  ") == "https://gw" + oc.RESPONSES_PATH
    assert oc._endpoint("ws://gw:1") == "http://gw:1" + oc.RESPONSES_PATH
    assert oc._endpoint("wss://gw") == "https://gw" + oc.RESPONSES_PATH


def test_request_target_prefers_the_proxy_and_sends_no_token(oc, monkeypatch):
    monkeypatch.setattr(oc, "config_get_by_key", lambda key, default=None: "http://localhost:8080/")
    monkeypatch.setenv("OMEGA_OPENCLAW_TOKEN", "must-not-be-used")
    url, headers = oc._request_target("http://gw:18789")
    assert url == "http://localhost:8080/openclaw" + oc.RESPONSES_PATH
    assert headers == {}


def test_request_target_falls_back_to_a_direct_call_with_the_token(oc, monkeypatch):
    monkeypatch.setattr(oc, "config_get_by_key", lambda key, default=None: None)
    monkeypatch.setenv("OMEGA_OPENCLAW_TOKEN", "s3cret")
    url, headers = oc._request_target("http://gw:18789")
    assert url == "http://gw:18789" + oc.RESPONSES_PATH
    assert headers == {"Authorization": "Bearer s3cret"}


def test_request_target_refuses_when_it_cannot_authenticate(oc, monkeypatch):
    monkeypatch.setattr(oc, "config_get_by_key", lambda key, default=None: None)
    monkeypatch.setenv("OMEGA_OPENCLAW_TOKEN", "   ")
    with pytest.raises(oc.OpenClawError):
        oc._request_target("http://gw:18789")


def test_take_completed_drains_once(oc):
    oc._completed = ["first", "second"]
    assert oc.take_completed() == "first\nsecond"
    assert oc.take_completed() == ""
