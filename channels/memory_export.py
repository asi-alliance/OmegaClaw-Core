"""Shared authenticated /memory-export command handling."""

import os
import secrets
import threading
import time
from pathlib import Path

import auth
from config import config_get_by_key
from src.logger import get_logger
from memory_portability import MemoryTransfer

logger = get_logger(__name__)

_TRANSFER_DIR = Path(os.environ.get("MEMORY_TRANSFER_DIR", "/memory-transfer"))

_transfer = None

def _get_transfer() -> MemoryTransfer:
    global _transfer
    if _transfer is None:
        _transfer = MemoryTransfer(_TRANSFER_DIR)
    return _transfer

def start_export_job(component, on_complete=None):
    return _get_transfer().start_export_job(component, on_complete=on_complete)

def get_export_status(job_id):
    return _get_transfer().get_export_status(job_id)

_TOKEN_TTL_SECONDS = 60

_token_lock = threading.Lock()
_pending_requests: dict[str, tuple[str, str, float]] = {}
_job_owners: dict[str, str] = {}

_VALID_COMPONENTS = ("history", "ltm", "both")

def is_export_enabled() -> bool:
    value = os.environ.get("OMEGACLAW_memoryExportEnabled")
    if value is None:
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
    deliver_completion=lambda _message: None,
) -> str | None:
    stripped = text.strip()

    if not is_export_command(stripped):
        return None

    if not auth.is_auth_enabled():
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
        return _handle_confirm(owner_key, arg, deliver_completion)

    if sub == "status":
        return _handle_status(owner_key, arg)

    return (
        "Unknown /memory-export command. "
        "Use: /memory-export history|ltm|both  or  "
        "/memory-export confirm <token>  or  "
        "/memory-export status <job-id>"
    )

def _handle_request(owner_key: str, component: str) -> str:
    with _token_lock:
        token = _issue_token(owner_key, component)
    logger.info(f"memory_export: issued confirmation token for component={component}")
    return (
        f"Export requested for: {component}\n"
        f"Confirm within {_TOKEN_TTL_SECONDS}s:\n"
        f"/memory-export confirm {token}"
    )

def _handle_confirm(owner_key: str, token: str, deliver_completion) -> str:
    if not token:
        return "Usage: /memory-export confirm <token>"

    with _token_lock:
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
        job_id = start_export_job(
            component,
            lambda completed_job_id, status: deliver_completion(
                _format_completion(completed_job_id, status)
            ),
        )
    except Exception as exc:
        logger.exception(f"memory_export: failed to start export job: {exc}")
        return f"Export failed to start: {exc}"

    logger.info(f"memory_export: export job {job_id} started (component={component})")
    with _token_lock:
        _job_owners[job_id] = owner_key
    return (
        f"Export started. Job ID: {job_id}\n"
        f"Check progress: /memory-export status {job_id}"
    )

def _handle_status(owner_key: str, job_id: str) -> str:
    if not job_id:
        return "Usage: /memory-export status <job-id>"

    with _token_lock:
        if _job_owners.get(job_id) != owner_key:
            return f"Export {job_id}: unknown job ID"

    status = get_export_status(job_id)
    state = status.get("status", "unknown")

    if state == "running":
        return f"Export {job_id}: running…"

    if state == "done":
        return (
            f"Export {job_id}: done\n"
            f"File:     {status.get('filename')}\n"
            f"Size:     {status.get('size')} bytes\n"
            f"SHA-256:  {status.get('checksum')}\n"
            f"Records:  {status.get('record_count')}"
        )

    if state == "failed":
        return f"Export {job_id}: failed — {status.get('error')}"

    return f"Export {job_id}: unknown job ID"

def _format_completion(job_id: str, status: dict) -> str:
    if status.get("status") == "done":
        return (
            f"Export {job_id}: done\n"
            f"File:     {status.get('filename')}\n"
            f"Size:     {status.get('size')} bytes\n"
            f"SHA-256:  {status.get('checksum')}\n"
            f"Records:  {status.get('record_count')}"
        )
    return f"Export {job_id}: failed — {status.get('error')}"
