import importlib
import importlib.util
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

def test_export_command_requires_auth_and_policy(handler):
    handler.auth.is_auth_enabled = lambda: False
    assert handler.handle_export_command("/memory-export both") is None
    handler.auth.is_auth_enabled = lambda: True
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

def test_export_completion_is_delivered_after_loop_processing(handler):
    delivered = []
    exported = []
    handler._get_transfer = lambda: types.SimpleNamespace(
        export=lambda component: exported.append(component) or {
            "filename": "memory.tar.gz",
            "size": 1,
            "checksum": "abc",
            "record_count": 1,
        }
    )
    token = handler.handle_export_command("/memory-export both", "owner-a", delivered.append).split()[-1]
    delivered.append(
        handler.handle_export_command(
            f"/memory-export confirm {token}", "owner-a", delivered.append
        )
    )
    assert delivered == ["Export queued. It will run in the next agent iteration."]
    assert exported == []
    handler.process_pending_export()
    assert exported == ["both"]
    assert "memory.tar.gz" in delivered[-1]

def test_failed_completion_delivery_does_not_interrupt_loop(handler):
    handler._get_transfer = lambda: types.SimpleNamespace(export=lambda _component: {})
    token = handler.handle_export_command("/memory-export history").split()[-1]

    def fail_delivery(_message):
        raise RuntimeError("send failed")

    handler.handle_export_command(f"/memory-export confirm {token}", deliver_completion=fail_delivery)
    handler.process_pending_export()

def test_shared_dispatcher_consumes_control_commands(monkeypatch):
    control = types.ModuleType("memory_export")
    control.is_export_command = lambda text: text == "/memory-export both"
    control.handle_export_command = lambda text, owner, deliver: "Export requested"
    processed = []
    control.process_pending_export = lambda: processed.append(True)
    monkeypatch.setitem(sys.modules, "memory_export", control)

    monkeypatch.delitem(sys.modules, "channels", raising=False)
    channels = importlib.import_module("channels")

    replies = []
    assert channels.handle_control_message(
        "/memory-export both", "telegram:chat:user", replies.append
    )
    assert replies == ["Export requested"]
    assert not channels.handle_control_message("hello", "telegram:chat:user", replies.append)
    channels.process_control_messages()
    assert processed == [True]
