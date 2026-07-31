"""
Health/status HTTP endpoint for OmegaClaw (plugin).

Serves the agent's liveness and high-level state over HTTP so orchestrators
can poll it directly instead of scraping `docker logs`:

    GET /health  -> 200 while the loop is alive, 503 when the heartbeat is stale
    GET /status  -> JSON {status, current_iteration, last_activity_at,
                          uptime_seconds, version}

`status` is one of "thinking", "sleeping", "idle" or "offline". It is fed from
the agent loop via heartbeat() once per iteration (the plugin subscribes with
add-heartbeat-listener); "offline" is reported when no heartbeat arrives within
stale_after seconds. The server runs in a daemon thread and uses only the
standard library.
"""

import json
import os
import threading
import time
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

STATUS_THINKING = "thinking"
STATUS_SLEEPING = "sleeping"
STATUS_IDLE = "idle"
STATUS_OFFLINE = "offline"

DEFAULT_STALE_AFTER_SECONDS = 120
DEFAULT_PORT = 8081  # unprivileged: the agent runs as `nobody`


def _config_get(key, default=None):
    """Read a setting through the agent's config system (command line,
    OMEGACLAW_<key> environment variable or config file), like the channel
    plugins do. Falls back to the OMEGACLAW_<key> environment variable when the
    agent runtime is not loaded, so the standalone self-test still works."""
    try:
        from config import config_get_by_key
    except ImportError:
        env = os.environ.get(f"OMEGACLAW_{key}")
        return env if env is not None else default
    return config_get_by_key(key, default)


def _iso(wall_time):
    if wall_time is None:
        return None
    return datetime.fromtimestamp(wall_time, tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _version():
    configured = _config_get("VERSION")
    if configured and str(configured).strip():
        return str(configured).strip()
    try:
        # this file lives at <repo>/plugins/health/health.py, so the repo root
        # is two directories up.
        repo_root = os.path.join(os.path.dirname(os.path.abspath(__file__)), os.pardir, os.pardir)
        for name in ("VERSION", "version.txt"):
            path = os.path.join(repo_root, name)
            if os.path.isfile(path):
                with open(path, "r", encoding="utf-8", errors="ignore") as fh:
                    content = fh.read().strip()
                    if content:
                        return content
    except OSError:
        pass
    return "unknown"


class _State:
    def __init__(self, stale_after=DEFAULT_STALE_AFTER_SECONDS):
        self._lock = threading.Lock()
        self._start_time = time.time()
        self._iteration = 0
        self._status = STATUS_IDLE
        self._last_heartbeat = None
        self.stale_after = stale_after

    def heartbeat(self, iteration, status):
        with self._lock:
            try:
                self._iteration = int(iteration)
            except (TypeError, ValueError):
                pass
            if status:
                self._status = str(status)
            self._last_heartbeat = time.time()

    def snapshot(self):
        with self._lock:
            now = time.time()
            is_stale = (
                self._last_heartbeat is None
                or (now - self._last_heartbeat) > self.stale_after
            )
            return {
                "status": STATUS_OFFLINE if is_stale else self._status,
                "current_iteration": self._iteration,
                "last_activity_at": _iso(self._last_heartbeat),
                "uptime_seconds": int(now - self._start_time),
                "version": _version(),
                "healthy": not is_stale,
            }


_state = _State()
_server = None
_server_lock = threading.Lock()


class _Handler(BaseHTTPRequestHandler):
    server_version = "OmegaClawHealth/1.0"

    def log_message(self, fmt, *args):
        return

    def _send_json(self, code, payload):
        body = json.dumps(payload).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        if self.command != "HEAD":
            self.wfile.write(body)

    def do_GET(self):
        path = self.path.split("?", 1)[0].rstrip("/") or "/"
        if path == "/health":
            snap = _state.snapshot()
            self._send_json(
                200 if snap["healthy"] else 503,
                {
                    "status": "ok" if snap["healthy"] else "unhealthy",
                    "agent_status": snap["status"],
                    "uptime_seconds": snap["uptime_seconds"],
                },
            )
        elif path == "/status":
            snap = _state.snapshot()
            snap.pop("healthy", None)
            self._send_json(200, snap)
        else:
            self._send_json(404, {"error": "not found", "path": path})

    do_HEAD = do_GET


def heartbeat(iteration=0, status=STATUS_IDLE):
    """Record a heartbeat from the agent loop. Returns a marker so it can sit in a MeTTa progn."""
    _state.heartbeat(iteration, status)
    return "HEALTH-HEARTBEAT-OK"


def start(port=None, stale_after=DEFAULT_STALE_AFTER_SECONDS):
    """Start the server in a daemon thread. Idempotent; bind failures are logged, not raised."""
    global _server
    with _server_lock:
        if _server is not None:
            return "HEALTH-ALREADY-RUNNING"
        try:
            resolved_port = int(port) if port else int(_config_get("HEALTH_PORT", DEFAULT_PORT))
        except (TypeError, ValueError):
            resolved_port = DEFAULT_PORT
        _state.stale_after = stale_after
        try:
            server = ThreadingHTTPServer(("0.0.0.0", resolved_port), _Handler)
        except OSError as exc:
            print(f"[HEALTH] could not bind port {resolved_port}: {exc}")
            return "HEALTH-BIND-FAILED"
        threading.Thread(target=server.serve_forever, name="omegaclaw-health", daemon=True).start()
        _server = server
        print(f"[HEALTH] health/status endpoint listening on 0.0.0.0:{resolved_port}")
        return "HEALTH-STARTED"


def stop():
    global _server
    with _server_lock:
        if _server is not None:
            _server.shutdown()
            _server.server_close()
            _server = None
    return "HEALTH-STOPPED"


def _selftest():
    """Standalone self-test: python3 plugins/health/health.py"""
    import socket
    import urllib.error
    import urllib.request

    def _get(path):
        try:
            with urllib.request.urlopen(f"http://127.0.0.1:{port}{path}", timeout=5) as resp:
                return resp.status, json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as err:
            return err.code, json.loads(err.read().decode("utf-8"))

    sock = socket.socket()
    sock.bind(("127.0.0.1", 0))
    port = sock.getsockname()[1]
    sock.close()

    assert start(port=port, stale_after=1) == "HEALTH-STARTED"
    try:
        assert start(port=port) == "HEALTH-ALREADY-RUNNING"

        code, body = _get("/status")
        assert code == 200 and body["current_iteration"] == 0 and body["last_activity_at"] is None, body
        assert set(body) == {"status", "current_iteration", "last_activity_at", "uptime_seconds", "version"}, body

        heartbeat(42, STATUS_THINKING)
        code, body = _get("/status")
        assert code == 200 and body["status"] == STATUS_THINKING and body["current_iteration"] == 42, body
        assert body["last_activity_at"] is not None, body
        code, body = _get("/health")
        assert code == 200 and body["status"] == "ok", (code, body)

        time.sleep(1.2)
        code, body = _get("/status")
        assert code == 200 and body["status"] == STATUS_OFFLINE, body
        code, body = _get("/health")
        assert code == 503 and body["status"] == "unhealthy", (code, body)

        heartbeat(43, STATUS_SLEEPING)
        assert _get("/health")[0] == 200
        code, body = _get("/status")
        assert body["status"] == STATUS_SLEEPING and body["current_iteration"] == 43, body

        assert _get("/nope")[0] == 404
        print("health.py self-test: PASS")
    finally:
        stop()


if __name__ == "__main__":
    _selftest()
