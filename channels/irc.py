import socket, threading, random

_running = False
_sock = None
_sock_lock = threading.Lock()
_last_message = ""
_msg_lock = threading.Lock()
_channel = None
_connected = False

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
                    _set_last(f"{nick}: {msg}")
                except Exception:
                    pass  # never let IRC parsing kill the thread
    with _sock_lock:
        _sock = None
    sock.close()

def start_irc(channel, server="irc.libera.chat", port=6667, nick="mettaclaw"):
    global _running, _channel
    nick = f"{nick}{random.randint(1000, 9999)}"
    _running = True
    _channel = channel
    t = threading.Thread(target=_irc_loop, args=(channel, server, port, nick), daemon=True)
    t.start()
    return t

def stop_irc():
    global _running
    _running = False

def send_message(text):
    if _connected:
        _send(f"PRIVMSG {_channel} :{text}")
