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
_last_message = ""
_msg_lock = threading.Lock()
_state_lock = threading.Lock()
_flush_lock = threading.Lock()

_bot_token = ""
_api_base = ""
_chat_id = ""
_poll_timeout = 20
_offset = None
_connected = False

_PENDING_MAX = 50
_pending = deque()  # sends issued before the adapter was ready (see send_message)

_authenticated_user_id = None


def _set_last(msg):
    global _last_message
    with _msg_lock:
        if _last_message == "":
            _last_message = msg
        else:
            _last_message = _last_message + " | " + msg


def getLastMessage():
    global _last_message
    with _msg_lock:
        tmp = _last_message
        _last_message = ""
        return tmp


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


def _is_allowed_message(chat_id, user_id, msg):
    global _chat_id, _authenticated_user_id

    with _state_lock:
        if _chat_id and chat_id != _chat_id:
            return "ignore"
        if not auth.is_auth_enabled():
            if not _chat_id:
                _chat_id = chat_id
            return "allow"
        if _authenticated_user_id is not None:
            if chat_id != _chat_id:
                return "ignore"
            return "allow" if user_id == _authenticated_user_id else "ignore"
        candidate = _parse_auth_candidate(msg)
        user_id_check = auth.authenticate_channel_user('TELEGRAM', user_id, candidate)
        if user_id_check in ["auth_bound", "allow"]:
            _authenticated_user_id = user_id
            _chat_id = chat_id
            return user_id_check
        else:
            return "ignore"


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
                    _set_last(f"{display_name}: {text}")
                elif state == "auth_bound":
                    # Enqueue instead of send_message so the poll thread never
                    # blocks on _flush_lock; the flush below delivers it.
                    _enqueue_pending(f"Authentication successful for {display_name}.")

            # After update processing so a chat bound in THIS iteration
            # (auto-bind/auth) flushes immediately, not one poll cycle later.
            # Unlocked emptiness read: worst case a no-op flush or a
            # one-cycle delay; _flush_pending re-checks under _state_lock.
            if _pending:
                _flush_pending(blocking=False)
        except Exception as exc:
            _connected = False
            logger.warning(f"Poll error: {exc}")
            time.sleep(2)

    _connected = False
    logger.info("Polling stopped")


def start_telegram(chat_id="", poll_timeout=20):
    global _running, _bot_token, _api_base, _chat_id, _poll_timeout, _offset, _connected

    proxy = auth.get_proxy_url()
    if proxy:
        _bot_token = "proxy"
        _api_base = f"{proxy}/telegram"
    else:
        _bot_token = os.environ.get("TG_BOT_TOKEN", "").strip()
        if not _bot_token:
            raise ValueError("TG_BOT_TOKEN is required")
        _api_base = f"https://api.telegram.org/bot{_bot_token}"

    _chat_id = str(chat_id).strip()

    try:
        _poll_timeout = max(1, int(poll_timeout))
    except Exception as e:
        logger.warning(f"Invalid poll_timeout {poll_timeout!r}, falling back to 20: {e}")
        _poll_timeout = 20

    _offset = None
    _running = True
    _connected = False
    logger.info(f"Starting adapter with chat target: {_chat_id or 'auto-bind'}")
    _initialize_offset()

    t = threading.Thread(target=_poll_loop, daemon=True)
    t.start()
    return t


def stop_telegram():
    global _running
    _running = False


def _enqueue_pending(text):
    with _state_lock:
        dropped = len(_pending) >= _PENDING_MAX
        if dropped:
            _pending.popleft()
        _pending.append(text)
        queued = len(_pending)
    if dropped:
        logger.warning(f"[SEND_QUEUE] full ({_PENDING_MAX}): dropped oldest queued message")
    logger.info(f"[SEND_QUEUE] queued chars={len(text)} ({queued} pending)")


def _flush_pending(blocking=True):
    # _flush_lock serializes concurrent flushers so queued messages leave in
    # order; _state_lock is never held across the network call. The poll
    # thread passes blocking=False and skips a contended flush (another
    # thread is already draining) instead of stalling getUpdates behind it.
    if not _flush_lock.acquire(blocking=blocking):
        return
    try:
        while True:
            with _state_lock:
                if not _pending or not _connected or not _chat_id:
                    return
                text = _pending.popleft()
                target_chat = _chat_id
                remaining = len(_pending)
            logger.info(f"[SEND_FLUSH] delivering queued message ({remaining} left)")
            if not _deliver(text, target_chat):
                # Stop the drain: the failed message is dropped (matching
                # direct-send semantics), the rest stays queued and retries
                # on the next poll-cycle flush — so a rate-limit burst cannot
                # burn the whole queue in one failing drain.
                logger.warning(
                    f"[SEND_FLUSH] delivery failed, stopping drain ({remaining} still queued)"
                )
                return
    finally:
        _flush_lock.release()


def _deliver(text, target_chat):
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
            return False
    return True


def send_message(text):
    text = str(text).replace("\\n", "\n").replace("\r", "")
    if not text:
        return

    with _state_lock:
        target_chat = _chat_id

    if not _connected or not target_chat:
        # Sends issued before polling is up (or before a chat is bound) used
        # to be dropped silently — most visibly the agent's first message
        # right after launch, which races the adapter's first getUpdates.
        _enqueue_pending(text)
        return

    _flush_pending()
    with _state_lock:
        drain_incomplete = bool(_pending)
    if drain_incomplete:
        # A failed drain left older messages queued — join the queue instead
        # of overtaking them, so delivery order stays chronological.
        _enqueue_pending(text)
        return
    _deliver(text, target_chat)

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
