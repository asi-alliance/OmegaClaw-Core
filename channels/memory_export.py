"""Shared /memory-export command handling."""

import secrets
import threading
import time
from pathlib import Path

from config import config_get_by_key
from src.logger import get_logger
from memory_portability import MemoryTransfer

logger = get_logger(__name__)

_TRANSFER_DIR = Path("/memory-transfer")

_transfer = None

def _get_transfer() -> MemoryTransfer:
    global _transfer
    if _transfer is None:
        _transfer = MemoryTransfer(_TRANSFER_DIR)
    return _transfer

_TOKEN_TTL_SECONDS = 60

_request_lock = threading.Lock()
_pending_requests: dict[str, tuple[str, str, float]] = {}

_VALID_COMPONENTS = ("history", "ltm", "both")

def is_export_enabled() -> bool:
    value = config_get_by_key("memoryExportEnabled", False)
    return value is True or (
        isinstance(value, str) and value.strip().lower() == "true"
    )

def is_export_command(text: str) -> bool:
    command = text.strip().split(None, 1)
    if not command:
        return False
    name = command[0].lower()
    return name == "/memory-export" or name.startswith("/memory-export@")

def _command_arguments(text: str) -> str:
    parts = text.strip().split(None, 1)
    return parts[1].strip() if len(parts) == 2 else ""

def _issue_token(owner_key: str, component: str) -> str:
    token = secrets.token_hex(8)
    _pending_requests[owner_key] = (
        token,
        component,
        time.monotonic() + _TOKEN_TTL_SECONDS,
    )
    return token

def handle_export_command(
    text: str,
    owner_key: str = "default-owner",
) -> str | None:
    stripped = text.strip()

    if not is_export_command(stripped):
        return None

    if not is_export_enabled():
        return None

    rest = _command_arguments(stripped)
    parts = rest.split(None, 1)
    sub = parts[0].lower() if parts else ""
    arg = parts[1].strip() if len(parts) > 1 else ""

    if sub in _VALID_COMPONENTS:
        return _handle_request(owner_key, sub)

    if sub == "confirm":
        return _handle_confirm(owner_key, arg)

    return (
        "Unknown /memory-export command. "
        "Use: /memory-export history|ltm|both  or  "
        "/memory-export confirm <token>"
    )

def _handle_request(owner_key: str, component: str) -> str:
    with _request_lock:
        token = _issue_token(owner_key, component)
    logger.info(f"memory_export: issued confirmation token for component={component}")
    return (
        f"Export requested for: {component}\n"
        f"Confirm within {_TOKEN_TTL_SECONDS}s:\n"
        f"/memory-export confirm {token}"
    )

def _handle_confirm(owner_key: str, token: str) -> str:
    if not token:
        return "Usage: /memory-export confirm <token>"

    with _request_lock:
        pending = _pending_requests.get(owner_key)
        if pending is None:
            return "No pending export request. Start with /memory-export history|ltm|both"
        expected_token, component, expires_at = pending
        if time.monotonic() > expires_at:
            del _pending_requests[owner_key]
            return "Confirmation token expired. Start again with /memory-export history|ltm|both"
        if not secrets.compare_digest(expected_token, token):
            return "Invalid token."
        del _pending_requests[owner_key]
    try:
        result = _get_transfer().export(component)
        return _format_export(result)
    except Exception as exc:
        logger.exception(f"memory_export: export failed: {exc}")
        return f"Memory export failed: {exc}"

def _format_export(result: dict) -> str:
    return (
        "Memory export complete\n"
        f"File:     {result.get('filename')}\n"
        f"Size:     {result.get('size')} bytes\n"
        f"SHA-256:  {result.get('sha256', result.get('checksum'))}\n"
        f"Records:  {result.get('record_count')}"
    )
