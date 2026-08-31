import importlib
import importlib.util
import hashlib
import json
import os
import sys
import types
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]

@pytest.fixture
def handler(monkeypatch):
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

def test_export_command_requires_policy(handler):
    exported = []
    handler._get_transfer = lambda: types.SimpleNamespace(
        export=lambda component: exported.append(component) or {
            "filename": "memory.tar.gz",
            "size": 1,
            "sha256": "abc",
            "record_count": 1,
        }
    )

    assert "Memory export complete" in handler.handle_export_command(
        "/memory-export both", "authenticated-user"
    )
    assert exported == ["both"]

    handler.is_export_enabled = lambda: False
    assert handler.handle_export_command(
        "/memory-export both", "authenticated-user"
    ) is None
    assert exported == ["both"]


def test_export_requires_authenticated_user(handler):
    handler._get_transfer = lambda: pytest.fail(
        "an unauthenticated command must not start an export"
    )

    assert handler.handle_export_command("/memory-export both") == (
        "Memory export denied: an authenticated user is required."
    )

def test_module_import_does_not_require_memory_portability(handler):
    assert "memory_portability" not in sys.modules
    assert handler.is_export_command("/memory-export both")

@pytest.mark.parametrize("component", ["history", "ltm", "both"])
def test_export_runs_immediately(handler, component):
    exported = []
    handler._get_transfer = lambda: types.SimpleNamespace(
        export=lambda component: exported.append(component) or {
            "filename": "memory.tar.gz",
            "size": 1,
            "sha256": "abc",
            "record_count": 1,
        }
    )
    reply = handler.handle_export_command(
        f"/memory-export {component}", "authenticated-user"
    )
    assert exported == [component]
    assert "memory.tar.gz" in reply
    assert "SHA-256:  abc" in reply


def test_confirmation_command_is_no_longer_supported(handler):
    handler._get_transfer = lambda: pytest.fail(
        "the removed confirmation command must not start an export"
    )

    reply = handler.handle_export_command(
        "/memory-export confirm old-token", "authenticated-user"
    )

    assert reply == (
        "Unknown /memory-export command. "
        "Use: /memory-export history|ltm|both"
    )

def test_transfer_uses_effective_runtime_embedding_provider(handler, monkeypatch):
    created = []

    class FakeTransfer:
        def __init__(self, **kwargs):
            created.append({
                **kwargs,
                "embedding_provider": os.environ["EMBEDDING_PROVIDER"],
            })

    monkeypatch.delenv("EMBEDDING_PROVIDER", raising=False)
    package = types.ModuleType("memory_portability")
    package.MemoryTransfer = FakeTransfer
    monkeypatch.setitem(sys.modules, "memory_portability", package)
    monkeypatch.setattr(handler, "create_memory_store", lambda: "configured-store")
    monkeypatch.setattr(
        handler,
        "config_get_by_key",
        lambda key, default=None: "OpenAI" if key == "embeddingprovider" else default,
    )
    handler._transfer = None

    transfer = handler._get_transfer()

    assert transfer is handler._transfer
    assert created == [{
        "transfer_dir": handler._TRANSFER_DIR,
        "store": "configured-store",
        "embedding_provider": "OpenAI",
    }]


def test_memory_store_receives_explicit_omegaclaw_storage_configuration(
    handler,
    monkeypatch,
    tmp_path,
):
    created_stores = []

    class FakeStore:
        def __init__(self, **kwargs):
            created_stores.append(kwargs)

    package = types.ModuleType("memory_portability")
    package.__path__ = []
    storage = types.ModuleType("memory_portability.storage")
    storage.MemoryStore = FakeStore
    monkeypatch.setitem(sys.modules, "memory_portability", package)
    monkeypatch.setitem(sys.modules, "memory_portability.storage", storage)

    memory_dir = tmp_path / "custom-memory"
    chroma_path = tmp_path / "custom-chroma"
    monkeypatch.setattr(handler, "_resolve_memory_dir", lambda: memory_dir)
    monkeypatch.setattr(handler, "_resolve_chroma_path", lambda: chroma_path)

    store = handler.create_memory_store()

    assert isinstance(store, FakeStore)
    assert created_stores == [
        {
            "memory_dir": memory_dir,
            "chroma_path": chroma_path,
            "collection_name": "memories",
        }
    ]


def test_storage_paths_are_resolved_from_omegaclaw_config(
    handler,
    monkeypatch,
    tmp_path,
):
    configured = {
        "memoryDirectory": str(tmp_path / "configured-memory"),
        "chromaDbPath": str(tmp_path / "configured-chroma"),
    }
    monkeypatch.delenv("CHROMA_DB_PATH", raising=False)
    monkeypatch.setattr(
        handler,
        "config_get_by_key",
        lambda key, default=None: configured.get(key, default),
    )

    assert handler._resolve_memory_dir() == tmp_path / "configured-memory"
    assert handler._resolve_chroma_path() == tmp_path / "configured-chroma"


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

    principals: list[str] = []
    control = types.ModuleType("src.memory_export")
    control.is_export_command = lambda text: text == "/memory-export both"
    control.handle_export_command = lambda text, principal: (
        principals.append(principal) or "Memory export complete"
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
    assert principals == [authenticated_user_id]
    assert replies == ["Memory export complete"]


def test_commchannel_receive_denies_export_without_authenticated_user(monkeypatch):
    auth = types.ModuleType("auth")
    auth.is_auth_enabled = lambda: False
    auth.get_channel_authenticated_user_id = lambda *_: pytest.fail(
        "disabled authentication must not resolve a user ID"
    )
    monkeypatch.setitem(sys.modules, "auth", auth)

    control = types.ModuleType("src.memory_export")
    control.is_export_command = lambda text: text == "/memory-export both"
    control.handle_export_command = lambda text, principal: (
        "Memory export denied: an authenticated user is required."
        if principal is None
        else pytest.fail("an unauthenticated command received a principal")
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
    assert replies == ["Memory export denied: an authenticated user is required."]


def test_commchannel_receive_dispatches_websocket_export(monkeypatch):
    websocket_token = "private-websocket-token"
    config = types.ModuleType("config")
    config.config_get_by_key = lambda key, default=None: (
        websocket_token if key == "WS_TOKEN" else default
    )
    monkeypatch.setitem(sys.modules, "config", config)

    commands: list[str] = []
    principals: list[str] = []
    control = types.ModuleType("src.memory_export")
    control.is_export_command = lambda text: text == "/memory-export both"
    control.handle_export_command = lambda text, principal: (
        commands.append(text)
        or principals.append(principal)
        or "Memory export complete"
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
    assert commands == ["/memory-export both"]
    assert principals == [
        f"websocket:{hashlib.sha256(websocket_token.encode('utf-8')).hexdigest()}"
    ]
    assert websocket_token not in principals[0]
    assert replies == ["Memory export complete"]


def test_websocket_export_requires_bearer_token(monkeypatch):
    config = types.ModuleType("config")
    config.config_get_by_key = lambda key, default=None: default
    monkeypatch.setitem(sys.modules, "config", config)

    monkeypatch.delitem(sys.modules, "channels", raising=False)
    channels = importlib.import_module("channels")
    channels._commchannel_id = "websocket"

    assert channels._authenticated_export_principal() is None


def test_commchannel_receive_does_not_consume_command_mentions(monkeypatch):
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
