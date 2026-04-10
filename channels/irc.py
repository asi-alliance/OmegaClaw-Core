import os
import random
import socket
import threading

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
            return True
        if candidate == _auth_secret:
            if _authenticated_nick is None:
                _authenticated_nick = norm_nick
            return False
        if _authenticated_nick is None:
            return False
        return norm_nick == _authenticated_nick

def _irc_loop(channel, server, port, nick):
    global _running, _sock, _connected
    sock = socket.socket()
    sock.connect((server, port))
    _sock = sock
    _send(f"NICK {nick}")
    _send(f"USER {nick} 0 * :{nick}")
    #_send(f"JOIN {channel}")
    while _running:
        try:
            data = sock.recv(4096).decode(errors="ignore")
        except OSError:
            break
        for line in data.split("\r\n"):
            if line.startswith("PING"):
                _send(f"PONG {line.split()[1]}")
            parts = line.split()
            if len(parts) > 1 and parts[1] == "001":
                _connected = True
                _send(f"JOIN {_channel}")
            elif line.startswith(":") and " PRIVMSG " in line:
                try:
                    prefix, trailing = line[1:].split(" PRIVMSG ", 1)
                    nick = prefix.split("!", 1)[0]

                    if " :" not in trailing:
                        return  # malformed, ignore safely

                    msg = trailing.split(" :", 1)[1]
                    if _is_allowed_message(nick, msg):
                        _set_last(f"{nick}: {msg}")
                except Exception:
                    pass  # never let IRC parsing kill the thread
    with _sock_lock:
        _sock = None
    sock.close()

def start_irc(channel, server="irc.libera.chat", port=6667, nick="omegaclaw", auth_secret=None):
    global _running, _channel, _connected
    nick = f"{nick}{random.randint(1000, 9999)}"
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
    if _connected:
        _send(f"PRIVMSG {_channel} :{text}")
