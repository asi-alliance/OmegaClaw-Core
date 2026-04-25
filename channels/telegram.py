import os
import threading
import time

import requests

_running = False
_bot_token = ""
_configured_chat_id = None
_chat_id = None
_offset = 0

_last_message = ""
_msg_lock = threading.Lock()

_auth_lock = threading.Lock()
_auth_secret = ""
_authenticated_user_ids = set()

# Anti-paraphrase send dedup: keep a small ring of recent sends and refuse to
# resend anything whose first 80 normalized chars match a recent message.
# Reasoning models like phi4-reasoning and deepseek-r1 tend to re-emit the
# same answer with reworded prefixes ("Yes, X provides…" vs "Yes, X offers…");
# the existing &lastsend exact-match dedup in channels.metta misses these.
_send_lock = threading.Lock()
_recent_sends = []  # list of normalized prefixes
_RECENT_SEND_LIMIT = 8
_DEDUP_PREFIX_LEN = 80


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
    global _auth_secret
    if secret is None:
        secret = os.environ.get("OMEGACLAW_AUTH_SECRET", "")
    with _auth_lock:
        _auth_secret = (secret or "").strip()
        _authenticated_user_ids.clear()


def _parse_auth_candidate(msg):
    text = msg.strip()
    lower = text.lower()
    if lower.startswith("auth "):
        return text[5:].strip()
    if lower.startswith("/auth "):
        return text[6:].strip()
    return text


def _is_allowed_message(user_id, msg):
    candidate = _parse_auth_candidate(msg)
    with _auth_lock:
        if not _auth_secret:
            return True
        if candidate == _auth_secret:
            _authenticated_user_ids.add(user_id)
            return False
        return user_id in _authenticated_user_ids


def _poll_loop():
    global _offset, _chat_id
    url = f"https://api.telegram.org/bot{_bot_token}/getUpdates"
    while _running:
        try:
            r = requests.get(
                url,
                params={"offset": _offset, "timeout": 25},
                timeout=35,
            )
            data = r.json()
            if not data.get("ok"):
                time.sleep(2)
                continue
            for upd in data.get("result", []):
                _offset = upd["update_id"] + 1
                msg = (
                    upd.get("message")
                    or upd.get("edited_message")
                    or upd.get("channel_post")
                )
                if not msg:
                    continue
                text = msg.get("text", "")
                if not text:
                    continue
                sender = msg.get("from") or {}
                user_id = sender.get("id")
                chat_id = msg["chat"]["id"]

                if _configured_chat_id and str(chat_id) != str(_configured_chat_id):
                    continue

                allowed = _is_allowed_message(user_id, text)

                with _auth_lock:
                    is_authed = user_id in _authenticated_user_ids

                if is_authed and not _configured_chat_id:
                    _chat_id = chat_id

                if allowed:
                    name = (
                        sender.get("username")
                        or sender.get("first_name")
                        or "user"
                    )
                    _set_last(f"{name}: {text}")
        except Exception:
            time.sleep(2)


def start_telegram(bot_token, chat_id="", auth_secret=None):
    global _running, _bot_token, _configured_chat_id, _chat_id
    _bot_token = str(bot_token).strip()
    cid = str(chat_id).strip()
    _configured_chat_id = cid or None
    _chat_id = int(cid) if cid else None
    _set_auth_secret(auth_secret)
    _running = True
    t = threading.Thread(target=_poll_loop, daemon=True)
    t.start()
    return t


def stop_telegram():
    global _running
    _running = False


def _normalize_for_dedup(text):
    """Lowercase + collapse whitespace + take first prefix for paraphrase
       comparison."""
    if not text:
        return ""
    norm = " ".join(text.lower().split())
    return norm[:_DEDUP_PREFIX_LEN]


def send_message(text):
    text = text.replace("\\n", "\n")
    if _chat_id is None or not _bot_token:
        return
    norm = _normalize_for_dedup(text)
    if norm:
        with _send_lock:
            if norm in _recent_sends:
                # Near-duplicate of something we sent recently; drop silently.
                return
            _recent_sends.append(norm)
            if len(_recent_sends) > _RECENT_SEND_LIMIT:
                _recent_sends.pop(0)
    try:
        requests.post(
            f"https://api.telegram.org/bot{_bot_token}/sendMessage",
            json={"chat_id": _chat_id, "text": text},
            timeout=10,
        )
    except Exception:
        pass
