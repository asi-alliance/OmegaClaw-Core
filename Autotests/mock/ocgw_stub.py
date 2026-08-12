"""Stub OpenClaw Gateway implementing the OpenResponses POST /v1/responses contract.

The `openclaw_gateway` fixture in conftest.py starts it, so the delegation
tests carry their own Gateway rather than needing an external one. It uses
the standard library only.

Markers inside the delegated task text choose how the Gateway answers, since
the task text is the one thing a test controls all the way through:

    OCGW_SLEEP:<seconds>   hold the reply, used to prove delegation is async
    OCGW_503:<n>           answer 503 + Retry-After for the first <n> calls
    OCGW_UNAUTHORIZED      answer 401 regardless of the token
    OCGW_NOTEXT            answer 200 with a reasoning-only output
    Reply with exactly: X  answer exactly X

The stub records every request, so a test can check what the Gateway received
instead of inferring it from the agent's history: whether Nginx injected the
token, and whether two delegations landed in separate sessions.
"""
import json
import re
import threading
import time
import uuid
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

GATEWAY_PORT = 18789
RESPONSES_PATH = "/v1/responses"


class GatewayRecorder:
    def __init__(self, token):
        self.token = token
        self.requests = []
        self._lock = threading.Lock()
        self._counter = 0
        self._503_seen = {}

    def record(self, entry):
        with self._lock:
            self.requests.append(entry)

    def next_response_id(self):
        with self._lock:
            self._counter += 1
            return f"resp_{self._counter}_{uuid.uuid4().hex[:12]}"

    def count_503(self, key):
        with self._lock:
            seen = self._503_seen.get(key, 0)
            self._503_seen[key] = seen + 1
            return seen

    def reset(self):
        with self._lock:
            self.requests = []
            self._503_seen = {}

    def authorized_requests(self):
        return [r for r in self.requests if r["auth_ok"]]

    def response_ids(self):
        return [r["response_id"] for r in self.requests if r.get("response_id")]


def _make_handler(recorder):
    class Handler(BaseHTTPRequestHandler):
        protocol_version = "HTTP/1.1"

        def log_message(self, *args):
            pass

        def _reply(self, code, payload, extra_headers=None):
            body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
            self.send_response(code)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            for key, value in (extra_headers or {}).items():
                self.send_header(key, value)
            self.end_headers()
            self.wfile.write(body)

        def do_GET(self):
            self._reply(200, {"status": "alive"})

        def do_POST(self):
            length = int(self.headers.get("Content-Length", 0))
            raw = self.rfile.read(length).decode("utf-8", "replace")
            auth = self.headers.get("Authorization", "")
            try:
                body = json.loads(raw)
            except ValueError:
                body = {}
            task = str(body.get("input", ""))

            entry = {
                "path": self.path,
                "agent": self.headers.get("x-openclaw-agent-id", ""),
                "auth_header_present": bool(auth),
                "auth_ok": bool(recorder.token) and auth == f"Bearer {recorder.token}",
                "model": body.get("model"),
                "input": task,
                "response_id": None,
                "received_at": time.time(),
            }

            if self.path != RESPONSES_PATH:
                entry["outcome"] = "404"
                recorder.record(entry)
                return self._reply(404, {"error": {"message": "unknown endpoint",
                                                   "type": "not_found"}})

            if not entry["auth_ok"] or "OCGW_UNAUTHORIZED" in task:
                entry["outcome"] = "401"
                recorder.record(entry)
                return self._reply(401, {"error": {"message": "invalid or missing token",
                                                   "type": "invalid_token"}})

            retries = re.search(r"OCGW_503:(\d+)", task)
            if retries and recorder.count_503(task) < int(retries.group(1)):
                entry["outcome"] = "503"
                recorder.record(entry)
                return self._reply(503, {"error": {"message": "gateway is starting",
                                                   "type": "server_starting"}},
                                   {"Retry-After": "1"})

            delay = re.search(r"OCGW_SLEEP:(\d+)", task)
            if delay:
                time.sleep(int(delay.group(1)))

            response_id = recorder.next_response_id()
            entry["response_id"] = response_id

            if "OCGW_NOTEXT" in task:
                entry["outcome"] = "200 no-text"
                recorder.record(entry)
                return self._reply(200, {"id": response_id,
                                         "output": [{"type": "reasoning", "summary": []}]})

            exact = re.search(r"Reply with exactly:\s*(.+?)\s*$", task, re.S)
            reply = exact.group(1).strip() if exact else f"ack: {task[:200]}"
            entry["outcome"] = "200 ok"
            entry["reply"] = reply
            recorder.record(entry)
            return self._reply(200, {
                "id": response_id,
                "object": "response",
                "status": "completed",
                "output": [
                    {"type": "reasoning", "summary": []},
                    {"type": "message", "role": "assistant",
                     "content": [{"type": "output_text", "text": reply}]},
                ],
            })

    return Handler


class GatewayStub:
    def __init__(self, token, port=GATEWAY_PORT):
        self.recorder = GatewayRecorder(token)
        self._server = ThreadingHTTPServer(("0.0.0.0", port), _make_handler(self.recorder))
        self._server.daemon_threads = True
        self._thread = threading.Thread(target=self._server.serve_forever, daemon=True)

    def start(self):
        self._thread.start()
        return self

    def stop(self, timeout=5):
        self._server.shutdown()
        self._server.server_close()
        self._thread.join(timeout)
