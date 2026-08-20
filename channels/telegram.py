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

# --- Admin allowlist (review point #8) --------------------------------
# A chat-level administrator boundary.  The initial owner-authentication DM
# and the persisted owner's DM are intentionally exempt when auth is enabled.
# TG_CHAT_ID is kept for backwards compatibility (single chat);
# TG_ALLOWED_CHAT_IDS is new and accepts a comma-separated list. Empty
# means "no admin restriction configured".
_admin_allowed_chats = set()

# Legacy no-auth fallback: first chat to talk wins. Only used when auth is
# disabled AND no admin allowlist is configured, preserving the original
# single-chat auto-bind behavior for existing no-auth deployments.
_auto_bound_chat = ""

_BIND_COMMANDS = ("/bind", "/authorize_group")


# ---------------------------------------------------------------------------
# Multi-chat routing (review point #9).
#
# Pure plumbing: remembers which chat each inbound message came from, and
# lets replies target that same chat. Has no knowledge of authorization --
# it only ever queues/sends what _is_allowed_message() has already approved.
# ---------------------------------------------------------------------------

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


# ---------------------------------------------------------------------------
# Authorization.
#
# Layered, outer to inner:
#   1. Admin allowlist (TG_CHAT_ID / TG_ALLOWED_CHAT_IDS) -- chats outside
#      it are ignored, except for private owner bootstrap/owner DMs when
#      authentication is enabled.
#   2. If auth is disabled: allowlisted chats are trusted outright; with no
#      allowlist at all, fall back to the legacy single-chat auto-bind.
#   3. If auth is enabled: nothing is allowed until an owner exists. The
#      owner is established exactly once via "auth <secret>" -- reusing
#      auth.authenticate_channel_user(), the SAME function IRC/Slack/
#      Mattermost use, keyed as "TELEGRAM". This is a deliberate reuse, not
#      a parallel system (review point #2).
#   4. Once an owner exists:
#        - Private chats (DMs): owner only, forever. No other user can ever
#          be allowed in the owner's DM (review point #6).
#        - Group chats: open to every member once authorized. Before that,
#          only the owner's own "/bind" (or "/authorize_group") message
#          opens it -- verified by sender user_id, never by the secret
#          (review point #3, #4, #5).
# ---------------------------------------------------------------------------

def _parse_auth_candidate(msg):
    text = msg.strip()
    lower = text.lower()
    if lower.startswith("auth "):
        return text[5:].strip()
    if lower.startswith("/auth "):
        return text[6:].strip()
    return text


def _is_auth_command(msg):
    lower = msg.strip().lower()
    return lower.startswith("auth ") or lower.startswith("/auth ")


def _first_token(msg):
    stripped = msg.strip()
    if not stripped:
        return ""
    return stripped.split(None, 1)[0].lower()


def _is_bind_command(msg):
    # Handle Telegram's "/bind@YourBotName" form, sent automatically by
    # clients when a group has more than one bot in it.
    token = _first_token(msg).split("@", 1)[0]
    return token in _BIND_COMMANDS


def _is_allowed_message(chat_id, user_id, chat_type, msg):
    global _auto_bound_chat

    auth_enabled = auth.is_auth_enabled()

    if not auth_enabled:
        if _admin_allowed_chats:
            return "allow" if chat_id in _admin_allowed_chats else "ignore"
        with _state_lock:
            if _auto_bound_chat and chat_id != _auto_bound_chat:
                return "ignore"
            if not _auto_bound_chat:
                _auto_bound_chat = chat_id
        return "allow"

    owner_id = auth.get_channel_authenticated_user_id("TELEGRAM")

    is_owner_bootstrap = (
        owner_id is None
        and chat_type == "private"
        and _is_auth_command(msg)
    )
    is_owner_private_chat = (
        owner_id is not None
        and chat_type == "private"
        and user_id == owner_id
    )

    if (
        _admin_allowed_chats
        and chat_id not in _admin_allowed_chats
        and not is_owner_bootstrap
        and not is_owner_private_chat
    ):
        return "ignore"

    if owner_id is None:
        # The reusable secret is accepted only in a private DM. The owner can
        # then open groups using /bind, which relies on Telegram user id.
        if is_owner_bootstrap:
            candidate = _parse_auth_candidate(msg)
            return auth.authenticate_channel_user("TELEGRAM", user_id, candidate)
        return "ignore"

    if chat_type == "private":
        return "allow" if user_id == owner_id else "ignore"

    # Anything that isn't "private" is a group/supergroup chat.
    if auth.get_channel_saved_group_id("TELEGRAM", chat_id):
        return "allow"

    if user_id == owner_id and _is_bind_command(msg):
        return auth.authorize_channel_group("TELEGRAM", chat_id, user_id)

    return "ignore"


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
                chat_type = str(chat.get("type", "")).strip()
                if not chat_id or not user_id:
                    continue

                state = _is_allowed_message(chat_id, user_id, chat_type, text)
                display_name = _display_name(user, chat)

                if state == "allow":
                    _enqueue_message(f"{display_name}: {text}", chat_id)
                elif state == "auth_bound":
                    send_message(
                        f"Authentication successful. {display_name} is now the bot owner. "
                        "Send /bind in a group to open it to everyone there.",
                        chat_id,
                    )
                elif state == "group_bound":
                    send_message(
                        "This group is now authorized. All members can talk to the bot here.",
                        chat_id,
                    )
        except Exception as exc:
            _connected = False
            logger.warning(f"Poll error: {exc}")
            time.sleep(2)

    _connected = False
    logger.info("Polling stopped")


def _parse_admin_allowed_chats(chat_id_config, allowed_config):
    ids = set()
    single = str(chat_id_config or "").strip()
    if single:
        ids.add(single)
    for part in str(allowed_config or "").split(","):
        part = part.strip()
        if part:
            ids.add(part)
    return ids


def start_telegram(chat_id="", allowed_chat_ids="", poll_timeout=20):
    global _running, _bot_token, _api_base, _poll_timeout, _offset, _connected
    global _active_chat_id, _admin_allowed_chats, _auto_bound_chat

    proxy = auth.get_proxy_url()
    if proxy:
        _bot_token = "proxy"
        _api_base = f"{proxy}/telegram"
    else:
        _bot_token = os.environ.get("TG_BOT_TOKEN", "").strip()
        if not _bot_token:
            raise ValueError("TG_BOT_TOKEN is required")
        _api_base = f"https://api.telegram.org/bot{_bot_token}"

    _admin_allowed_chats = _parse_admin_allowed_chats(chat_id, allowed_chat_ids)
    _auto_bound_chat = ""

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
    if _admin_allowed_chats:
        logger.info(f"Starting adapter, admin-restricted to chats: {sorted(_admin_allowed_chats)}")
    else:
        logger.info("Starting adapter with no admin chat restriction")
    _initialize_offset()

    t = threading.Thread(target=_poll_loop, daemon=True)
    t.start()
    return t


def stop_telegram():
    global _running
    _running = False


class TelegramChannel(channels.CommChannel):

    def __init__(self):
        super().__init__()

    def start(self) -> None:
        chat_id = config_get_by_key("TG_CHAT_ID", "")
        allowed_chat_ids = config_get_by_key("TG_ALLOWED_CHAT_IDS", "")
        poll_timeout = int(config_get_by_key("TG_POLL_TIMEOUT", 20))
        start_telegram(chat_id, allowed_chat_ids, poll_timeout)

    def stop(self) -> None:
        stop_telegram()

    def receive(self) -> str:
        return getLastMessage()

    def send(self, message: str) -> None:
        send_message(message)


def loadOmegaClawPlugin():
    channels.registerCommChannel("telegram", TelegramChannel())
