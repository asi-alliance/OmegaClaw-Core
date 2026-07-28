"""Minimal JSON chat adapter over WebSocket.

Connects to a chat server that speaks a small JSON frame format and exposes
an inbox/outbox surface: ``start_websocket`` / ``stop_websocket`` /
``send_message`` / ``getLastMessage``.

Connection
----------
URL and optional bearer token are read from ``WS_URL`` / ``WS_TOKEN``, or
passed to ``start_websocket`` directly. When a token is present it is sent
as ``Authorization: Bearer <token>``. The adapter reconnects automatically
with exponential backoff (1s -> 30s, +/-20% jitter) and is safe to start
once at process startup.

Frames
------
All frames are UTF-8 JSON objects with a ``type`` field; unknown types are
logged and ignored.

Server -> client:

  ``{"type": "user_message", "seq": <int>, "text": <str>}``
      A new inbound message. ``seq`` is a monotonically increasing integer
      assigned by the server; the client uses it for ordering and dedup.

  ``{"type": "ack", "seq": <int|null>, "client_seq": <str>}``
      Acknowledges a previously sent ``agent_message`` identified by
      ``client_seq``. Informational; logged only.

  ``{"type": "error", "code": <str>, "message": <str>}``
      Server-side error. Logged; the connection is left open.

Client -> server:

  ``{"type": "agent_message", "client_seq": <str>, "text": <str>}``
      A message produced by the local agent. ``client_seq`` is a
      client-generated idempotency key (UUID hex) so the server can dedupe
      retries after reconnect.

  ``{"type": "resume", "last_seen_seq": <int|null>}``
      Sent immediately after every (re)connect. The server should replay
      any ``user_message`` frames with ``seq > last_seen_seq``; on the
      first connection ``last_seen_seq`` is null.

Delivery semantics
------------------
- Inbound messages are buffered in a bounded inbox (256 entries) and drained
  by ``getLastMessage``, which joins pending texts with ``' | '`` and
  advances ``last_seen_seq``.
- Outbound messages sent while disconnected are queued in a bounded outbox
  (100 entries) and flushed after the next successful connect, before any
  new inbound traffic is processed.
- Duplicate ``user_message`` frames (``seq <= last_seen_seq``, or already in
  the inbox) are dropped, so server replays after resume are idempotent.
"""

import json
import os
import random
import threading
import time
import uuid
from collections import deque
from pathlib import Path
import sys
from config import config_get_by_key

_REPO_ROOT = Path(__file__).resolve().parents[1]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from src.logger import get_logger
try:
    import channels
except ModuleNotFoundError:
    import src.channels as channels

logger = get_logger(__name__)

_running = False
_thread = None
_ws = None
_connected = False

_state_lock = threading.Lock()
_send_lock = threading.Lock()
_msg_lock = threading.Lock()

_ws_url = ""
_ws_token = ""
_inbox = deque(maxlen=256)
_outbox = deque(maxlen=100)
_last_seen_seq = None


def _ensure_websockets_available():
    from websockets.sync.client import connect  # noqa: F401


def _connect_client(ws_url, ws_token):
    from websockets.sync.client import connect

    headers = {}
    if ws_token:
        headers["Authorization"] = f"Bearer {ws_token}"
    kwargs = {
        "open_timeout": 15,
        "close_timeout": 5,
        "ping_interval": 20,
        "ping_timeout": 20,
        "max_size": 64 * 1024,
    }

    try:
        return connect(ws_url, additional_headers=headers, **kwargs)
    except TypeError as e:
        logger.warning(f"additional_headers unsupported, retrying with extra_headers: {e}")
        return connect(ws_url, extra_headers=headers, **kwargs)  # for websockets<=4.14


def _resolve_connection_inputs(ws_url=None, ws_token=None):
    resolved_url = str(ws_url or os.environ.get("WS_URL", "")).strip()
    resolved_token = str(ws_token or os.environ.get("WS_TOKEN", "")).strip()

    if not resolved_url:
        raise ValueError("WS_URL is required")

    return resolved_url, resolved_token


def _build_resume_frame():
    with _msg_lock:
        return {"type": "resume", "last_seen_seq": _last_seen_seq}


def _set_connection(ws):
    global _ws, _connected
    with _state_lock:
        _ws = ws
        _connected = True


def _clear_connection(ws=None):
    global _ws, _connected
    with _state_lock:
        if ws is not None and _ws is not ws:
            return
        _ws = None
        _connected = False


def _send_json(payload, ws=None):
    target_ws = ws
    if target_ws is None:
        with _state_lock:
            target_ws = _ws

    if target_ws is None:
        raise RuntimeError("WebSocket channel is not connected")

    message = json.dumps(payload)
    with _send_lock:
        target_ws.send(message)


def _enqueue_user_message(seq, text):
    with _msg_lock:
        if _last_seen_seq is not None and seq <= _last_seen_seq:
            return False
        if _inbox and seq <= _inbox[-1][0]:
            return False
        _inbox.append((seq, text))
        return True


def _handle_frame(raw_message):
    if isinstance(raw_message, bytes):
        raw_message = raw_message.decode("utf-8", errors="ignore")

    try:
        frame = json.loads(raw_message)
    except json.JSONDecodeError:
        logger.warning(f"Ignoring non-JSON frame: {raw_message!r}")
        return

    if not isinstance(frame, dict):
        logger.warning(f"Ignoring unexpected frame payload: {frame!r}")
        return

    frame_type = frame.get("type")
    if frame_type == "user_message":
        seq = frame.get("seq")
        text = frame.get("text")
        if not isinstance(seq, int) or not isinstance(text, str):
            logger.warning(f"Ignoring malformed user_message frame: {frame!r}")
            return
        _enqueue_user_message(seq, text)
        return

    if frame_type == "ack":
        logger.info(f"Ack received for seq={frame.get('seq')} client_seq={frame.get('client_seq')}")
        return

    if frame_type == "error":
        logger.error(f"Server error {frame.get('code')}: {frame.get('message')}")
        return

    logger.warning(f"Ignoring unsupported frame type: {frame_type!r}")


def _drain_outbox(ws):
    with _msg_lock:
        pending = list(_outbox)
        _outbox.clear()
    for payload in pending:
        try:
            _send_json(payload, ws=ws)
        except Exception:
            with _msg_lock:
                _outbox.appendleft(payload)
            raise


def _listen_once(ws):
    _send_json(_build_resume_frame(), ws=ws)
    _drain_outbox(ws)
    while _running:
        raw_message = ws.recv()
        if raw_message is None:
            raise RuntimeError("WebSocket closed by peer")
        _handle_frame(raw_message)


def _listener_loop():
    backoff_seconds = 1.0
    logger.info(f"Starting adapter for {_ws_url}")

    while _running:
        active_ws = None
        try:
            with _connect_client(_ws_url, _ws_token) as ws:
                active_ws = ws
                _set_connection(ws)
                logger.info("Connected")
                backoff_seconds = 1.0
                _listen_once(ws)
        except Exception as exc:
            _clear_connection(active_ws)
            active_ws = None
            if not _running:
                break

            delay = min(backoff_seconds, 30.0)
            delay += random.uniform(0.0, delay * 0.2)
            logger.exception(f"Connection error: {exc}. Reconnecting in {delay:.1f}s")
            time.sleep(delay)
            backoff_seconds = min(backoff_seconds * 2.0, 30.0)
        finally:
            _clear_connection(active_ws)

    logger.info("Adapter stopped")


def start_websocket(ws_url=None, ws_token=None):
    global _running, _thread, _ws_url, _ws_token

    try:
        _ensure_websockets_available()
        _ws_url, _ws_token = _resolve_connection_inputs(ws_url, ws_token)
    except Exception as exc:
        logger.exception(f"WebSocket channel disabled: {exc}")
        return None

    _clear_connection()

    _running = True
    _thread = threading.Thread(target=_listener_loop, daemon=True, name="websocket-channel")
    _thread.start()
    return _thread


def stop_websocket():
    global _running
    _running = False

    with _state_lock:
        active_ws = _ws

    if active_ws is None:
        return

    try:
        active_ws.close()
    except Exception as exc:
        logger.exception(f"Error while closing websocket: {exc}")


def getLastMessage():
    global _last_seen_seq

    with _msg_lock:
        if not _inbox:
            return ""

        batch = list(_inbox)
        _inbox.clear()
        _last_seen_seq = batch[-1][0]

    return " | ".join(text for _, text in batch)


def send_message(text):
    message_text = str(text).replace("\\n", "\n").replace("\r", "")
    if not message_text:
        return

    payload = {
        "type": "agent_message",
        "client_seq": uuid.uuid4().hex,
        "text": message_text,
    }

    with _state_lock:
        connected = _connected
        active_ws = _ws

    if not connected:
        with _msg_lock:
            _outbox.append(payload)
        return

    try:
        _send_json(payload, ws=active_ws)
    except Exception as exc:
        logger.exception(f"Send failed, buffering for reconnect: {exc}")
        with _msg_lock:
            _outbox.append(payload)


class WSChannel(channels.CommChannel):

    def __init__(self):
        super().__init__()

    def start(self) -> None:
        start_websocket(config_get_by_key("WS_URL", ""), config_get_by_key("WS_TOKEN", ""))

    def stop(self) -> None:
        stop_websocket()

    def receive(self) -> str:
        return getLastMessage()

    def send(self, message: str) -> None:
        send_message(message)


def loadOmegaClawPlugin():
    channels.registerCommChannel("websocket", WSChannel())
