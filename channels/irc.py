import os
import random
import socket
import threading
import time
import textwrap
import auth
from src.logger import get_logger
import channels
from config import config_get_by_key

logger = get_logger(__name__)

_running = False
_sock = None
_sock_lock = threading.Lock()
_last_message = ""
_msg_lock = threading.Lock()
_channel = None
_connected = False
_auth_lock = threading.Lock()
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

def _is_auth_command(msg):
    lower = msg.strip().lower()
    return lower.startswith("auth ") or lower.startswith("/auth ")

def _is_allowed_message(nick, msg):
    global _authenticated_nick
    norm_nick = _normalize_nick(nick)
    with _auth_lock:
        if not auth.is_auth_enabled():
            return "allow"
        if _authenticated_nick is not None:
            return "allow" if norm_nick == _authenticated_nick else "ignore"
        candidate = _parse_auth_candidate(msg)
        user_id_check = auth.authenticate_channel_user('IRC', norm_nick, candidate)
        if user_id_check in ["auth_bound", "allow"]:
            _authenticated_nick = norm_nick
            return user_id_check
        else:
            return "ignore"

def _irc_loop(channel, server, port, nick):
    global _running, _sock, _connected
    logger.info(f"Connecting to {server}:{port} as {nick} for channel {channel}")
    try:
        sock = socket.create_connection((server, int(port)), timeout=15)
        sock.settimeout(60)
        logger.info("TCP connected")
    except OSError as e:
        logger.exception(f"Connect failed: {e}")
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
            logger.debug("IRC receive timed out, polling again")
            continue
        except OSError as e:
            logger.exception(f"IRC socket error, stopping receive loop: {e}")
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
                logger.info(f"Registered. Joining {_channel}")
                _send(f"JOIN {_channel}")
            elif len(parts) > 1 and parts[1] in {"403", "405", "471", "473", "474", "475"}:
                logger.error(f"Join failed: {line}")
            elif len(parts) > 1 and parts[1] == "433":
                logger.error(f"Nickname in use: {line}")
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
                except Exception as e:
                    logger.exception(f"Exception caught {repr(e)}")
    _connected = False
    with _sock_lock:
        _sock = None
    sock.close()
    logger.info("Disconnected")

def start_irc(channel, server="irc.libera.chat", port=6667, nick="omegaclaw"):
    global _running, _channel, _connected
    nick = f"{nick}{random.randint(1000, 9999)}"
    if not channel.startswith("#"):
        channel = f"#{channel}"
    _running = True
    _connected = False
    _channel = channel
    t = threading.Thread(target=_irc_loop, args=(channel, server, port, nick), daemon=True)
    t.start()
    return t

def stop_irc():
    global _running
    _running = False

def send_message(text):
    max_len = 400
    segments = text.replace("\r", "").split("\\n")
    lines = []
    for segment in segments:
        lines.extend(textwrap.wrap(segment, width=max_len, break_long_words=True, break_on_hyphens=False))
    for chunk in lines:
        try:
            if _connected and _channel:
                 _send(f"PRIVMSG {_channel} :{chunk}")
        except Exception as e:
            logger.exception(f"Error in send_message on channel {_channel}: {e}")

class IRCChannel(channels.CommChannel):

    def __init__(self):
        super().__init__()

    def start(self) -> None:
        channel = config_get_by_key("IRC_channel", "##omegaclaw")
        server = config_get_by_key("IRC_server", "irc.quakenet.org")
        port = int(config_get_by_key("IRC_port", 6667))
        user = config_get_by_key("IRC_user", "omegaclaw")
        start_irc(channel, server, port, user)

    def stop(self) -> None:
        stop_irc()

    def receive(self) -> str:
        return getLastMessage()

    def send(self, message: str) -> None:
        send_message(message)

def loadOmegaClawPlugin():
    channels.registerCommChannel("irc", IRCChannel())
