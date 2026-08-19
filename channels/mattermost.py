import json
import os
import threading
import time

import requests
import websocket
import auth
from src.logger import get_logger
from delivery_queue import PendingMessages
import channels
from config import config_get_by_key

logger = get_logger(__name__)

_running = False
_ws = None
_ws_lock = threading.Lock()
_last_message = ""
_msg_lock = threading.Lock()
_connected = False
_auth_lock = threading.Lock()
_authenticated_user_id = None
_use_proxy = True
_outbox = PendingMessages()

# ---- Mattermost config (dummy token ok) ----
MM_URL = "https://chat.singularitynet.io"
CHANNEL_ID = "8fjrmabjx7gupy7e5kjznpt5qh" #NOT AN ID JUST NAME: "omegaclaw"x
BOT_TOKEN = ""
BOT_USER_ID = ""

def _get_bot_user_id():
    global headers
    r = requests.get(
        f"{MM_URL}/api/v4/users/me",
        headers=_headers
    )
    return r.json()["id"]

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

def _is_auth_command(msg):
    lower = msg.strip().lower()
    return lower.startswith("auth ") or lower.startswith("/auth ")

def _is_allowed_message(user_id, msg):
    global _authenticated_user_id
    with _auth_lock:
        if not auth.is_auth_enabled():
            return "allow"
        if _authenticated_user_id is not None:
            return "allow" if user_id == _authenticated_user_id else "ignore"
        auth_candidate = _parse_auth_candidate(msg) if _is_auth_command(msg) else None
        user_id_check = auth.authenticate_channel_user('MATTERMOST', user_id, auth_candidate)
        if user_id_check in ["auth_bound", "allow"]:
            _authenticated_user_id = user_id
            return user_id_check
        else:
            return "ignore"

def _get_display_name(user_id):
    r = requests.get(
        f"{MM_URL}/api/v4/users/{user_id}",
        headers=_headers
    )
    u = r.json()

    # Mimic common Mattermost display setting
    if u.get("first_name") or u.get("last_name"):
        return f"{u.get('first_name','')} {u.get('last_name','')}".strip()

    return u["username"]

def _ready_to_send():
    with _ws_lock:
        return _connected and bool(CHANNEL_ID)


def _deliver_outbound(text):
    response = requests.post(
        f"{MM_URL}/api/v4/posts",
        headers=_headers,
        json={"channel_id": CHANNEL_ID, "message": text},
        timeout=15,
    )
    response.raise_for_status()


def _send_export_reply(user_id, text):
    """Deliver export-control output through the requester's Mattermost DM."""
    if not BOT_USER_ID:
        raise RuntimeError("Mattermost bot identity is not initialized")
    direct = requests.post(
        f"{MM_URL}/api/v4/channels/direct",
        headers=_headers,
        json=[BOT_USER_ID, user_id],
        timeout=15,
    )
    direct.raise_for_status()
    direct_channel_id = str(direct.json().get("id", "")).strip()
    if not direct_channel_id:
        raise RuntimeError("Mattermost did not return a direct-message channel")
    response = requests.post(
        f"{MM_URL}/api/v4/posts",
        headers=_headers,
        json={"channel_id": direct_channel_id, "message": str(text)},
        timeout=15,
    )
    response.raise_for_status()


def _flush_outbox():
    try:
        _outbox.flush(_deliver_outbound, _ready_to_send)
    except Exception as exc:
        logger.warning(f"Mattermost send failed; retaining queued message: {exc}")


def _ws_session():
    global _ws, _connected, BOT_USER_ID, _use_proxy

    if _use_proxy:
        ws_url = MM_URL.replace("http", "ws")
    else:
        ws_url = MM_URL.replace("https", "wss")
    ws_url = ws_url + "/api/v4/websocket"
    ws = websocket.WebSocket()
    ws.connect(ws_url, header=[f"Authorization: Bearer {BOT_TOKEN}"])

    BOT_USER_ID = _get_bot_user_id()
    with _ws_lock:
        _ws = ws
        _connected = True
    _flush_outbox()

    last_ping = time.time()

    try:
        while _running:
            # send ping every 25s
            if time.time() - last_ping > 25:
                ws.ping()
                last_ping = time.time()

            ws.settimeout(1)
            try:
                raw_event = ws.recv()
            except websocket.WebSocketTimeoutException:
                _flush_outbox()
                continue
            event = json.loads(raw_event)

            if event.get("event") == "posted":
                post = json.loads(event["data"]["post"])
                if post["channel_id"] == CHANNEL_ID and post["user_id"] != BOT_USER_ID:
                    user_id = post["user_id"]
                    message = post.get("message", "")
                    state = _is_allowed_message(user_id, message)
                    if state == "allow":
                        name = _get_display_name(user_id)
                        owner_key = f"mattermost:{CHANNEL_ID}:{user_id}"
                        deliver_reply = lambda text, target=user_id: _send_export_reply(target, text)
                        if not channels.handle_control_message(message, owner_key, deliver_reply):
                            _set_last(f"{name}: {message}")
                    elif state == "auth_bound":
                        name = _get_display_name(user_id)
                        send_message(f"Authentication successful for {name}.")
            _flush_outbox()
    finally:
        with _ws_lock:
            if _ws is ws:
                _ws = None
            _connected = False
        ws.close()


def _ws_loop():
    backoff_seconds = 1
    while _running:
        try:
            _ws_session()
            backoff_seconds = 1
        except Exception as exc:
            if _running:
                logger.warning(f"Mattermost connection error: {exc}")

        if not _running:
            break
        logger.info(f"Reconnecting Mattermost in {backoff_seconds}s")
        time.sleep(backoff_seconds)
        backoff_seconds = min(backoff_seconds * 2, 30)

def start_mattermost(MM_URL_, CHANNEL_ID_):
    global _running, MM_URL, CHANNEL_ID, BOT_TOKEN, _headers, _connected, _use_proxy
    proxy = auth.get_proxy_url()
    if proxy:
        MM_URL = f"{proxy}/mattermost"
        BOT_TOKEN = "proxy"
        _headers = {}
        _use_proxy = True
    else:
        MM_URL = MM_URL_
        BOT_TOKEN = os.environ.get("MM_BOT_TOKEN", "").strip()
        _headers = {"Authorization": f"Bearer {BOT_TOKEN}"} if BOT_TOKEN else {}
        _use_proxy = False
    CHANNEL_ID = CHANNEL_ID_
    _running = True
    _connected = False
    t = threading.Thread(target=_ws_loop, daemon=True)
    t.start()
    return t

def stop_mattermost():
    global _running
    _running = False
    with _ws_lock:
        ws = _ws
    if ws is not None:
        try:
            ws.close()
        except Exception as exc:
            logger.warning(f"Could not close Mattermost websocket: {exc}")

def send_message(text):
    text = str(text).replace("\\n", "\n").replace("\r", "")
    if not text:
        return
    _outbox.put(text)
    _flush_outbox()

class MattermostChannel(channels.CommChannel):

    def __init__(self):
        super().__init__()

    def start(self) -> None:
        global MM_URL, CHANNEL_ID
        url = config_get_by_key("MM_URL", MM_URL)
        channel = config_get_by_key("MM_CHANNEL_ID", CHANNEL_ID)
        start_mattermost(url, channel)

    def stop(self) -> None:
        stop_mattermost()

    def receive(self) -> str:
        return getLastMessage()

    def send(self, message: str) -> None:
        send_message(message)

def loadOmegaClawPlugin():
    channels.registerCommChannel("mattermost", MattermostChannel())
