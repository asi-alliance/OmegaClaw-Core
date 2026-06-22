import json
import os
import random
import threading
import time
import urllib.error
import urllib.parse
import urllib.request

import websocket
import auth

_running = False
_last_message = ""
_msg_lock = threading.Lock()
_state_lock = threading.Lock()
_ws_lock = threading.Lock()

_DEFAULT_GATEWAY_INTENTS = 37377

_bot_token = ""
_api_base = "https://discord.com/api/v10"
_gateway_url = "wss://gateway.discord.gg/?v=10&encoding=json"
_channel_id = ""
_gateway_intents = _DEFAULT_GATEWAY_INTENTS
_bot_user_id = ""
_connected = False
_ws = None
_last_sequence = None
_session_id = ""
_resume_gateway_url = ""
_heartbeat_acked = True

_authenticated_user_id = None
_message_content_warning_logged = False

_MAX_MESSAGE_LEN = 1900

# Cap on back-to-back fast RESUME attempts before falling back to a full
# re-IDENTIFY with normal backoff, so a flapping connection can't thrash.
_MAX_RESUME_ATTEMPTS = 3


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


def _display_name(author, member):
    nick = str((member or {}).get("nick", "") or "").strip()
    if nick:
        return nick

    global_name = str(author.get("global_name", "") or "").strip()
    if global_name:
        return global_name

    username = str(author.get("username", "") or "").strip()
    if username:
        return username

    return str(author.get("id", "") or "discord_user")


def _parse_retry_after(value, default=5):
    try:
        seconds = float(str(value).strip())
        return max(1.0, seconds)
    except Exception:
        return default


def _api_call_once(method, path, params=None, body=None, timeout=30):
    if not _bot_token:
        raise RuntimeError("Discord adapter not initialized")

    params = params or {}
    url = f"{_api_base}{path}"
    if params:
        url = f"{url}?{urllib.parse.urlencode(params)}"

    data = None
    headers = {
        "Authorization": f"Bot {_bot_token}",
        "User-Agent": "OmegaClaw Discord Adapter",
    }
    if body is not None:
        data = json.dumps(body).encode("utf-8")
        headers["Content-Type"] = "application/json"

    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    with urllib.request.urlopen(req, timeout=timeout) as response:
        raw = response.read().decode("utf-8", errors="ignore")
        if not raw:
            return {}
        return json.loads(raw)


def _api_call(method, path, params=None, body=None, timeout=30):
    try:
        return _api_call_once(method, path, params=params, body=body, timeout=timeout)
    except urllib.error.HTTPError as exc:
        raw = exc.read().decode("utf-8", errors="ignore")
        try:
            payload = json.loads(raw) if raw else {}
        except Exception:
            payload = {}

        if exc.code == 429:
            retry_after = _parse_retry_after(payload.get("retry_after"), default=5)
            time.sleep(retry_after)
            return _api_call_once(method, path, params=params, body=body, timeout=timeout)

        message = payload.get("message") or raw or f"HTTP {exc.code}"
        raise RuntimeError(message) from exc


def _initialize_identity():
    global _bot_user_id
    payload = _api_call("GET", "/users/@me", timeout=15)
    bot_user_id = str(payload.get("id", "")).strip()
    with _state_lock:
        _bot_user_id = bot_user_id


def _validate_channel():
    payload = _api_call("GET", f"/channels/{_channel_id}", timeout=15)
    name = str(payload.get("name", "") or "").strip()
    if name:
        print(f"[DISCORD] Channel ready: #{name}")
    else:
        print(f"[DISCORD] Channel ready: {_channel_id}")


def _is_allowed_message(channel_id, user_id, msg):
    global _channel_id, _authenticated_user_id

    with _state_lock:
        if _channel_id and channel_id != _channel_id:
            return "ignore"
        if not auth.is_auth_enabled():
            if not _channel_id:
                print(f"[DISCORD] Auto-bound to channel {channel_id}")
                _channel_id = channel_id
            return "allow"
        if _authenticated_user_id is not None:
            if channel_id != _channel_id:
                return "ignore"
            return "allow" if user_id == _authenticated_user_id else "ignore"
        if not _is_auth_command(msg):
            return "ignore"
        candidate = _parse_auth_candidate(msg)
        if auth.verify_token(candidate):
            _authenticated_user_id = user_id
            _channel_id = channel_id
            return "auth_bound"
        return "ignore"


def _send_gateway_payload(ws, payload):
    with _ws_lock:
        ws.send(json.dumps(payload))


def _send_heartbeat(ws):
    with _state_lock:
        seq = _last_sequence
    _send_gateway_payload(ws, {"op": 1, "d": seq})


def _heartbeat_loop(ws, interval_seconds):
    global _heartbeat_acked
    while _running:
        time.sleep(max(1.0, interval_seconds))
        if not _running:
            return
        with _state_lock:
            if _ws is not ws:
                return
            acked = _heartbeat_acked
            _heartbeat_acked = False
        if not acked:
            # No HEARTBEAT_ACK since the last beat: the connection is zombied.
            # Force a close so the gateway loop reconnects (and resumes).
            print("[DISCORD] Heartbeat not acknowledged; reconnecting")
            try:
                ws.close()
            except Exception:
                pass
            return
        try:
            _send_heartbeat(ws)
        except Exception as exc:
            print(f"[DISCORD] Heartbeat failed: {exc}")
            return


def _identify(ws):
    _send_gateway_payload(
        ws,
        {
            "op": 2,
            "d": {
                "token": _bot_token,
                "intents": _gateway_intents,
                "properties": {
                    "os": "linux",
                    "browser": "omegaclaw",
                    "device": "omegaclaw",
                },
            },
        },
    )


def _resume(ws):
    with _state_lock:
        session_id = _session_id
        seq = _last_sequence
    _send_gateway_payload(
        ws,
        {
            "op": 6,
            "d": {
                "token": _bot_token,
                "session_id": session_id,
                "seq": seq,
            },
        },
    )


def _handle_message_create(message):
    global _message_content_warning_logged

    channel_id = str(message.get("channel_id", "") or "").strip()
    content = str(message.get("content", "") or "").strip()
    author = message.get("author") or {}
    user_id = str(author.get("id", "") or "").strip()

    if not channel_id or not user_id:
        return

    with _state_lock:
        bot_user_id = _bot_user_id
    if author.get("bot") or (bot_user_id and user_id == bot_user_id):
        return

    if not content:
        with _state_lock:
            already_logged = _message_content_warning_logged
            _message_content_warning_logged = True
        if not already_logged:
            print(
                "[DISCORD] Received a message without content. Enable the "
                "MESSAGE_CONTENT privileged intent for this bot."
            )
        return

    state = _is_allowed_message(channel_id, user_id, content)
    display_name = _display_name(author, message.get("member") or {})
    if state == "allow":
        _set_last(f"{display_name}: {content}")
    elif state == "auth_bound":
        send_message(f"Authentication successful for {display_name}.")


def _gateway_loop():
    global _connected, _ws, _last_sequence, _bot_user_id
    global _session_id, _resume_gateway_url, _heartbeat_acked

    print("[DISCORD] Gateway listener started")
    retry_delay = 5
    want_resume = False
    resume_attempts = 0

    while _running:
        ws = None
        try:
            with _state_lock:
                can_resume = bool(
                    _session_id and _last_sequence is not None and _resume_gateway_url
                )
                resume_url = _resume_gateway_url
            do_resume = want_resume and can_resume and resume_attempts < _MAX_RESUME_ATTEMPTS
            if do_resume:
                resume_attempts += 1
            elif want_resume:
                # Resume not possible (or too many attempts): start fresh.
                with _state_lock:
                    _session_id = ""
                    _last_sequence = None
            connect_url = resume_url if do_resume else _gateway_url

            ws = websocket.WebSocket()
            ws.connect(connect_url)
            ws.settimeout(1)
            with _state_lock:
                _ws = ws
                _heartbeat_acked = True
                if not do_resume:
                    _last_sequence = None
                    _session_id = ""

            identified = False

            while _running:
                try:
                    raw = ws.recv()
                except websocket.WebSocketTimeoutException:
                    continue

                if not raw:
                    continue

                payload = json.loads(raw)
                op = payload.get("op")
                seq = payload.get("s")
                event_type = payload.get("t")
                data = payload.get("d")
                if not isinstance(data, dict):
                    data = {}

                if seq is not None:
                    with _state_lock:
                        _last_sequence = seq

                if op == 10:
                    interval = float(data.get("heartbeat_interval", 45000)) / 1000.0
                    with _state_lock:
                        _heartbeat_acked = True
                    threading.Thread(
                        target=_heartbeat_loop,
                        args=(ws, interval),
                        daemon=True,
                    ).start()
                    if do_resume:
                        print("[DISCORD] Resuming gateway session")
                        _resume(ws)
                    else:
                        _identify(ws)
                    identified = True
                elif op == 11:
                    with _state_lock:
                        _heartbeat_acked = True
                elif op == 1:
                    _send_heartbeat(ws)
                elif op == 7:
                    # Reconnect requested: the session can be resumed.
                    print("[DISCORD] Gateway requested reconnect")
                    want_resume = True
                    break
                elif op == 9:
                    # Invalid session. The payload is a boolean telling us
                    # whether the session may be resumed.
                    resumable = payload.get("d") is True
                    print(f"[DISCORD] Gateway session invalidated (resumable={resumable})")
                    if resumable:
                        want_resume = True
                    else:
                        want_resume = False
                        with _state_lock:
                            _session_id = ""
                            _last_sequence = None
                        # Discord asks for a 1-5s wait before re-identifying.
                        time.sleep(random.uniform(1.0, 5.0))
                    break
                elif op != 0:
                    continue

                if event_type == "READY":
                    user = data.get("user") or {}
                    ready_user_id = str(user.get("id", "") or "").strip()
                    session_id = str(data.get("session_id", "") or "").strip()
                    resume_url = str(data.get("resume_gateway_url", "") or "").strip()
                    with _state_lock:
                        if ready_user_id:
                            _bot_user_id = ready_user_id
                        _session_id = session_id
                        if resume_url:
                            _resume_gateway_url = resume_url
                    _connected = True
                    retry_delay = 5
                    want_resume = False
                    resume_attempts = 0
                    print("[DISCORD] Gateway ready")
                elif event_type == "RESUMED":
                    _connected = True
                    retry_delay = 5
                    want_resume = False
                    resume_attempts = 0
                    print("[DISCORD] Gateway resumed")
                elif event_type == "MESSAGE_CREATE":
                    _connected = True
                    _handle_message_create(data)

            if not identified:
                print("[DISCORD] Gateway closed before identify")
        except Exception as exc:
            _connected = False
            print(f"[DISCORD] Gateway error: {exc}")
            # An unexpected drop after a live session can be resumed.
            with _state_lock:
                if _session_id and _last_sequence is not None:
                    want_resume = True
        finally:
            try:
                if ws is not None:
                    ws.close()
            except Exception:
                pass
            with _state_lock:
                if _ws is ws:
                    _ws = None
            _connected = False

        if _running:
            if want_resume and resume_attempts < _MAX_RESUME_ATTEMPTS:
                # A resume is pending: retry promptly rather than backing off.
                time.sleep(1)
            else:
                time.sleep(retry_delay)
                retry_delay = min(retry_delay * 2, 60)

    print("[DISCORD] Gateway listener stopped")


def start_discord(channel_id="", gateway_intents=""):
    global _running, _bot_token, _api_base, _gateway_url, _channel_id
    global _gateway_intents, _connected, _authenticated_user_id
    global _message_content_warning_logged
    global _session_id, _resume_gateway_url, _last_sequence, _heartbeat_acked

    _bot_token = os.environ.get("DC_BOT_TOKEN", "").strip()
    if not _bot_token:
        raise ValueError("DC_BOT_TOKEN is required")

    _api_base = os.environ.get("DC_API_BASE", "https://discord.com/api/v10").rstrip("/")
    _gateway_url = os.environ.get(
        "DC_GATEWAY_URL",
        "wss://gateway.discord.gg/?v=10&encoding=json",
    ).strip()
    _channel_id = str(channel_id).strip()

    intents_value = str(gateway_intents or os.environ.get("DC_GATEWAY_INTENTS", "")).strip()
    if intents_value:
        try:
            _gateway_intents = int(intents_value)
        except Exception:
            _gateway_intents = _DEFAULT_GATEWAY_INTENTS
    else:
        _gateway_intents = _DEFAULT_GATEWAY_INTENTS

    _connected = False
    _authenticated_user_id = None
    _message_content_warning_logged = False
    _session_id = ""
    _resume_gateway_url = ""
    _last_sequence = None
    _heartbeat_acked = True

    _initialize_identity()
    if _channel_id:
        _validate_channel()
    else:
        print("[DISCORD] Starting adapter in auto-bind mode (channel not configured).")

    _running = True
    print(f"[DISCORD] Starting adapter with channel target: {_channel_id or 'auto-bind'}")
    t = threading.Thread(target=_gateway_loop, daemon=True)
    t.start()
    return t


def stop_discord():
    global _running
    _running = False
    with _state_lock:
        ws = _ws
    if ws is not None:
        try:
            ws.close()
        except Exception:
            pass


def send_message(text):
    text = str(text).replace("\\n", "\n").replace("\r", "")
    if not text:
        return

    with _state_lock:
        target_channel = _channel_id

    if not target_channel:
        return

    for i in range(0, len(text), _MAX_MESSAGE_LEN):
        chunk = text[i:i + _MAX_MESSAGE_LEN]
        if not chunk:
            continue
        try:
            _api_call(
                "POST",
                f"/channels/{target_channel}/messages",
                body={
                    "content": chunk,
                    "allowed_mentions": {"parse": []},
                },
                timeout=15,
            )
        except Exception as exc:
            print(f"[DISCORD] Send failed: {exc}")
            return
