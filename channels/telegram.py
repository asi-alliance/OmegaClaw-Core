import json
import os
import threading
import time
import urllib.parse
import urllib.request
from collections import deque
import auth
from src.logger import get_logger
from delivery_queue import PendingMessages
import channels
from config import config_get_by_key

logger = get_logger(__name__)

_running = False
_msg_lock = threading.Lock()
_state_lock = threading.Lock()
_inbox = deque()
_active_chat_id = ""
_active_message_token = None
_active_replied = False
_next_message_token = 0
_default_chat_id = ""
_outbox = PendingMessages()

_bot_token = ""
_api_base = ""
_bot_username= ""
_poll_timeout = 20
_offset = None
_connected = False
_admin_allowed_chats = set()
_owner_id = None
_authorized_groups = set()

_auto_bound_chat = ""

_BIND_COMMANDS = ("/bind", "/authorize_group")
_UNBIND_COMMANDS = ("/unbind", "/unauthorize_group")


def _enqueue_message(msg, chat_id):
    global _next_message_token
    with _msg_lock:
        _next_message_token += 1
        _inbox.append((_next_message_token, str(chat_id), str(msg)))


def getLastMessage():
    global _active_chat_id, _active_message_token, _active_replied
    with _msg_lock:
        if _active_chat_id and not _active_replied:
            return ""
        if _active_replied:
            _active_chat_id = ""
            _active_message_token = None
            _active_replied = False
        if not _inbox:
            return ""
        message_token, chat_id, message = _inbox.popleft()
        _active_chat_id = chat_id
        _active_message_token = message_token
    return message


def _ready_to_send():
    return _connected


def _deliver_outbound(item):
    global _active_replied
    target_chat, chunk, completed_message_token = item
    _api_call(
        "sendMessage",
        {"chat_id": target_chat, "text": chunk},
        timeout=15,
        use_post=True,
    )
    if completed_message_token is not None:
        with _msg_lock:
            if completed_message_token == _active_message_token:
                _active_replied = True


def _flush_outbox():
    try:
        _outbox.flush(_deliver_outbound, _ready_to_send)
    except Exception as exc:
        logger.warning(f"Telegram send failed; retaining queued message: {exc}")


def send_message(text, target_chat=None):
    text = str(text).replace("\\n", "\n").replace("\r", "")
    if not text:
        return False

    explicit_target = str(target_chat or "").strip()
    with _msg_lock:
        active_chat = _active_chat_id
        active_message_token = _active_message_token
        target_chat = explicit_target or active_chat or _default_chat_id
        completed_message_token = (
            active_message_token
            if not explicit_target and active_chat and target_chat == active_chat
            else None
        )

    if not target_chat:
        logger.warning("Telegram send skipped: no active or default chat is available")
        return False

    max_len = 3900
    chunks = [text[i:i + max_len] for i in range(0, len(text), max_len)]
    outbound = []
    for index, chunk in enumerate(chunks):
        completes_message = completed_message_token if index == len(chunks) - 1 else None
        outbound.append((target_chat, chunk, completes_message))
    _outbox.extend(outbound)
    _flush_outbox()
    return True


# ---------------------------------------------------------------------------
# Authorization.

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


def _is_targeted_command(msg, commands):
    token = _first_token(msg)
    command, separator, target_username = token.partition("@")

    if command not in commands:
        return False

    if not separator:
        return True

    return bool(_bot_username) and target_username == _bot_username


def _is_bind_command(msg):
    return _is_targeted_command(msg, _BIND_COMMANDS)


def _is_unbind_command(msg):
    return _is_targeted_command(msg, _UNBIND_COMMANDS)


def _command_argument(msg):
    parts = str(msg or "").strip().split(None, 1)
    return parts[1].strip() if len(parts) == 2 else ""


def _is_allowed_message(chat_id, user_id, chat_type, msg):
    global _auto_bound_chat, _owner_id

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

    owner_id = _owner_id

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
        if is_owner_bootstrap:
            candidate = _parse_auth_candidate(msg)
            state = auth.authenticate_channel_user("TELEGRAM", user_id, candidate)
            if state == "auth_bound":
                _owner_id = user_id
            return state
        return "ignore"

    if chat_type == "private":
        if user_id == owner_id and _is_unbind_command(msg):
            group_id = _command_argument(msg)
            if group_id:
                state = auth.revoke_channel_group("TELEGRAM", group_id, user_id)
                if state == "group_unbound":
                    _authorized_groups.discard(group_id)
                return state
            return "ignore"
        return "allow" if user_id == owner_id else "ignore"

    # Anything that isn't "private" is a group/supergroup chat.
    if _is_unbind_command(msg):
        if user_id == owner_id:
            state = auth.revoke_channel_group("TELEGRAM", chat_id, user_id)
            if state == "group_unbound":
                _authorized_groups.discard(chat_id)
            return state
        return "ignore"

    if chat_id in _authorized_groups:
        return "allow"

    if user_id == owner_id and _is_bind_command(msg):
        state = auth.authorize_channel_group("TELEGRAM", chat_id, user_id)
        if state in {"allow", "group_bound"}:
            _authorized_groups.add(chat_id)
        return state

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

def _initialize_bot_identity():
    global _bot_username

    try:
        result = _api_call("getMe", timeout=10)
        if not isinstance(result, dict):
            raise RuntimeError("Telegram getMe returned an invalid response")
        username = str(result.get("username", "")).strip().lstrip("@").lower()
        if not username:
            raise RuntimeError("Telegram getMe did not return the bot username")
    except Exception as exc:
        _bot_username = ""
        logger.warning(f"Could not read Telegram bot identity: {exc}")
        return False

    _bot_username = username
    return True


def _process_update(update):
    message = update.get("message") or update.get("edited_message")
    if not isinstance(message, dict):
        return

    text = message.get("text")
    if not text:
        return

    chat = message.get("chat") or {}
    user = message.get("from") or {}
    chat_id = str(chat.get("id", "")).strip()
    user_id = str(user.get("id", "")).strip()
    chat_type = str(chat.get("type", "")).strip()
    if not chat_id or not user_id:
        return

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
    elif state == "group_unbound":
        send_message("This group is no longer authorized.", chat_id)



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
            _flush_outbox()

            for update in updates:
                update_id = update.get("update_id")
                _process_update(update)
                if isinstance(update_id, int):
                    with _state_lock:
                        if _offset is None or (update_id + 1) > _offset:
                            _offset = update_id + 1
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
    global _active_chat_id, _active_message_token, _active_replied
    global _next_message_token, _default_chat_id
    global _admin_allowed_chats, _auto_bound_chat, _owner_id, _authorized_groups

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
    _default_chat_id = str(chat_id or "").strip()
    _auto_bound_chat = ""
    if auth.is_auth_enabled():
        _owner_id, _authorized_groups = auth.load_channel_auth_state("TELEGRAM")
    else:
        _owner_id, _authorized_groups = None, set()

    with _msg_lock:
        _inbox.clear()
        _active_chat_id = ""
        _active_message_token = None
        _active_replied = False
        _next_message_token = 0
    _outbox.clear()

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
    
    _initialize_bot_identity()

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
