import json
import os
import threading
import time
import urllib.parse
import urllib.request
from collections import deque
import auth
from src.logger import get_logger
import channels
from config import config_get_by_key

logger = get_logger(__name__)

_running = False
_msg_lock = threading.Lock()
_state_lock = threading.Lock()
_inbox = deque()
_active_chat_id = ""

_bot_token = ""
_api_base = ""
_poll_timeout = 20
_offset = None
_connected = False

def _enqueue_message(msg, chat_id):
    with _msg_lock:
        _inbox.append((str(chat_id), str(msg)))


def getLastMessage():
    global _active_chat_id
    with _msg_lock:
        if not _inbox:
            return ""
        chat_id, message = _inbox.popleft()
    with _state_lock:
        _active_chat_id = chat_id
    return message


def _parse_auth_candidate(msg):
    text = msg.strip()
    lower = text.lower()
    if lower.startswith("auth "):
        return text[5:].strip()
    if lower.startswith("/auth "):
        return text[6:].strip()
    return text


def _display_name(user, chat):
    username = str(user.get("username", "")).strip()
    if username:
        return f"@{username}"

    first = str(user.get("first_name", "")).strip()
    last = str(user.get("last_name", "")).strip()
    full = f"{first} {last}".strip()
    if full:
        return full

    title = str(chat.get("title", "")).strip()
    if title:
        return title

    return "telegram_user"


def _api_call(method, params=None, timeout=30, use_post=False):
    if not _api_base:
        raise RuntimeError("Telegram adapter not initialized")

    params = params or {}
    encoded = urllib.parse.urlencode(params).encode("utf-8")
    url = f"{_api_base}/{method}"

    if use_post:
        req = urllib.request.Request(url, data=encoded)
    else:
        if params:
            url = f"{url}?{urllib.parse.urlencode(params)}"
        req = urllib.request.Request(url)

    with urllib.request.urlopen(req, timeout=timeout) as response:
        payload = json.loads(response.read().decode("utf-8", errors="ignore"))

    if not payload.get("ok"):
        raise RuntimeError(payload.get("description", f"{method} failed"))

    return payload.get("result")


def _initialize_offset():
    global _offset
    try:
        updates = _api_call("getUpdates", {"timeout": 0}, timeout=10) or []
    except Exception as exc:
        logger.warning(f"Could not read initial offset: {exc}")
        return

    max_update = -1
    for update in updates:
        update_id = update.get("update_id")
        if isinstance(update_id, int):
            max_update = max(max_update, update_id)

    if max_update >= 0:
        with _state_lock:
            _offset = max_update + 1


def _is_auth_command(msg):
    lower = msg.strip().lower()
    return lower.startswith("auth ") or lower.startswith("/auth ")


def _is_allowed_message(chat_id, _user_id, msg):
    """Trust an entire chat after one explicit shared-secret authentication."""
    if not auth.is_auth_enabled():
        return "allow"

    # The chat ID is deliberately stored as the authorization subject. Once a
    # trusted user authenticates a group, all present and future members of
    # that group may use the bot. Other chats remain independently protected.
    if auth.get_channel_saved_group_id("TELEGRAM", chat_id):
        return "allow"

    candidate = _parse_auth_candidate(msg) if _is_auth_command(msg) else None
    if candidate is None:
        return "ignore"
    return auth.authenticate_channel_group("TELEGRAM", chat_id, candidate)


def _poll_loop():
    global _connected, _offset
    logger.info("Polling started")

    while _running:
        try:
            params = {"timeout": int(_poll_timeout)}
            with _state_lock:
                if _offset is not None:
                    params["offset"] = _offset

            updates = _api_call("getUpdates", params=params, timeout=int(_poll_timeout) + 10) or []
            _connected = True

            for update in updates:
                update_id = update.get("update_id")
                if isinstance(update_id, int):
                    with _state_lock:
                        if _offset is None or (update_id + 1) > _offset:
                            _offset = update_id + 1

                message = update.get("message") or update.get("edited_message")
                if not isinstance(message, dict):
                    continue

                text = message.get("text")
                if not text:
                    continue

                chat = message.get("chat") or {}
                user = message.get("from") or {}
                chat_id = str(chat.get("id", "")).strip()
                user_id = str(user.get("id", "")).strip()
                if not chat_id or not user_id:
                    continue

                state = _is_allowed_message(chat_id, user_id, text)
                display_name = _display_name(user, chat)
                if state == "allow":
                    _enqueue_message(f"{display_name}: {text}", chat_id)
                elif state == "auth_bound":
                    send_message(f"Authentication successful for {display_name}.", chat_id)
        except Exception as exc:
            _connected = False
            logger.warning(f"Poll error: {exc}")
            time.sleep(2)

    _connected = False
    logger.info("Polling stopped")


def start_telegram(chat_id="", poll_timeout=20):
    global _running, _bot_token, _api_base, _poll_timeout, _offset, _connected, _active_chat_id

    proxy = auth.get_proxy_url()
    if proxy:
        _bot_token = "proxy"
        _api_base = f"{proxy}/telegram"
    else:
        _bot_token = os.environ.get("TG_BOT_TOKEN", "").strip()
        if not _bot_token:
            raise ValueError("TG_BOT_TOKEN is required")
        _api_base = f"https://api.telegram.org/bot{_bot_token}"

    if str(chat_id).strip():
        logger.warning("TG_CHAT_ID is ignored by multi-chat Telegram mode")
    with _msg_lock:
        _inbox.clear()
    with _state_lock:
        _active_chat_id = ""

    try:
        _poll_timeout = max(1, int(poll_timeout))
    except Exception as e:
        logger.warning(f"Invalid poll_timeout {poll_timeout!r}, falling back to 20: {e}")
        _poll_timeout = 20

    _offset = None
    _running = True
    _connected = False
    logger.info("Starting adapter in multi-chat mode")
    _initialize_offset()

    t = threading.Thread(target=_poll_loop, daemon=True)
    t.start()
    return t


def stop_telegram():
    global _running
    _running = False


def send_message(text, target_chat=None):
    text = str(text).replace("\\n", "\n").replace("\r", "")
    if not text:
        return

    with _state_lock:
        target_chat = str(target_chat or _active_chat_id).strip()

    if not _connected or not target_chat:
        return

    max_len = 3900
    for i in range(0, len(text), max_len):
        chunk = text[i:i + max_len]
        if not chunk:
            continue
        try:
            _api_call(
                "sendMessage",
                {"chat_id": target_chat, "text": chunk},
                timeout=15,
                use_post=True,
            )
        except Exception as exc:
            logger.exception(f"Send failed: {exc}")
            return

class TelegramChannel(channels.CommChannel):

    def __init__(self):
        super().__init__()

    def start(self) -> None:
        chat_id = config_get_by_key("TG_CHAT_ID", "")
        poll_timeout = int(config_get_by_key("TG_POLL_TIMEOUT", 20))
        start_telegram(chat_id, poll_timeout)

    def stop(self) -> None:
        stop_telegram()

    def receive(self) -> str:
        return getLastMessage()

    def send(self, message: str) -> None:
        send_message(message)

def loadOmegaClawPlugin():
    channels.registerCommChannel("telegram", TelegramChannel())
