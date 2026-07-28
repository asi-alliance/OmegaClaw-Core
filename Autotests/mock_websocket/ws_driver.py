"""Local mock WebSocket server standing in for the ASI Create chat.

The agent's WebSocket channel (`channels/wschat.py`) is a client: it connects
to a chat server, sends `resume`, receives `user_message`, replies with
`agent_message`, and expects `ack`. This driver is that server, running on the
pytest host, so the WS transport can be exercised without ASI Create.

Test-side surface mirrors RealTgDriver / SlackRealDriver:

- inject_user_message(text)  -> send `user_message{seq,text}` (auto seq)
- pop_agent_reply(timeout=N) -> (client_seq, text) from the agent, or (None, None)
- drain_agent_replies(...)   -> drain everything pending
- clear()                    -> empty the reply queue
- stop(timeout)              -> shut the server down
- mirror(text)               -> no-op (no separate mirror surface for WS)

Plus WS-specific hooks the channel tests need:

- inject_raw(raw)            -> send an arbitrary frame (malformed / unknown)
- drop_connection()          -> close the agent's socket to force a reconnect
- block_connections() / unblock_connections() -> refuse reconnects for a window
- wait_for_connection(...)   -> block until the agent is connected
- wait_for_resume(...)       -> block until a `resume` frame arrives; the last
                                one's `last_seen_seq` is on `.last_resume_seq`
"""
import json
import queue
import threading
import time


class WsMockDriver:
    def __init__(self, port, host="0.0.0.0", token="test-token"):
        self._host = host
        self._port = int(port)
        self._token = token or ""
        self._lock = threading.Lock()
        self._ws = None
        self._replies = queue.Queue()
        self._sent = []
        self._acks = []
        self._next_seq = 1
        self.last_resume_seq = None
        self._resume_count = 0
        self._connected = threading.Event()
        self._resumed = threading.Event()
        self._accept = threading.Event()
        self._accept.set()
        self._server = None
        self._ready = threading.Event()
        self._thread = threading.Thread(target=self._serve, daemon=True, name="ws-mock-server")
        self._thread.start()
        if not self._ready.wait(timeout=10):
            raise RuntimeError("WsMockDriver failed to start listening")
        print(f"[WsMockDriver] listening on {self._host}:{self._port}", flush=True)

    def inject_user_message(self, text, **_):
        with self._lock:
            seq = self._next_seq
            self._next_seq += 1
            self._sent.append((seq, str(text)))
        self._send({"type": "user_message", "seq": seq, "text": str(text)})
        print(f"[WsMockDriver] -> user_message seq={seq}: {text!r}", flush=True)
        return seq

    def inject_raw(self, raw):
        with self._lock:
            ws = self._ws
        if ws is None:
            raise RuntimeError("no agent connected")
        with self._lock:
            ws.send(raw)
        print(f"[WsMockDriver] -> raw frame: {raw!r}", flush=True)

    def pop_agent_reply(self, timeout=30):
        try:
            client_seq, text, _ts = self._replies.get(timeout=timeout)
            return client_seq, text
        except queue.Empty:
            return None, None

    def drain_agent_replies(self, max_wait=2):
        out = []
        deadline = time.time() + max_wait
        while time.time() < deadline:
            try:
                client_seq, text, _ts = self._replies.get(timeout=0.2)
                out.append((client_seq, text))
            except queue.Empty:
                break
        return out

    def clear(self):
        while True:
            try:
                self._replies.get_nowait()
            except queue.Empty:
                return

    def mirror(self, text):
        return

    _mirror = mirror

    def drop_connection(self):
        with self._lock:
            ws = self._ws
            self._ws = None
        self._connected.clear()
        if ws is not None:
            try:
                ws.close()
            except Exception:
                pass
            print("[WsMockDriver] dropped agent connection", flush=True)

    def block_connections(self):
        self._accept.clear()
        self.drop_connection()

    def unblock_connections(self):
        self._accept.set()

    def wait_for_connection(self, timeout=30):
        return self._connected.wait(timeout=timeout)

    def resume_count(self):
        with self._lock:
            return self._resume_count

    def wait_for_resume(self, min_count=1, timeout=30):
        deadline = time.time() + timeout
        while time.time() < deadline:
            with self._lock:
                if self._resume_count >= min_count:
                    return self.last_resume_seq
            time.sleep(0.1)
        return None

    def stop(self, timeout=5):
        self.drop_connection()
        if self._server is not None:
            try:
                self._server.shutdown()
            except Exception:
                pass
        self._thread.join(timeout=timeout)

    def _serve(self):
        from websockets.sync.server import serve

        with serve(self._handler, self._host, self._port,
                   process_request=self._process_request) as server:
            self._server = server
            self._ready.set()
            server.serve_forever()

    def _process_request(self, connection, request):
        if not self._accept.is_set():
            print("[WsMockDriver] refusing handshake (blocked)", flush=True)
            return connection.respond(503, "blocked")
        return None

    def _handler(self, ws):
        headers = getattr(ws.request, "headers", {})
        authorization = headers.get("Authorization", "") if hasattr(headers, "get") else ""
        if self._token and authorization != f"Bearer {self._token}":
            print(f"[WsMockDriver] rejecting unauthorized connection: {authorization!r}", flush=True)
            try:
                ws.close(1008, "unauthorized")
            except Exception:
                pass
            return

        with self._lock:
            self._ws = ws
        self._connected.set()
        print("[WsMockDriver] agent connected", flush=True)
        try:
            for raw in ws:
                self._on_frame(ws, raw)
        except Exception:
            pass
        finally:
            with self._lock:
                if self._ws is ws:
                    self._ws = None
                    self._connected.clear()

    def _on_frame(self, ws, raw):
        if isinstance(raw, bytes):
            raw = raw.decode("utf-8", errors="ignore")
        try:
            frame = json.loads(raw)
        except json.JSONDecodeError:
            return
        if not isinstance(frame, dict):
            return

        frame_type = frame.get("type")
        if frame_type == "resume":
            with self._lock:
                self.last_resume_seq = frame.get("last_seen_seq")
                self._resume_count += 1
                pending = list(self._sent)
            self._resumed.set()
            print(f"[WsMockDriver] <- resume last_seen_seq={frame.get('last_seen_seq')}", flush=True)
            for seq, text in pending:
                self._send({"type": "user_message", "seq": seq, "text": text}, ws=ws)
        elif frame_type == "agent_message":
            client_seq = frame.get("client_seq")
            text = frame.get("text")
            self._replies.put((client_seq, text, time.time()))
            self._acks.append(client_seq)
            print(f"[WsMockDriver] <- agent_message client_seq={client_seq}: {text!r}", flush=True)
            self._send({"type": "ack", "seq": None, "client_seq": client_seq}, ws=ws)
        else:
            print(f"[WsMockDriver] <- ignoring frame type {frame_type!r}", flush=True)

    def _send(self, payload, ws=None):
        with self._lock:
            target = ws if ws is not None else self._ws
            if target is None:
                return False
            try:
                target.send(json.dumps(payload))
                return True
            except Exception as exc:
                print(f"[WsMockDriver] send failed: {exc}", flush=True)
                return False
