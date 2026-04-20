import os
import random
import socket
import threading
import time

_running = False
_sock = None
_sock_lock = threading.Lock()
_last_message = ""
_msg_lock = threading.Lock()
_channel = None
_connected = False
_auth_lock = threading.Lock()
_auth_secret = ""
_authenticated_nick = None

def _send(cmd):
    with _sock_lock:
        if _sock:
            _sock.sendall((cmd + "\r\n").encode())
    time.sleep(1)

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
    global _auth_secret, _authenticated_nick
    if secret is None:
        secret = os.environ.get("OMEGACLAW_AUTH_SECRET", "")
    with _auth_lock:
        _auth_secret = (secret or "").strip()
        _authenticated_nick = None


def _normalize_nick(nick):
    return nick.strip().lower()


def _parse_auth_candidate(msg):
    text = msg.strip()
    lower = text.lower()
    if lower.startswith("auth "):
        return text[5:].strip()
    if lower.startswith("/auth "):
        return text[6:].strip()
    return text


def _is_allowed_message(nick, msg):
    global _authenticated_nick
    candidate = _parse_auth_candidate(msg)
    norm_nick = _normalize_nick(nick)
    with _auth_lock:
        if not _auth_secret:
            return "allow"
        if candidate == _auth_secret:
            if _authenticated_nick is None:
                _authenticated_nick = norm_nick
                return "auth_bound"
            return "ignore"
        if _authenticated_nick is None:
            return "ignore"
        return "allow" if norm_nick == _authenticated_nick else "ignore"

def _irc_loop(channel, server, port, nick):
    global _running, _sock, _connected
    print(f"[IRC] Connecting to {server}:{port} as {nick} for channel {channel}")
    try:
        sock = socket.create_connection((server, int(port)), timeout=15)
        sock.settimeout(60)
        print("[IRC] TCP connected")
    except OSError as e:
        print(f"[IRC] Connect failed: {e}")
        return
    _sock = sock
    _send(f"NICK {nick}")
    _send(f"USER {nick} 0 * :{nick}")
    #_send(f"JOIN {channel}")
    read_buffer = ""
    while _running:
        try:
            data = sock.recv(4096).decode(errors="ignore")
            if not data:
                break
        except socket.timeout:
            continue
        except OSError:
            break
        read_buffer += data
        while "\r\n" in read_buffer:
            line, read_buffer = read_buffer.split("\r\n", 1)
            if not line:
                continue
            if line.startswith("PING"):
                _send(f"PONG {line.split()[1]}")
            parts = line.split()
            if len(parts) > 1 and parts[1] == "001":
                _connected = True
                print(f"[IRC] Registered. Joining {_channel}")
                _send(f"JOIN {_channel}")
            elif len(parts) > 1 and parts[1] in {"403", "405", "471", "473", "474", "475"}:
                print(f"[IRC] Join failed: {line}")
            elif len(parts) > 1 and parts[1] == "433":
                print(f"[IRC] Nickname in use: {line}")
            elif line.startswith(":") and " PRIVMSG " in line:
                try:
                    prefix, trailing = line[1:].split(" PRIVMSG ", 1)
                    nick = prefix.split("!", 1)[0]

                    if " :" not in trailing:
                        continue  # malformed, ignore safely

                    msg = trailing.split(" :", 1)[1]
                    state = _is_allowed_message(nick, msg)
                    if state == "allow":
                        _set_last(f"{nick}: {msg}")
                    elif state == "auth_bound":
                        _send(f"PRIVMSG {_channel} :Authentication successful for {nick}.")
                except Exception:
                    pass  # never let IRC parsing kill the thread
    _connected = False
    with _sock_lock:
        _sock = None
    sock.close()
    print("[IRC] Disconnected")

def start_irc(channel, server="irc.libera.chat", port=6667, nick="omegaclaw", auth_secret=None):
    global _running, _channel, _connected
    nick = f"{nick}{random.randint(1000, 9999)}"
    if not channel.startswith("#"):
        channel = f"#{channel}"
    _running = True
    _connected = False
    _channel = channel
    _set_auth_secret(auth_secret)
    t = threading.Thread(target=_irc_loop, args=(channel, server, port, nick), daemon=True)
    t.start()
    return t

def stop_irc():
    global _running
    _running = False

def send_message(text):
    max_len = 400
    lines = text.replace("\r", "").split("\\n")
    for text in lines:
        try:
            if _connected and _channel:
                for i in range(0, len(text), max_len):
                    chunk = text[i:i + max_len]
                    _send(f"PRIVMSG {_channel} :{chunk}")
        except Exception:
            pass
