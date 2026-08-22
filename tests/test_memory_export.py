import importlib
import importlib.util
import json
import os
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

    monkeypatch.delitem(sys.modules, "memory_portability", raising=False)

    spec = importlib.util.spec_from_file_location(
        "memory_export_under_test",
        REPO_ROOT / "src" / "memory_export.py",
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    module.is_export_enabled = lambda: True
    return module

def test_export_command_requires_policy_but_not_auth(handler):
    assert "Export requested" in handler.handle_export_command("/memory-export both")
    handler.is_export_enabled = lambda: False
    assert handler.handle_export_command("/memory-export both") is None

def test_module_import_does_not_require_memory_portability(handler):
    assert "memory_portability" not in sys.modules
    assert handler.is_export_command("/memory-export both")

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

def test_transfer_uses_effective_runtime_embedding_provider(handler, monkeypatch):
    created = []

    class FakeTransfer:
        def __init__(self, transfer_dir):
            created.append((transfer_dir, os.environ["EMBEDDING_PROVIDER"]))

    monkeypatch.delenv("EMBEDDING_PROVIDER", raising=False)
    mp_mod = types.ModuleType("memory_portability")
    mp_mod.MemoryTransfer = FakeTransfer
    monkeypatch.setitem(sys.modules, "memory_portability", mp_mod)
    monkeypatch.setattr(
        handler,
        "config_get_by_key",
        lambda key, default=None: "OpenAI" if key == "embeddingprovider" else default,
    )
    handler._transfer = None

    transfer = handler._get_transfer()

    assert isinstance(transfer, FakeTransfer)
    assert created == [(handler._TRANSFER_DIR, "OpenAI")]

def test_websocket_defers_memory_export_to_core_dispatch(monkeypatch):
    config = types.ModuleType("config")
    config.config_get_by_key = lambda key, default=None: default
    logger_mod = types.ModuleType("src.logger")
    logger_mod.get_logger = lambda name: __import__("logging").getLogger(name)
    channels = types.ModuleType("channels")
    channels.CommChannel = object
    channels.registerCommChannel = lambda *args: None
    monkeypatch.setitem(sys.modules, "config", config)
    monkeypatch.setitem(sys.modules, "src.logger", logger_mod)
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
    assert received == [(1, "/memory-export both")]
    assert replies == []


def test_commchannel_receive_dispatches_control_commands(monkeypatch):
    authenticated_user_id = "telegram-user-123"
    auth = types.ModuleType("auth")
    auth.is_auth_enabled = lambda: True
    auth.get_channel_authenticated_user_id = lambda channel: (
        authenticated_user_id if channel == "TELEGRAM" else None
    )
    monkeypatch.setitem(sys.modules, "auth", auth)

    owners: list[str] = []
    control = types.ModuleType("src.memory_export")
    control.is_export_command = lambda text: text == "/memory-export both"
    control.handle_export_command = lambda text, owner: (
        owners.append(owner) or "Export requested"
    )
    monkeypatch.setitem(sys.modules, "src.memory_export", control)

    monkeypatch.delitem(sys.modules, "channels", raising=False)
    channels = importlib.import_module("channels")

    replies: list[str] = []
    channels._commchannel = types.SimpleNamespace(
        receive=lambda: "alice: /memory-export both | alice: hello",
        send=replies.append,
    )
    channels._commchannel_id = "telegram"

    assert channels.commChannelReceive() == "alice: hello"
    assert replies == ["Export requested"]
    assert owners == [f"telegram:{authenticated_user_id}"]


def test_commchannel_receive_rejects_unsupported_control_channel(monkeypatch):
    auth = types.ModuleType("auth")
    auth.is_auth_enabled = lambda: True
    auth.get_channel_authenticated_user_id = lambda *_: "websocket-user"
    monkeypatch.setitem(sys.modules, "auth", auth)

    control = types.ModuleType("src.memory_export")
    control.is_export_command = lambda text: text == "/memory-export both"
    control.handle_export_command = lambda *_: pytest.fail(
        "unsupported channels must not execute exports"
    )
    monkeypatch.setitem(sys.modules, "src.memory_export", control)

    monkeypatch.delitem(sys.modules, "channels", raising=False)
    channels = importlib.import_module("channels")

    replies: list[str] = []
    channels._commchannel = types.SimpleNamespace(
        receive=lambda: "/memory-export both",
        send=replies.append,
    )
    channels._commchannel_id = "websocket"

    assert channels.commChannelReceive() == ""
    assert replies == ["Memory export is not supported on the WebSocket channel."]


def test_commchannel_receive_does_not_consume_command_mentions(monkeypatch):
    auth = types.ModuleType("auth")
    auth.is_auth_enabled = lambda: False
    auth.get_channel_authenticated_user_id = lambda *_: pytest.fail(
        "disabled authentication must not read a persisted owner"
    )
    monkeypatch.setitem(sys.modules, "auth", auth)

    control = types.ModuleType("src.memory_export")
    control.is_export_command = lambda text: text == "/memory-export both"
    control.handle_export_command = lambda *_: pytest.fail(
        "a command mentioned in normal text must not execute"
    )
    monkeypatch.setitem(sys.modules, "src.memory_export", control)

    monkeypatch.delitem(sys.modules, "channels", raising=False)
    channels = importlib.import_module("channels")

    message = "alice: please use /memory-export both"
    channels._commchannel = types.SimpleNamespace(
        receive=lambda: message,
        send=lambda *_: pytest.fail("normal messages must not generate replies"),
    )
    channels._commchannel_id = "telegram"

    assert channels.commChannelReceive() == message


def test_commchannel_receive_falls_back_to_sender_without_auth(monkeypatch):
    auth = types.ModuleType("auth")
    auth.is_auth_enabled = lambda: False
    auth.get_channel_authenticated_user_id = lambda *_: pytest.fail(
        "disabled authentication must not read a persisted owner"
    )
    monkeypatch.setitem(sys.modules, "auth", auth)

    owners: list[str] = []
    control = types.ModuleType("src.memory_export")
    control.is_export_command = lambda text: text == "/memory-export both"
    control.handle_export_command = lambda text, owner: (
        owners.append(owner) or "Export requested"
    )
    monkeypatch.setitem(sys.modules, "src.memory_export", control)

    monkeypatch.delitem(sys.modules, "channels", raising=False)
    channels = importlib.import_module("channels")

    replies: list[str] = []
    channels._commchannel = types.SimpleNamespace(
        receive=lambda: "alice: /memory-export both",
        send=replies.append,
    )
    channels._commchannel_id = "telegram"

    assert channels.commChannelReceive() == ""
    assert replies == ["Export requested"]
    assert owners == ["telegram:alice"]
