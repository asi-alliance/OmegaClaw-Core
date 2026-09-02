"""Driver bot for the Telegram autotest suite.

Uses a second bot ("driver bot") to talk to the agent bot via Telegram's
bot-to-bot communication mode (Bot API 10.0, May 2026). Test-side surface:

- `inject_user_message(text, ...)` -> driver sends `sendMessage(@agent, text)`
- `pop_agent_reply(timeout=N)`     -> blocks on driver's getUpdates inbox
- `drain_agent_replies(...)`       -> drains everything pending
- `clear()`                        -> empties driver's inbox queue
- `mirror(text)` / `_mirror`       -> echo bot-to-bot traffic and per-test
                                      PASS/FAIL/SKIP to TG_MIRROR_CHAT_ID

Requires `channels/telegram.py` to run against the real api.telegram.org
and both bots opted into bot-to-bot mode via BotFather. See
`Autotests/mock_telegram/README.md` for setup.
"""
import json
import queue
import threading
import time
import urllib.parse
import urllib.request


class RealTgDriver:
    def __init__(self, driver_token, agent_username, poll_timeout=20, mirror_chat_id=None):
        self._token = driver_token
        if not self._token:
            raise ValueError("driver_token is required")
        self._agent = agent_username.lstrip("@") if agent_username else ""
        if not self._agent:
            raise ValueError("agent_username is required")
        self._api = f"https://api.telegram.org/bot{self._token}"
        self._poll_timeout = max(1, int(poll_timeout))
        self._mirror_chat_id = str(mirror_chat_id).strip() if mirror_chat_id else ""
        self._inbox = queue.Queue()
        self._stop = threading.Event()
        self._offset = self._drain_initial_offset()
        self._thread = threading.Thread(target=self._poll, daemon=True)
        self._thread.start()
        print(f"[RealTgDriver] driver -> @{self._agent} (initial offset={self._offset}, "
              f"mirror={self._mirror_chat_id or 'off'})", flush=True)

    # ---- test-side API --------------------------------------------------
    def inject_user_message(self, text, user_id=None, chat_id=None, username=None):
        # user_id/chat_id/username are ignored: the driver bot is the only
        # sender real Telegram knows about. They exist in the signature so
        # the call site can be transport-agnostic with the IRC harness.
        self._api_call("sendMessage", {"chat_id": f"@{self._agent}", "text": str(text)},
                       use_post=True, timeout=15)
        print(f"[RealTgDriver] driver -> @{self._agent}: {text!r}", flush=True)
        self._mirror(f"-> {text}")

    def pop_agent_reply(self, timeout=30):
        try:
            chat_id, text, _ts = self._inbox.get(timeout=timeout)
            return chat_id, text
        except queue.Empty:
            return None, None

    def drain_agent_replies(self, max_wait=2):
        out = []
        deadline = time.time() + max_wait
        while time.time() < deadline:
            try:
                chat_id, text, _ts = self._inbox.get(timeout=0.2)
                out.append((chat_id, text))
            except queue.Empty:
                break
        return out

    def clear(self):
        while True:
            try:
                self._inbox.get_nowait()
            except queue.Empty:
                return

    def stop(self, timeout=5):
        self._stop.set()
        self._thread.join(timeout=timeout)

    # ---- internals ------------------------------------------------------
    def _api_call(self, method, params=None, timeout=20, use_post=False):
        params = params or {}
        url = f"{self._api}/{method}"
        if use_post:
            data = urllib.parse.urlencode(params).encode("utf-8")
            req = urllib.request.Request(url, data=data)
        else:
            if params:
                url = f"{url}?{urllib.parse.urlencode(params)}"
            req = urllib.request.Request(url)
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            payload = json.loads(resp.read().decode("utf-8", errors="ignore"))
        if not payload.get("ok"):
            raise RuntimeError(payload.get("description", f"{method} failed"))
        return payload.get("result")

    def _drain_initial_offset(self):
        try:
            updates = self._api_call("getUpdates", {"timeout": 0}, timeout=10) or []
        except Exception as exc:
            print(f"[RealTgDriver] initial offset probe failed: {exc}", flush=True)
            return None
        if not updates:
            return None
        return max(u.get("update_id", 0) for u in updates) + 1

    def _poll(self):
        while not self._stop.is_set():
            try:
                params = {"timeout": self._poll_timeout}
                if self._offset is not None:
                    params["offset"] = self._offset
                updates = self._api_call(
                    "getUpdates", params, timeout=self._poll_timeout + 10
                ) or []
                for u in updates:
                    uid = u.get("update_id")
                    if isinstance(uid, int):
                        if self._offset is None or uid + 1 > self._offset:
                            self._offset = uid + 1
                    msg = u.get("message") or u.get("edited_message")
                    if not isinstance(msg, dict):
                        continue
                    text = msg.get("text")
                    if not text:
                        continue
                    chat = msg.get("chat") or {}
                    self._inbox.put((str(chat.get("id", "")), text, int(time.time())))
                    sender = (msg.get("from") or {}).get("username") or "?"
                    print(f"[RealTgDriver] @{sender} -> driver: {text!r}", flush=True)
                    self._mirror(f"<- {text}")
            except Exception as exc:
                if self._stop.is_set():
                    return
                print(f"[RealTgDriver] poll error: {exc}", flush=True)
                time.sleep(2)

    def mirror(self, text):
        if not self._mirror_chat_id:
            return
        try:
            self._api_call("sendMessage",
                           {"chat_id": self._mirror_chat_id, "text": text},
                           use_post=True, timeout=10)
        except Exception as exc:
            print(f"[RealTgDriver] mirror failed: {exc}", flush=True)

    _mirror = mirror
