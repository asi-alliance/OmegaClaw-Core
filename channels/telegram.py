import json
import os
import threading
import time
import urllib.parse
import urllib.request

_running = False
_last_message = ""
_msg_lock = threading.Lock()
_state_lock = threading.Lock()

_bot_token = ""
_api_base = ""
_chat_id = ""
_poll_timeout = 20
_offset = None
_connected = False

_auth_secret = ""
_authenticated_user_id = None
_authenticated_chat_id = None


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


def _set_auth_secret(secret=None):
    global _auth_secret, _authenticated_user_id, _authenticated_chat_id
    if secret is None:
        secret = os.environ.get("OMEGACLAW_AUTH_SECRET", "")
    with _state_lock:
        _auth_secret = (secret or "").strip()
        _authenticated_user_id = None
        _authenticated_chat_id = None


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
        print(f"[TELEGRAM] Could not read initial offset: {exc}")
        return

    max_update = -1
    for update in updates:
        update_id = update.get("update_id")
        if isinstance(update_id, int):
            max_update = max(max_update, update_id)

    if max_update >= 0:
        with _state_lock:
            _offset = max_update + 1


def _is_allowed_message(chat_id, user_id, msg):
    global _chat_id, _authenticated_user_id, _authenticated_chat_id
    candidate = _parse_auth_candidate(msg)

    with _state_lock:
        if _chat_id and chat_id != _chat_id:
            return "ignore"

        if not _auth_secret:
            if not _chat_id:
                _chat_id = chat_id
            return "allow"

        if _authenticated_user_id is None:
            if candidate == _auth_secret:
                _authenticated_user_id = user_id
                _authenticated_chat_id = chat_id
                _chat_id = chat_id
                return "auth_bound"
            return "ignore"

        if chat_id != _authenticated_chat_id:
            return "ignore"
        return "allow" if user_id == _authenticated_user_id else "ignore"


def _poll_loop():
    global _connected, _offset
    print("[TELEGRAM] Polling started")

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
                    send_message(f"Authentication successful for {display_name}.")
        except Exception as exc:
            _connected = False
            print(f"[TELEGRAM] Poll error: {exc}")
            time.sleep(2)

    _connected = False
    print("[TELEGRAM] Polling stopped")


def start_telegram(bot_token, chat_id="", poll_timeout=20, auth_secret=None):
    global _running, _bot_token, _api_base, _chat_id, _poll_timeout, _offset, _connected

    _bot_token = str(bot_token).strip()
    if not _bot_token:
        raise ValueError("TG_BOT_TOKEN is required")

    _api_base = f"https://api.telegram.org/bot{_bot_token}"
    _chat_id = str(chat_id).strip()

    try:
        _poll_timeout = max(1, int(poll_timeout))
    except Exception:
        _poll_timeout = 20

    _offset = None
    _running = True
    _connected = False
    _set_auth_secret(auth_secret)
    print(f"[TELEGRAM] Starting adapter with chat target: {_chat_id or 'auto-bind'}")
    _initialize_offset()

    t = threading.Thread(target=_poll_loop, daemon=True)
    t.start()
    return t


def stop_telegram():
    global _running
    _running = False


def send_message(text):
    text = str(text).replace("\\n", "\n").replace("\r", "")
    if not text:
        return

    with _state_lock:
        target_chat = _chat_id

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
            print(f"[TELEGRAM] Send failed: {exc}")
            return
