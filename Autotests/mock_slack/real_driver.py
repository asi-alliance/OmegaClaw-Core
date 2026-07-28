"""Real Slack drop-in driver for mock_slack tests.

Uses a second Slack bot ("driver bot") to talk to the agent bot through a
shared channel. Modern Bot users post messages without a `subtype`, so the
agent's normal polling loop (`channels/slack.py:_poll_channel`) treats the
driver's posts as regular user messages and routes them through the auth
gate. Test-side surface mirrors RealTgDriver:

- inject_user_message(text)  -> driver posts to the shared channel
- pop_agent_reply(timeout=N)  -> blocks on the driver's polled inbox
- drain_agent_replies(...)    -> drain everything pending
- clear()                     -> empty inbox
- mirror(text)                -> post a one-line marker into the shared
                                 channel itself (no separate mirror channel
                                 needed in Slack; humans in the channel see
                                 the whole exchange directly).
"""
import json
import queue
import threading
import time
import urllib.parse
import urllib.request


SLACK_API = "https://slack.com/api"


class SlackRealDriver:
    def __init__(self, driver_token, channel_id, agent_user_id, poll_interval=5):
        self._token = (driver_token or "").strip()
        if not self._token:
            raise ValueError("driver_token is required")
        self._channel = (channel_id or "").strip()
        if not self._channel:
            raise ValueError("channel_id is required")
        self._agent_user_id = (agent_user_id or "").strip()
        if not self._agent_user_id:
            raise ValueError("agent_user_id is required")
        self._poll_interval = max(1, int(poll_interval))
        self._inbox = queue.Queue()
        self._stop = threading.Event()
        self._driver_user_id = self._who_am_i()
        self._cursor = self._initial_cursor()
        self._thread = threading.Thread(target=self._poll, daemon=True)
        self._thread.start()
        print(f"[SlackRealDriver] driver={self._driver_user_id} -> channel={self._channel} "
              f"(agent={self._agent_user_id}, cursor={self._cursor})", flush=True)

    # ---- test-side API (matches MockTelegramServer / RealTgDriver) -------
    def inject_user_message(self, text, **_):
        self._post(str(text))
        print(f"[SlackRealDriver] driver -> #{self._channel}: {text!r}", flush=True)

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

    def mirror(self, text):
        try:
            self._post(str(text))
        except Exception as exc:
            print(f"[SlackRealDriver] mirror failed: {exc}", flush=True)

    def stop(self, timeout=5):
        self._stop.set()
        self._thread.join(timeout=timeout)

    # ---- internals -------------------------------------------------------
    def _api(self, method, params=None, timeout=20):
        body = urllib.parse.urlencode(params or {}).encode("utf-8")
        req = urllib.request.Request(
            f"{SLACK_API}/{method}",
            data=body,
            headers={
                "Authorization": f"Bearer {self._token}",
                "Content-Type": "application/x-www-form-urlencoded",
            },
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            payload = json.loads(resp.read().decode("utf-8", errors="ignore"))
        if not payload.get("ok"):
            raise RuntimeError(payload.get("error", f"{method} failed"))
        return payload

    def _who_am_i(self):
        return self._api("auth.test", timeout=10).get("user_id", "")

    def _post(self, text):
        self._api("chat.postMessage", {"channel": self._channel, "text": text}, timeout=15)

    def _initial_cursor(self):
        payload = self._api("conversations.history",
                            {"channel": self._channel, "limit": 1}, timeout=15)
        messages = payload.get("messages") or []
        return str(messages[0].get("ts", "")).strip() if messages else ""

    def _poll(self):
        while not self._stop.is_set():
            try:
                params = {"channel": self._channel, "limit": 20}
                if self._cursor:
                    params["oldest"] = self._cursor
                    params["inclusive"] = "false"
                payload = self._api("conversations.history", params, timeout=30)
                messages = payload.get("messages") or []
                if messages:
                    ordered = sorted(messages, key=lambda m: float(m.get("ts", 0.0)))
                    for msg in ordered:
                        ts = str(msg.get("ts", "")).strip()
                        if ts:
                            self._cursor = ts
                        if msg.get("subtype"):
                            continue
                        user = str(msg.get("user", "")).strip()
                        text = str(msg.get("text", "")).strip()
                        if not user or not text:
                            continue
                        if user == self._driver_user_id:
                            continue
                        if user != self._agent_user_id:
                            continue
                        self._inbox.put((self._channel, text, int(time.time())))
                        print(f"[SlackRealDriver] agent -> driver: {text!r}", flush=True)
            except Exception as exc:
                if self._stop.is_set():
                    return
                print(f"[SlackRealDriver] poll error: {exc}", flush=True)
            time.sleep(self._poll_interval)
