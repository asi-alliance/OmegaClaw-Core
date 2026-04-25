"""Local terminal channel for Oma — internet-free.

Pairs with the small chat-REPL TUI in `tui.py` at the repo root.

Wire:
  /tmp/oma-in   (FIFO)  — TUI writes user input lines here; Oma reads.
  /tmp/oma-out  (FIFO)  — Oma writes outbound messages here; TUI reads.

Same channel contract as channels/irc.py and channels/telegram.py:
  start_local(...)     — spawn the listener thread, open the fifos.
  getLastMessage()     — return + clear the accumulated inbound buffer.
  send_message(str)    — push outbound text to the TUI.

The auth-secret pattern works identically to the Telegram adapter, but for
the local channel we treat any single user (the one at this terminal) as
authenticated by default — set OMEGACLAW_AUTH_SECRET to require an explicit
`auth <secret>` line if you ever want to gate input here too.
"""
import os
import threading
import errno

_IN_PATH = "/tmp/oma-in"
_OUT_PATH = "/tmp/oma-out"

_running = False
_listener_thread = None

_msg_lock = threading.Lock()
_last_message = ""

_out_lock = threading.Lock()
_out_fd = None  # opened lazily on first send

_auth_lock = threading.Lock()
_auth_secret = ""
_authenticated = False  # single-user gate; True once secret matches (or if secret unset)


def _ensure_fifo(path):
    """Create the named pipe if it doesn't already exist."""
    try:
        if not os.path.exists(path):
            os.mkfifo(path, 0o600)
    except FileExistsError:
        pass


def _set_last(line):
    global _last_message
    with _msg_lock:
        if _last_message == "":
            _last_message = line
        else:
            _last_message = _last_message + " | " + line


def getLastMessage():
    global _last_message
    with _msg_lock:
        tmp = _last_message
        _last_message = ""
        return tmp


def _set_auth_secret(secret=None):
    global _auth_secret, _authenticated
    if secret is None:
        secret = os.environ.get("OMEGACLAW_AUTH_SECRET", "")
    with _auth_lock:
        _auth_secret = (secret or "").strip()
        # If no secret is configured, the local terminal user is trusted by default.
        _authenticated = (_auth_secret == "")


def _parse_auth_candidate(line):
    text = line.strip()
    lower = text.lower()
    if lower.startswith("auth "):
        return text[5:].strip()
    if lower.startswith("/auth "):
        return text[6:].strip()
    return text


def _is_allowed(line):
    """Same shape as the other adapters' allowance check, simplified to a
       single local user."""
    global _authenticated
    candidate = _parse_auth_candidate(line)
    with _auth_lock:
        if not _auth_secret:
            return True
        if candidate == _auth_secret:
            _authenticated = True
            return False  # auth handshake itself isn't passed through
        return _authenticated


def _read_loop():
    """Block-read /tmp/oma-in line by line; push allowed lines into the
       inbound buffer so Oma's `(receive)` picks them up."""
    while _running:
        try:
            # Open read-only every iteration: the writer (TUI) may close and reopen.
            with open(_IN_PATH, "r") as f:
                for line in f:
                    if not _running:
                        break
                    line = line.rstrip("\n")
                    if not line:
                        continue
                    if _is_allowed(line):
                        _set_last(f"local: {line}")
        except Exception:
            # Re-open on any read error; sleep briefly to avoid a tight error loop.
            import time
            time.sleep(0.5)


def start_local(*_args, **_kwargs):
    """Called from src/channels.metta initChannels for commchannel=local.

       Positional/keyword args ignored — the local channel takes no runtime
       parameters. The signature matches the other adapters' so the
       channels.metta dispatch can be uniform if desired."""
    global _running, _listener_thread
    _ensure_fifo(_IN_PATH)
    _ensure_fifo(_OUT_PATH)
    _set_auth_secret(None)
    _running = True
    _listener_thread = threading.Thread(target=_read_loop, daemon=True)
    _listener_thread.start()
    return _listener_thread


def stop_local():
    global _running
    _running = False


def send_message(text):
    """Write outbound text to /tmp/oma-out. The TUI tails this fifo.

       We open the fifo lazily because it blocks until a reader is present;
       failing to open silently is the right behavior so Oma keeps running
       even when no TUI is attached."""
    global _out_fd
    text = text.replace("\\n", "\n")
    if not text:
        return
    with _out_lock:
        try:
            if _out_fd is None or _out_fd.closed:
                # Non-blocking open; raises if no reader is present.
                fd = os.open(_OUT_PATH, os.O_WRONLY | os.O_NONBLOCK)
                _out_fd = os.fdopen(fd, "w", buffering=1)
            _out_fd.write(text + "\n---\n")
            _out_fd.flush()
        except OSError as e:
            if e.errno == errno.ENXIO:
                # No reader on the fifo right now — drop the message silently
                # rather than blocking the agent loop.
                _out_fd = None
            else:
                _out_fd = None
        except Exception:
            _out_fd = None
