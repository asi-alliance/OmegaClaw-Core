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
    logger = types.ModuleType("src.logger")
    logger.get_logger = lambda name: __import__("logging").getLogger(name)
    monkeypatch.setitem(sys.modules, "src.logger", logger)
    transfer = types.ModuleType("src.memory_transfer")
    transfer.is_export_enabled = lambda: True
    transfer.start_export_job = lambda component, on_complete=None: "job-1"
    transfer.get_export_status = lambda job_id: {"status": "unknown"}
    monkeypatch.setitem(sys.modules, "src.memory_transfer", transfer)
    spec = importlib.util.spec_from_file_location(
        "memory_export_handler_under_test", REPO_ROOT / "channels" / "memory_export_handler.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_export_command_requires_auth_and_policy(handler):
    handler.auth.is_auth_enabled = lambda: False
    assert handler.handle_export_command("/memory-export both") is None
    handler.auth.is_auth_enabled = lambda: True
    handler.is_export_enabled = lambda: False
    assert handler.handle_export_command("/memory-export both") is None


def test_confirmation_starts_only_the_requested_export(handler):
    started = []
    handler.start_export_job = lambda component, on_complete: started.append(component) or "job-1"
    token = handler.handle_export_command("/memory-export ltm").split()[-1]

    assert "Invalid token" in handler.handle_export_command("/memory-export confirm wrong")
    assert "job-1" in handler.handle_export_command(f"/memory-export confirm {token}")
    assert started == ["ltm"]


def test_expired_and_other_owner_tokens_cannot_start_export(handler):
    token = handler.handle_export_command("/memory-export history", "owner-a").split()[-1]
    assert "No pending export" in handler.handle_export_command(
        f"/memory-export confirm {token}", "owner-b"
    )
    token_state = handler._pending_requests["owner-a"]
    handler._pending_requests["owner-a"] = (*token_state[:2], time.monotonic() - 1)
    assert "expired" in handler.handle_export_command(
        f"/memory-export confirm {token}", "owner-a"
    ).lower()


def test_completion_and_status_are_limited_to_requesting_owner(handler):
    delivered = []

    def start_job(component, callback):
        callback("job-1", {"status": "done", "filename": "memory.tar.gz"})
        return "job-1"

    handler.start_export_job = start_job
    token = handler.handle_export_command("/memory-export both", "owner-a", delivered.append).split()[-1]
    handler.handle_export_command(f"/memory-export confirm {token}", "owner-a", delivered.append)

    assert "memory.tar.gz" in delivered[0]
    assert "unknown job ID" in handler.handle_export_command("/memory-export status job-1", "owner-b")
