import importlib
import importlib.util
import json
import sys
import time
import types
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]

@pytest.fixture
def handler(monkeypatch):
    auth = types.ModuleType("auth")
    auth.is_auth_enabled = lambda: True
    monkeypatch.setitem(sys.modules, "auth", auth)

    logger_mod = types.ModuleType("src.logger")
    logger_mod.get_logger = lambda name: __import__("logging").getLogger(name)
    monkeypatch.setitem(sys.modules, "src.logger", logger_mod)

    mp_mod = types.ModuleType("memory_portability")
    mp_mod.MemoryTransfer = object
    monkeypatch.setitem(sys.modules, "memory_portability", mp_mod)

    spec = importlib.util.spec_from_file_location(
        "memory_export_under_test",
        REPO_ROOT / "channels" / "memory_export.py",
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    module.is_export_enabled = lambda: True
    return module

def test_export_command_requires_policy_but_not_auth(handler):
    assert "Export requested" in handler.handle_export_command("/memory-export both")
    handler.is_export_enabled = lambda: False
    assert handler.handle_export_command("/memory-export both") is None

def test_expired_and_other_owner_tokens_cannot_start_export(handler):
    token = handler.handle_export_command("/memory-export history", "owner-a").split()[-1]
    assert "Invalid token" in handler.handle_export_command(
        "/memory-export confirm wrong", "owner-a"
    )
    assert "No pending export" in handler.handle_export_command(
        f"/memory-export confirm {token}", "owner-b"
    )
    token_state = handler._pending_requests["owner-a"]
    handler._pending_requests["owner-a"] = (*token_state[:2], time.monotonic() - 1)
    assert "expired" in handler.handle_export_command(
        f"/memory-export confirm {token}", "owner-a"
    ).lower()

def test_confirmation_exports_immediately(handler):
    exported = []
    handler._get_transfer = lambda: types.SimpleNamespace(
        export=lambda component: exported.append(component) or {
            "filename": "memory.tar.gz",
            "size": 1,
            "sha256": "abc",
            "record_count": 1,
        }
    )
    token = handler.handle_export_command("/memory-export both", "owner-a").split()[-1]
    reply = handler.handle_export_command(f"/memory-export confirm {token}", "owner-a")
    assert exported == ["both"]
    assert "memory.tar.gz" in reply
    assert "SHA-256:  abc" in reply

def test_websocket_ignores_memory_export(monkeypatch):
    config = types.ModuleType("config")
    config.config_get_by_key = lambda key, default=None: default
    logger_mod = types.ModuleType("src.logger")
    logger_mod.get_logger = lambda name: __import__("logging").getLogger(name)
    control = types.ModuleType("memory_export")
    control.is_export_command = lambda text: text.startswith("/memory-export")
    channels = types.ModuleType("channels")
    channels.CommChannel = object
    channels.registerCommChannel = lambda *args: None
    monkeypatch.setitem(sys.modules, "config", config)
    monkeypatch.setitem(sys.modules, "src.logger", logger_mod)
    monkeypatch.setitem(sys.modules, "memory_export", control)
    monkeypatch.setitem(sys.modules, "channels", channels)

    spec = importlib.util.spec_from_file_location(
        "wschat_under_test", REPO_ROOT / "channels" / "wschat.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    received = []
    replies = []
    module._enqueue_user_message = lambda *args: received.append(args)
    module.send_message = replies.append

    module._handle_frame(json.dumps({
        "type": "user_message", "seq": 1, "text": "/memory-export both"
    }))
    assert received == []
    assert replies == ["Memory export is not supported on the WebSocket channel."]

def test_shared_dispatcher_consumes_control_commands(monkeypatch):
    control = types.ModuleType("memory_export")
    control.is_export_command = lambda text: text == "/memory-export both"
    control.handle_export_command = lambda text, owner: "Export requested"
    monkeypatch.setitem(sys.modules, "memory_export", control)

    monkeypatch.delitem(sys.modules, "channels", raising=False)
    channels = importlib.import_module("channels")

    replies = []
    assert channels.handle_control_message(
        "/memory-export both", "telegram:chat:user", replies.append
    )
    assert replies == ["Export requested"]
    assert not channels.handle_control_message("hello", "telegram:chat:user", replies.append)
