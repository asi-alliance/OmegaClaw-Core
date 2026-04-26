#!/usr/bin/env python3
"""Minimal local web UI for Oma — read live status + send prompts.

Stdlib only. Single file. Local-only by design (binds 127.0.0.1).
Pairs with channels/local.py the same way tui.py does:
  - Outbound (Oma → user): tailed from /tmp/omegaclaw.log
  - Inbound (user → Oma): written to /tmp/oma-in
  - Stats: parsed from /tmp/omegaclaw.log + Ollama HTTP API + /proc/<pid>

Run:
    python3 webui.py
Open:
    http://127.0.0.1:22333

The page polls /stats every 2 s and /messages every 1.5 s. POST /send
writes whatever you type to the fifo so Oma's `(receive)` picks it up.
"""
import http.server
import json
import os
import re
import shlex
import socketserver
import subprocess
import threading
import time
import urllib.request
from urllib.parse import urlparse

PORT = 22333  # RAW nod: 23 enigma + 33 (apple of discord). The fnord is a feature.
LOG_PATH = "/tmp/omegaclaw.log"
IN_FIFO = "/tmp/oma-in"
OLLAMA_BASE = os.environ.get("OLLAMA_BASE_URL", "http://192.168.86.22:11434")

# --- caching -----------------------------------------------------------------
_ollama_cache = {"ts": 0, "data": {}}
_OLLAMA_CACHE_TTL = 5.0

# tps probe — periodically asks Ollama for a tiny generation to read its own
# eval_count / eval_duration. Cached so we don't beat up the GPU; runs in a
# background thread so /stats responses stay snappy.
_tps_cache = {"ts": 0, "tps": 0, "model": "", "stale": True}
_TPS_PROBE_TTL = 30.0
_tps_lock = threading.Lock()

# --- helpers -----------------------------------------------------------------

def find_swipl():
    """Return (pid, cmdline_str) for the active swipl Oma process, or (None, '')."""
    try:
        out = subprocess.check_output(
            ["pgrep", "-af", "[s]wipl.*main.pl"], text=True
        ).strip()
        if not out:
            return None, ""
        line = out.splitlines()[0]
        parts = line.split(None, 1)
        return int(parts[0]), parts[1] if len(parts) > 1 else ""
    except Exception:
        return None, ""


def proc_rss_mb(pid):
    try:
        with open(f"/proc/{pid}/status") as f:
            for line in f:
                if line.startswith("VmRSS"):
                    return int(line.split()[1]) // 1024
    except Exception:
        pass
    return 0


def proc_uptime_seconds(pid):
    try:
        with open(f"/proc/{pid}/stat") as f:
            stat = f.read().split()
        starttime_jiffies = int(stat[21])
        with open("/proc/uptime") as f:
            sys_uptime = float(f.read().split()[0])
        clk = os.sysconf("SC_CLK_TCK")
        return int(sys_uptime - (starttime_jiffies / clk))
    except Exception:
        return 0


def fmt_uptime(secs):
    if secs <= 0:
        return "?"
    h, rem = divmod(secs, 3600)
    m, s = divmod(rem, 60)
    if h:
        return f"{h}h{m:02d}m"
    if m:
        return f"{m}m{s:02d}s"
    return f"{s}s"


def grep_count(pattern, path=LOG_PATH):
    try:
        with open(path, "r", errors="replace") as f:
            return sum(1 for line in f if re.search(pattern, line))
    except Exception:
        return 0


def ollama_state():
    """Cached Ollama /api/ps + /api/tags lookup so we don't hammer the box."""
    now = time.time()
    if now - _ollama_cache["ts"] < _OLLAMA_CACHE_TTL and _ollama_cache["data"]:
        return _ollama_cache["data"]
    data = {"loaded": [], "available": []}
    try:
        with urllib.request.urlopen(f"{OLLAMA_BASE}/api/ps", timeout=2) as r:
            ps = json.load(r)
            data["loaded"] = [
                {"name": m["name"], "vram_mb": m.get("size_vram", 0) // 1024 // 1024}
                for m in ps.get("models", [])
            ]
    except Exception:
        pass
    try:
        with urllib.request.urlopen(f"{OLLAMA_BASE}/api/tags", timeout=2) as r:
            tags = json.load(r)
            data["available"] = [m["name"] for m in tags.get("models", [])]
    except Exception:
        pass
    _ollama_cache["ts"] = now
    _ollama_cache["data"] = data
    return data


def git_version():
    try:
        out = subprocess.check_output(
            ["git", "-C", os.path.dirname(os.path.abspath(__file__)),
             "rev-parse", "--short", "HEAD"],
            text=True, stderr=subprocess.DEVNULL,
        ).strip()
        return out
    except Exception:
        return "?"


def _probe_tps_blocking(model):
    """One-shot generation probe to measure model gen tok/s. Returns float or 0.

       Uses a short num_predict (10) so the probe completes quickly even on
       slow MoE models like Granite4-32B. Long timeout (240 s) so a busy GPU
       sharing with Oma's 12k-token prompts doesn't make the probe falsely
       report 0."""
    try:
        body = json.dumps({
            "model": model, "stream": False,
            "options": {"num_predict": 10, "temperature": 0.0},
            "messages": [{"role": "user", "content": "Reply with: pong"}],
        }).encode()
        req = urllib.request.Request(
            f"{OLLAMA_BASE}/api/chat", data=body,
            headers={"Content-Type": "application/json"},
        )
        with urllib.request.urlopen(req, timeout=240) as r:
            d = json.load(r)
        ev_n = d.get("eval_count", 0)
        ev_d = d.get("eval_duration", 1) or 1
        return round(ev_n / (ev_d / 1e9), 1) if (ev_d > 0 and ev_n > 0) else 0
    except Exception:
        return 0


def _tps_refresh_worker():
    """Background loop: probe every TTL + a small jitter, never on demand from /stats."""
    while True:
        try:
            now = time.time()
            with _tps_lock:
                age = now - _tps_cache["ts"]
            if age >= _TPS_PROBE_TTL:
                # Find currently-loaded model, fall back to OLLAMA_MODEL or first available
                state = ollama_state()
                model = ""
                if state["loaded"]:
                    model = state["loaded"][0]["name"]
                elif state["available"]:
                    model = state["available"][0]
                if model:
                    tps = _probe_tps_blocking(model)
                    with _tps_lock:
                        _tps_cache.update({"ts": time.time(), "tps": tps,
                                           "model": model, "stale": False})
        except Exception:
            pass
        time.sleep(5)


def get_tps():
    with _tps_lock:
        return dict(_tps_cache)


def full_history():
    """Read ALL of memory/history.metta (the persisted transcript). Falls
       back to scanning the runtime log if history.metta isn't writable
       in the same way."""
    candidates = [
        "/home/omaclaw/PeTTa/repos/OmegaClaw-Core/memory/history.metta",
        os.path.join(os.path.dirname(os.path.abspath(__file__)), "memory", "history.metta"),
    ]
    msgs = []
    text = ""
    for p in candidates:
        if os.path.exists(p):
            try:
                with open(p, "r", errors="replace") as f:
                    text = f.read()
                break
            except Exception:
                continue
    # Walk the file in order looking for time-stamped pairs and HUMAN/send markers.
    # history.metta uses a slightly different format than the runtime log;
    # extract whatever we can.
    for m in re.finditer(r"^\(HUMAN-MSG:\s*(.+?)\)\s*$", text, re.MULTILINE):
        inner = m.group(1).strip()
        inner = re.sub(r"^[A-Za-z0-9_-]+:\s*", "", inner)
        if inner:
            msgs.append({"who": "you", "text": inner, "pos": m.start()})
    for m in _SEND_RE.finditer(text):
        t = m.group(1)
        if t and t != "[ERROR_FEEDBACK]":
            msgs.append({"who": "oma", "text": t, "pos": m.start()})
    for m in _SEND_POSITIONAL_RE.finditer(text):
        t = m.group(1)
        if t and t != "[ERROR_FEEDBACK]":
            msgs.append({"who": "oma", "text": t, "pos": m.start()})
    msgs.sort(key=lambda x: x["pos"])
    # Fall back to runtime log if the history file is sparse
    if len(msgs) < 5:
        runtime = recent_messages(limit=500)
        for r in runtime:
            msgs.append({"who": r["who"], "text": r["text"], "pos": -1})
    # Dedup adjacent identical
    cleaned = []
    for m in msgs:
        rec = {"who": m["who"], "text": m["text"]}
        if not cleaned or cleaned[-1] != rec:
            cleaned.append(rec)
    return cleaned


def channels_status():
    """Survey of which channels Oma can talk over and current state."""
    pid, cmd = find_swipl()
    active = "?"
    if "commchannel=local" in cmd: active = "local"
    elif "commchannel=telegram" in cmd: active = "telegram"
    elif "commchannel=irc" in cmd: active = "irc"
    elif "commchannel=mattermost" in cmd: active = "mattermost"
    channels = []
    # Local
    in_present = os.path.exists("/tmp/oma-in")
    out_present = os.path.exists("/tmp/oma-out")
    channels.append({
        "name": "local",
        "active": active == "local",
        "available": True,
        "details": [
            f"input fifo: {'present' if in_present else 'missing'} (/tmp/oma-in)",
            f"output fifo: {'present' if out_present else 'missing'} (/tmp/oma-out)",
            "client: tui.py (CLI) + webui.py (this page)",
        ],
    })
    # Telegram
    tg_token = ""
    if "TG_BOT_TOKEN=" in cmd:
        m = re.search(r"TG_BOT_TOKEN=(\S+)", cmd)
        if m: tg_token = m.group(1)
    tg_details = []
    if tg_token:
        try:
            with urllib.request.urlopen(
                f"https://api.telegram.org/bot{tg_token}/getMe", timeout=4
            ) as r:
                d = json.load(r)
            if d.get("ok"):
                u = d["result"]
                tg_details.append(f"bot: @{u.get('username','?')} (id {u.get('id')})")
                tg_details.append(f"name: {u.get('first_name','?')}")
            else:
                tg_details.append(f"telegram api error: {d}")
        except Exception as e:
            tg_details.append(f"telegram unreachable: {e}")
    else:
        tg_details.append("not configured (no TG_BOT_TOKEN passed at launch)")
    channels.append({
        "name": "telegram",
        "active": active == "telegram",
        "available": bool(tg_token),
        "details": tg_details,
    })
    # IRC
    channels.append({
        "name": "irc",
        "active": active == "irc",
        "available": True,
        "details": ["adapter: channels/irc.py", "default server: irc.quakenet.org",
                    "set commchannel=irc and IRC_channel=#... to use"],
    })
    # Mattermost
    channels.append({
        "name": "mattermost",
        "active": active == "mattermost",
        "available": True,
        "details": ["adapter: channels/mattermost.py", "needs MM_URL/MM_CHANNEL_ID/MM_BOT_TOKEN"],
    })
    return {"active": active, "channels": channels}


def settings_view():
    """Read-only view of paths, sizes, and key config — no editing here."""
    pid, cmd = find_swipl()
    repo = os.path.dirname(os.path.abspath(__file__))
    paths = []
    for label, p in [
        ("repo", repo),
        ("history.metta", os.path.join(repo, "memory", "history.metta")),
        ("prompt.txt", os.path.join(repo, "memory", "prompt.txt")),
        ("models.yaml", os.path.join(repo, "models.yaml")),
        ("chroma_db", "/home/omaclaw/PeTTa/chroma_db"),
        ("runtime log", LOG_PATH),
    ]:
        try:
            if os.path.isdir(p):
                paths.append({"label": label, "path": p, "size_mb": _dir_size_mb(p),
                              "kind": "dir"})
            elif os.path.exists(p):
                size = os.path.getsize(p)
                paths.append({"label": label, "path": p,
                              "size_mb": round(size / 1024 / 1024, 2), "kind": "file"})
            else:
                paths.append({"label": label, "path": p, "size_mb": 0, "kind": "missing"})
        except Exception:
            paths.append({"label": label, "path": p, "size_mb": 0, "kind": "?"})

    # Per-model format config from models.yaml
    model_formats = []
    try:
        import yaml
        cfg_path = os.path.join(repo, "models.yaml")
        if os.path.exists(cfg_path):
            with open(cfg_path) as f:
                cfg = yaml.safe_load(f) or {}
            for name, spec in cfg.items():
                fmt = (spec or {}).get("format", "metta") if isinstance(spec, dict) else "metta"
                model_formats.append({"name": name, "format": fmt})
    except Exception:
        pass

    # Env vars (filter sensitive)
    env_pairs = {}
    if pid:
        try:
            for kv in open(f"/proc/{pid}/environ").read().split("\0"):
                if "=" in kv:
                    k, v = kv.split("=", 1)
                    if k in ("OMEGACLAW_AUTH_SECRET", "OLLAMA_MODEL", "OLLAMA_BASE_URL",
                             "ANTHROPIC_API_KEY"):
                        if k == "OMEGACLAW_AUTH_SECRET" and v:
                            v = "(set)"
                        elif k == "ANTHROPIC_API_KEY" and v:
                            v = v[:10] + "…" + v[-4:]
                        env_pairs[k] = v
        except Exception:
            pass

    return {
        "swipl_pid": pid, "swipl_cmd": cmd,
        "git_branch": git_branch(), "git_commit": git_version(),
        "ollama_base": OLLAMA_BASE,
        "paths": paths,
        "model_formats": model_formats,
        "env": env_pairs,
    }


def _dir_size_mb(d):
    total = 0
    try:
        for root, _, files in os.walk(d):
            for f in files:
                try:
                    total += os.path.getsize(os.path.join(root, f))
                except OSError:
                    pass
    except Exception:
        return 0
    return round(total / 1024 / 1024, 2)


def relaunch_swipl(new_model):
    """Kill the running swipl Oma and relaunch with a different OLLAMA_MODEL.
       Preserves the prior auth secret + provider + commchannel + token args
       by reading them from /proc/<pid>/environ and /proc/<pid>/cmdline."""
    pid, _cmd = find_swipl()
    if not pid:
        return False, "no swipl currently running"
    try:
        env_pairs = open(f"/proc/{pid}/environ").read().split("\0")
        env = dict(p.split("=", 1) for p in env_pairs if "=" in p)
    except Exception as e:
        return False, f"environ read failed: {e}"
    try:
        cmdline = open(f"/proc/{pid}/cmdline").read().split("\0")
        # strip empty trailing token from null-terminated cmdline
        cmdline = [c for c in cmdline if c]
        # everything after the swipl `--` is what got passed into run.metta
        idx = cmdline.index("--")
        run_args = cmdline[idx + 1 :]
    except Exception as e:
        return False, f"cmdline read failed: {e}"

    auth_secret = env.get("OMEGACLAW_AUTH_SECRET", "")
    args_str = " ".join(shlex.quote(a) for a in run_args)
    # Stop existing swipl, give it a moment, then relaunch.
    subprocess.run(["pkill", "-TERM", "-f", "[s]wipl.*main.pl"], check=False)
    time.sleep(2)
    subprocess.run(["pkill", "-KILL", "-f", "[s]wipl.*main.pl"], check=False)
    time.sleep(1)
    launch = (
        "cd /home/omaclaw/PeTTa && "
        "source .venv/bin/activate && "
        f"export OMEGACLAW_AUTH_SECRET={shlex.quote(auth_secret)} && "
        f"export OLLAMA_MODEL={shlex.quote(new_model)} && "
        ": > /tmp/omegaclaw.log && "
        f"nohup setsid sh run.sh {args_str} </dev/null "
        ">>/tmp/omegaclaw.log 2>&1 & disown"
    )
    try:
        subprocess.Popen(
            ["bash", "-c", launch],
            stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL, start_new_session=True,
        )
    except Exception as e:
        return False, f"launch failed: {e}"
    return True, f"swapped to {new_model}"


def git_branch():
    try:
        out = subprocess.check_output(
            ["git", "-C", os.path.dirname(os.path.abspath(__file__)),
             "rev-parse", "--abbrev-ref", "HEAD"],
            text=True, stderr=subprocess.DEVNULL,
        ).strip()
        return out
    except Exception:
        return "?"


# --- iter-rate window ---------------------------------------------------------
_iter_window = []  # [(ts, iter_count)] over last 60 s

def iter_rate_per_min():
    iters = grep_count(r"^\(---------iteration")
    now = time.time()
    _iter_window.append((now, iters))
    while _iter_window and now - _iter_window[0][0] > 60:
        _iter_window.pop(0)
    if len(_iter_window) >= 2:
        dt = _iter_window[-1][0] - _iter_window[0][0]
        di = _iter_window[-1][1] - _iter_window[0][1]
        if dt > 0:
            return int(di / dt * 60)
    return 0


# --- message extraction -------------------------------------------------------
_HUMAN_RE = re.compile(r"^\(HUMAN-MSG:\s*(.+?)\)\s*$")
# Send patterns. DOTALL so multi-paragraph replies (with embedded newlines
# inside the quoted text) are captured. Non-greedy so we stop at the next
# closing-quote-paren-paren even when the agent embeds nested parens.
_SEND_RE = re.compile(r'\(send\s+\(text\s+"(.*?)"\)\)', re.DOTALL)
_SEND_POSITIONAL_RE = re.compile(r'\(send\s+"(.*?)"\)', re.DOTALL)


def recent_messages(limit=200):
    """Walk the tail of the log and pull out recent human/agent messages in order.

       Reads the last ~5 MB as a single blob (so multi-paragraph replies that
       span several lines stay matchable). Each MeTTa iteration writes a
       ~40 KB CHARS_SENT block, so 5 MB covers roughly 100+ turns of history."""
    msgs = []
    try:
        with open(LOG_PATH, "r", errors="replace") as f:
            f.seek(0, os.SEEK_END)
            size = f.tell()
            f.seek(max(0, size - 5_000_000))
            blob = f.read()
        # Walk in order, interleaving HUMAN-MSG and send matches so chronology stays right
        events = []
        for m in re.finditer(r"^\(HUMAN-MSG:\s*(.+?)\)\s*$", blob, re.MULTILINE):
            inner = m.group(1).strip()
            inner = re.sub(r"^[A-Za-z0-9_-]+:\s*", "", inner)
            if inner:
                events.append((m.start(), "you", inner))
        for m in _SEND_RE.finditer(blob):
            text = m.group(1)
            if text and text != "[ERROR_FEEDBACK]":
                events.append((m.start(), "oma", text))
        for m in _SEND_POSITIONAL_RE.finditer(blob):
            text = m.group(1)
            if text and text != "[ERROR_FEEDBACK]":
                events.append((m.start(), "oma", text))
        events.sort(key=lambda e: e[0])
        for _pos, who, text in events:
            msgs.append({"who": who, "text": text})
    except Exception:
        pass
    # Dedup adjacent identical messages — paraphrase dedup happens at the channel layer
    cleaned = []
    for m in msgs:
        if not cleaned or cleaned[-1] != m:
            cleaned.append(m)
    return cleaned[-limit:]


# --- HTTP handler -------------------------------------------------------------
class Handler(http.server.BaseHTTPRequestHandler):
    # Quiet logs
    def log_message(self, *_a, **_kw):
        return

    def _json(self, obj, status=200):
        body = json.dumps(obj).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        path = urlparse(self.path).path
        if path == "/":
            body = INDEX_HTML.encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Cache-Control", "no-cache, no-store, must-revalidate")
            self.send_header("Pragma", "no-cache")
            self.send_header("Expires", "0")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return
        if path == "/stats":
            pid, cmd = find_swipl()
            ollama = ollama_state()
            loaded = ollama["loaded"][0] if ollama["loaded"] else None
            return self._json({
                "running": pid is not None,
                "pid": pid,
                "model": loaded["name"] if loaded else "?",
                "vram_mb": loaded["vram_mb"] if loaded else 0,
                "available_models": ollama["available"],
                "iter_total": grep_count(r"^\(---------iteration"),
                "iter_per_min": iter_rate_per_min(),
                "ollama_calls": grep_count(r"11434/api/chat"),
                "human_msgs": grep_count(r"^\(HUMAN-MSG"),
                "sends": grep_count(r"RESPONSE: \(\(send"),
                "rss_mb": proc_rss_mb(pid) if pid else 0,
                "uptime": fmt_uptime(proc_uptime_seconds(pid)) if pid else "—",
                "channel": "local" if "commchannel=local" in cmd
                           else ("telegram" if "commchannel=telegram" in cmd
                           else ("irc" if "commchannel=irc" in cmd else "?")),
                "git_branch": git_branch(),
                "git_commit": git_version(),
                "tps": get_tps(),
            })
        if path == "/messages":
            return self._json({"messages": recent_messages()})
        if path == "/history":
            # Full transcript — no 5MB tail cap. Pages of 100 most recent
            # by default. Optional ?offset=N&limit=N.
            qs = dict(p.split("=", 1) for p in (urlparse(self.path).query or "").split("&") if "=" in p)
            try:
                limit = int(qs.get("limit", "200"))
                offset = int(qs.get("offset", "0"))
            except ValueError:
                limit, offset = 200, 0
            limit = min(max(limit, 1), 1000)
            all_msgs = full_history()
            total = len(all_msgs)
            # offset counts back from the end; offset=0 means "latest page"
            end = total - offset
            start = max(0, end - limit)
            return self._json({"total": total, "offset": offset, "limit": limit,
                               "messages": all_msgs[start:end]})
        if path == "/channels":
            return self._json(channels_status())
        if path == "/settings":
            return self._json(settings_view())
        self.send_error(404)

    def do_POST(self):
        path = urlparse(self.path).path
        n = int(self.headers.get("Content-Length", "0") or 0)
        try:
            body = json.loads(self.rfile.read(n)) if n else {}
        except Exception:
            return self._json({"ok": False, "err": "bad json"}, 400)

        if path == "/send":
            text = (body.get("text") or "").strip()
            if not text:
                return self._json({"ok": False, "err": "empty"}, 400)
            try:
                with open(IN_FIFO, "w") as f:
                    f.write(text + "\n")
                return self._json({"ok": True})
            except OSError as e:
                return self._json({"ok": False, "err": f"fifo write failed: {e}"}, 503)

        if path == "/switch":
            target = (body.get("model") or "").strip()
            if not target:
                return self._json({"ok": False, "err": "no model"}, 400)
            avail = ollama_state().get("available", [])
            if target not in avail:
                return self._json({"ok": False, "err": f"unknown model {target}"}, 400)
            ok, msg = relaunch_swipl(target)
            return self._json({"ok": ok, "msg": msg}, 200 if ok else 500)

        if path == "/reset":
            # Level-1 reset: kill + relaunch swipl with the SAME model.
            # Wipes in-process MeTTa state (&prevmsg, &lastsend, &loops, etc.)
            # and per-channel state (auth set, recent-sends dedup) without
            # touching history.metta or chroma_db (long-term memory preserved).
            state = ollama_state()
            current_model = state["loaded"][0]["name"] if state["loaded"] else \
                            os.environ.get("OLLAMA_MODEL", "")
            if not current_model:
                return self._json({"ok": False, "err": "no current model detected"}, 500)
            ok, msg = relaunch_swipl(current_model)
            return self._json({"ok": ok, "msg": "in-process state cleared · " + (msg or "")}, 200 if ok else 500)

        return self.send_error(404)


# --- single-page HTML --------------------------------------------------------
INDEX_HTML = """<!DOCTYPE html>
<html lang="en"><head>
<meta charset="utf-8">
<title>Oma · live</title>
<style>
  :root {
    --bg: #0d1117; --fg: #c9d1d9; --dim: #6e7681; --accent: #79c0ff;
    --you: #7ee787; --oma: #ffa657; --warn: #ff7b72; --card: #161b22;
    --border: #30363d;
    /* SingularityNET-inspired accents — deep teal + magenta, the colors
       most associated with their decentralized-AGI brand presentations */
    --snet-teal: #16d4d4; --snet-magenta: #d946ef; --snet-deep: #1a0b2e;
  }
  *,*:before,*:after { box-sizing: border-box; }
  body { margin:0; font-family: ui-monospace, SFMono-Regular, Menlo, monospace;
         background: var(--bg); color: var(--fg); font-size: 13px;
         display: flex; flex-direction: column; height: 100vh; }
  .body-row { display: flex; flex: 1; min-height: 0; }
  nav.sidebar { width: 160px; background: var(--card); border-right: 1px solid var(--border);
                flex-shrink: 0; padding: 12px 0; }
  nav.sidebar a { display: block; padding: 8px 16px; color: var(--dim);
                  text-decoration: none; font-size: 12px; cursor: pointer;
                  border-left: 2px solid transparent; }
  nav.sidebar a:hover { color: var(--fg); }
  nav.sidebar a.active { color: var(--snet-teal); border-left-color: var(--snet-teal);
                         background: rgba(22,212,212,0.06); }
  nav.sidebar .nav-section { color: var(--dim); font-size: 9px; text-transform: uppercase;
                             letter-spacing: 0.6px; padding: 12px 16px 4px; }
  .main { flex: 1; min-width: 0; display: flex; flex-direction: column; }
  .page { flex: 1; min-height: 0; display: none; flex-direction: column; }
  .page.active { display: flex; }
  .page-content { padding: 16px; overflow-y: auto; flex: 1; min-height: 0; }
  .section { background: var(--card); border: 1px solid var(--border);
             border-radius: 6px; padding: 14px 18px; margin-bottom: 12px; }
  .section h2 { margin: 0 0 10px; font-size: 13px; color: var(--snet-teal);
                font-weight: 600; letter-spacing: 0.3px; }
  .row { display: flex; padding: 4px 0; font-size: 12px; }
  .row .k { color: var(--dim); width: 160px; flex-shrink: 0; }
  .row .v { color: var(--fg); word-break: break-all; flex: 1; }
  .badge { display: inline-block; padding: 1px 6px; border-radius: 8px;
           font-size: 10px; font-weight: 600; margin-left: 6px; }
  .badge.on { background: var(--snet-teal); color: var(--snet-deep); }
  .badge.off { background: transparent; color: var(--dim); border: 1px solid var(--dim); }
  .history-msg { padding: 6px 10px; margin: 3px 0; border-radius: 4px;
                 border-left: 3px solid var(--dim); white-space: pre-wrap; font-size: 12px; }
  .history-msg.you { border-left-color: var(--you); }
  .history-msg.you .who { color: var(--you); font-weight: 600; margin-right: 8px; }
  .history-msg.oma { border-left-color: var(--oma); }
  .history-msg.oma .who { color: var(--oma); font-weight: 600; margin-right: 8px; }
  .pager { display: flex; gap: 8px; align-items: center; padding: 8px 0;
           color: var(--dim); font-size: 11px; }
  .pager button { font-size: 11px; padding: 3px 10px; }
  header { padding: 10px 16px; border-bottom: 1px solid var(--border);
           background: linear-gradient(90deg, var(--snet-deep) 0%, var(--bg) 60%);
           display:flex; justify-content:space-between; align-items:center; gap:16px;
           flex-shrink: 0; }
  .brand { display: flex; align-items: center; gap: 12px; }
  .brand-svg { width: 30px; height: 30px; flex-shrink: 0; }
  .brand-text h1 { margin:0; font-size:14px; font-weight:600; color: var(--accent); }
  .brand-text .sub { color: var(--snet-teal); font-size:10px; margin-top:2px;
                     letter-spacing: 0.3px; opacity: 0.85; }
  header .ver { color: var(--dim); font-size:11px; text-align: right; }
  .grid { display:grid; grid-template-columns: repeat(6, 1fr); gap:8px;
          padding:12px 16px; flex-shrink: 0; }
  .tile { background: var(--card); border:1px solid var(--border);
          border-radius:6px; padding:10px 12px; }
  .tile .label { color: var(--dim); font-size:10px; text-transform: uppercase;
                 letter-spacing:0.5px; }
  .tile .value { font-size:16px; font-weight:600; margin-top:4px;
                 word-break: break-all; }
  /* Hero tps card — the big visible number on the dashboard */
  .hero { padding: 16px 16px 0 16px; flex-shrink: 0; }
  .hero-card { background: linear-gradient(135deg, var(--snet-deep) 0%, var(--card) 100%);
               border: 1px solid var(--border); border-radius: 8px;
               padding: 18px 24px; display: flex; align-items: center;
               justify-content: space-between; gap: 24px; }
  .hero-num { display: flex; align-items: baseline; gap: 12px; }
  .hero-num .n { font-size: 56px; font-weight: 700; line-height: 1;
                 background: linear-gradient(135deg, var(--snet-teal) 0%, var(--snet-magenta) 100%);
                 -webkit-background-clip: text; -webkit-text-fill-color: transparent;
                 background-clip: text; }
  .hero-num .units { font-size: 18px; color: var(--dim); font-weight: 500; }
  .hero-meta { text-align: right; color: var(--dim); font-size: 11px;
               line-height: 1.6; }
  .hero-meta .lbl { color: var(--dim); }
  .hero-meta .val { color: var(--fg); font-weight: 600; }
  .hero-meta .stale { color: var(--warn); }
  .messages { padding: 8px 16px 16px;
              overflow-y: auto; flex: 1; min-height: 0; }
  .msg { padding: 6px 10px; margin: 4px 0; border-radius:4px;
         border-left: 3px solid var(--dim); white-space: pre-wrap; }
  .msg.you { border-left-color: var(--you); }
  .msg.you .who { color: var(--you); }
  .msg.oma { border-left-color: var(--oma); }
  .msg.oma .who { color: var(--oma); }
  .who { font-weight:600; margin-right:8px; }
  .input-bar { padding: 12px 16px; border-top: 1px solid var(--border);
               display:flex; gap:8px; flex-shrink: 0; }
  input[type=text] { flex:1; background: var(--card); color: var(--fg);
                     border:1px solid var(--border); border-radius:4px;
                     padding:8px 10px; font-family: inherit; font-size:13px; }
  button { background: var(--accent); color: var(--bg); border:0;
           border-radius:4px; padding:8px 16px; font-family: inherit;
           font-weight:600; cursor:pointer; }
  button:disabled { opacity: 0.4; cursor:not-allowed; }
  .down { color: var(--warn) !important; }
  select { background: var(--card); color: var(--accent); border: 1px solid var(--border);
           border-radius:4px; padding: 4px 8px; font-family: inherit;
           font-size: 14px; font-weight: 600; }
  button.reset { background: transparent; color: var(--snet-teal);
                 border: 1px solid var(--snet-teal); border-radius: 12px;
                 padding: 2px 10px; font-size: 11px; font-weight: 500;
                 margin-left: 6px; cursor: pointer; }
  button.reset:hover { background: var(--snet-teal); color: var(--snet-deep); }
  button.reset:disabled { opacity: 0.4; cursor: not-allowed; }
  footer { padding: 8px 16px; font-size: 10px; color: var(--dim);
           border-top: 1px solid var(--border); display: flex;
           justify-content: space-between; align-items: center;
           flex-shrink: 0; }
  footer a { color: var(--snet-teal); text-decoration: none; }
  footer a:hover { color: var(--snet-magenta); text-decoration: underline; }
  .scroll-hint { position: fixed; bottom: 80px; right: 24px;
                 background: var(--card); border: 1px solid var(--border);
                 border-radius: 16px; padding: 4px 10px; font-size: 11px;
                 color: var(--snet-teal); cursor: pointer; opacity: 0;
                 transition: opacity 0.2s; pointer-events: none; }
  .scroll-hint.show { opacity: 1; pointer-events: auto; }
</style>
</head><body>
<header>
  <div class="brand">
    <!-- A small SVG nod: three interconnected nodes evoking decentralized AGI,
         the SingularityNET / OpenCog Hyperon visual concept of
         distributed-intelligence-as-network. Teal + magenta gradient. -->
    <svg class="brand-svg" viewBox="0 0 60 60" xmlns="http://www.w3.org/2000/svg">
      <defs>
        <linearGradient id="g1" x1="0" y1="0" x2="1" y2="1">
          <stop offset="0%" stop-color="#16d4d4"/>
          <stop offset="100%" stop-color="#d946ef"/>
        </linearGradient>
      </defs>
      <line x1="30" y1="14" x2="14" y2="44" stroke="url(#g1)" stroke-width="1.5" opacity="0.6"/>
      <line x1="30" y1="14" x2="46" y2="44" stroke="url(#g1)" stroke-width="1.5" opacity="0.6"/>
      <line x1="14" y1="44" x2="46" y2="44" stroke="url(#g1)" stroke-width="1.5" opacity="0.6"/>
      <circle cx="30" cy="14" r="6" fill="url(#g1)"/>
      <circle cx="14" cy="44" r="6" fill="url(#g1)"/>
      <circle cx="46" cy="44" r="6" fill="url(#g1)"/>
    </svg>
    <div class="brand-text">
      <h1>Oma · <select id="model_select" title="Switch model (kills + relaunches Oma)"></select>
        <button id="reset_btn" class="reset" title="Wipe in-process state (keeps long-term memory). Useful after model switches.">↻ new</button>
      </h1>
      <div class="sub">An OmegaClaw agent · OpenCog Hyperon roadmap · SingularityNET</div>
    </div>
  </div>
  <div class="ver"><span id="branch">?</span> @ <span id="commit">?</span></div>
</header>

<div class="body-row">
  <nav class="sidebar">
    <div class="nav-section">Pages</div>
    <a class="nav-link active" data-page="chat">Current chat</a>
    <a class="nav-link" data-page="history">History</a>
    <a class="nav-link" data-page="channels">Channels</a>
    <a class="nav-link" data-page="settings">Settings</a>
  </nav>

  <div class="main">

    <!-- ============ Page: Current chat ============ -->
    <div class="page active" id="page-chat">
      <div class="hero">
        <div class="hero-card">
          <div class="hero-num">
            <span class="n" id="tps_value">—</span>
            <span class="units">tokens / second</span>
          </div>
          <div class="hero-meta">
            <div><span class="lbl">model</span> · <span class="val" id="tps_model">—</span></div>
            <div><span class="lbl">measured</span> · <span class="val" id="tps_age">—</span></div>
            <div><span class="lbl">probe</span> · <span class="val">10 tokens · cached 30 s</span></div>
          </div>
        </div>
      </div>

      <div class="grid">
        <div class="tile"><div class="label">Channel</div><div class="value" id="channel">…</div></div>
        <div class="tile"><div class="label">Status</div><div class="value" id="status">…</div></div>
        <div class="tile"><div class="label">Iter / min</div><div class="value" id="iter_rate">…</div></div>
        <div class="tile"><div class="label">Sends</div><div class="value" id="sends">…</div></div>
        <div class="tile"><div class="label">RSS</div><div class="value" id="rss">…</div></div>
        <div class="tile"><div class="label">VRAM</div><div class="value" id="vram">…</div></div>
      </div>

      <div class="messages" id="messages"></div>
      <div class="scroll-hint" id="scrollhint">↓ new messages</div>

      <div class="input-bar">
        <input type="text" id="input" placeholder="Type a message and press Enter…" autofocus>
        <button id="sendbtn">Send</button>
      </div>
    </div>

    <!-- ============ Page: History ============ -->
    <div class="page" id="page-history">
      <div class="page-content">
        <div class="section">
          <h2>Full transcript history</h2>
          <div class="pager">
            <button id="hist_newer">← newer</button>
            <button id="hist_older">older →</button>
            <span id="hist_meta">—</span>
          </div>
          <div id="hist_list"></div>
        </div>
      </div>
    </div>

    <!-- ============ Page: Channels ============ -->
    <div class="page" id="page-channels">
      <div class="page-content">
        <div class="section">
          <h2>Connected channels</h2>
          <div id="channels_list">loading…</div>
        </div>
      </div>
    </div>

    <!-- ============ Page: Settings ============ -->
    <div class="page" id="page-settings">
      <div class="page-content">
        <div class="section">
          <h2>Runtime</h2>
          <div id="settings_runtime"></div>
        </div>
        <div class="section">
          <h2>Paths &amp; sizes</h2>
          <div id="settings_paths"></div>
        </div>
        <div class="section">
          <h2>models.yaml</h2>
          <div id="settings_models"></div>
        </div>
        <div class="section">
          <h2>Environment</h2>
          <div id="settings_env"></div>
        </div>
      </div>
    </div>

  </div>
</div>

<footer>
  <span>OmegaClaw-Core · forked from <a href="https://github.com/patham9/mettaclaw" target="_blank">patham9/mettaclaw</a></span>
  <span>Built for <a href="https://singularitynet.io" target="_blank">SingularityNET</a> · <a href="https://github.com/asi-alliance/OmegaClaw-Core" target="_blank">asi-alliance/OmegaClaw-Core</a></span>
</footer>

<script>
const $ = id => document.getElementById(id);

let _availSeen = '';
async function fetchStats() {
  try {
    const r = await fetch('/stats'); const d = await r.json();
    // Populate model dropdown from /api/tags (only rebuild when list changes)
    const sel = $('model_select');
    const avail = (d.available_models || []);
    const availKey = avail.join(',');
    if (availKey !== _availSeen) {
      _availSeen = availKey;
      sel.innerHTML = avail.map(m =>
        `<option value="${m}"${m === d.model ? ' selected' : ''}>${m}</option>`
      ).join('');
    } else if (sel.value !== d.model && !sel.dataset.userSwitching) {
      // Sync selection if active model changed externally
      sel.value = d.model;
    }
    $('channel').textContent = d.channel;
    $('status').textContent = d.running ? `pid ${d.pid} · up ${d.uptime}` : 'NOT RUNNING';
    $('status').className = 'value' + (d.running ? '' : ' down');
    $('iter_rate').textContent = `${d.iter_per_min}  (${d.iter_total} total)`;
    $('sends').textContent = d.sends;
    $('rss').textContent = d.rss_mb ? `${d.rss_mb} MB` : '—';
    $('vram').textContent = d.vram_mb ? `${(d.vram_mb/1024).toFixed(1)} GB` : '—';
    $('branch').textContent = d.git_branch;
    $('commit').textContent = d.git_commit;
    // Hero tps tile — show "—" instead of "0" when a probe returned no
    // measurable tokens (typically: timeout or thinking-mode burned the budget)
    const t = d.tps || {};
    if (t.tps && t.tps > 0) {
      $('tps_value').textContent = t.tps.toFixed(1);
    } else {
      $('tps_value').textContent = t.ts ? '—' : '…';
    }
    $('tps_model').textContent = t.model || '—';
    if (t.ts) {
      const age = Math.max(0, Math.floor(Date.now()/1000 - t.ts));
      $('tps_age').textContent = age < 60 ? `${age} s ago` : `${Math.floor(age/60)} m ago`;
      $('tps_age').className = age > 90 ? 'val stale' : 'val';
    } else {
      $('tps_age').textContent = 'measuring…';
      $('tps_age').className = 'val';
    }
  } catch (e) { /* offline; ignore */ }
}

$('reset_btn').addEventListener('click', async () => {
  const ok = confirm("Reset Oma's in-process memory? Clears short-term loop state and channel buffers; keeps history + chroma_db. Useful after a model switch.");
  if (!ok) return;
  const btn = $('reset_btn');
  btn.disabled = true; btn.textContent = '↻ resetting…';
  try {
    const r = await fetch('/reset', {method:'POST', headers:{'Content-Type':'application/json'}, body:'{}'});
    const d = await r.json();
    if (!d.ok) alert('Reset failed: ' + (d.err || d.msg));
    // Clear the on-screen message dedup so we re-render new conversation cleanly
    _seenKeys.clear();
    $('messages').innerHTML = '';
  } catch (e) { alert('Reset error: ' + e); }
  finally {
    setTimeout(() => { btn.disabled = false; btn.textContent = '↻ new'; }, 8000);
  }
});

$('model_select').addEventListener('change', async (e) => {
  const target = e.target.value;
  const ok = confirm(`Swap Oma to "${target}"? This kills swipl and relaunches; in-flight conversation will reset.`);
  if (!ok) {
    // revert UI selection on cancel
    fetchStats();
    return;
  }
  e.target.dataset.userSwitching = '1';
  e.target.disabled = true;
  try {
    const r = await fetch('/switch', {method:'POST', headers:{'Content-Type':'application/json'},
                                      body: JSON.stringify({model: target})});
    const d = await r.json();
    if (!d.ok) alert('Switch failed: ' + (d.err || d.msg || 'unknown'));
  } catch (err) {
    alert('Switch error: ' + err);
  } finally {
    setTimeout(() => {
      e.target.disabled = false;
      delete e.target.dataset.userSwitching;
      fetchStats();
    }, 8000);
  }
});

// Append-only message rendering. We never wipe the chat; new messages
// from /messages are diffed against what's already on screen and appended.
// This preserves scroll position and lets you scroll back through history
// without it getting yanked out from under you on each 1.5 s poll.
const _seenKeys = new Set();
function _msgKey(x) { return x.who + '\x1f' + x.text; }

async function fetchMessages() {
  try {
    const r = await fetch('/messages'); const d = await r.json();
    if (!d.messages || d.messages.length === 0) return;
    const m = $('messages');
    const wasNearBottom = (m.scrollHeight - m.scrollTop - m.clientHeight) < 80;
    let appended = 0;
    for (const x of d.messages) {
      const key = _msgKey(x);
      if (_seenKeys.has(key)) continue;
      _seenKeys.add(key);
      const div = document.createElement('div');
      div.className = 'msg ' + x.who;
      div.innerHTML = `<span class="who">${x.who === 'you' ? 'You' : 'Oma'}</span>${escapeHtml(x.text)}`;
      m.appendChild(div);
      appended++;
    }
    if (appended === 0) return;
    if (wasNearBottom) {
      m.scrollTop = m.scrollHeight;
      $('scrollhint').classList.remove('show');
    } else {
      // User has scrolled up to read history — show a hint they can click
      // to jump back to live.
      $('scrollhint').classList.add('show');
    }
  } catch (e) { /* ignore */ }
}

// Detach scroll-hint click → jump to bottom
document.addEventListener('DOMContentLoaded', () => {
  const hint = document.getElementById('scrollhint');
  if (hint) hint.addEventListener('click', () => {
    const m = $('messages');
    m.scrollTop = m.scrollHeight;
    hint.classList.remove('show');
  });
});

// When the user scrolls back near the bottom, hide the hint
document.addEventListener('scroll', () => {
  const m = $('messages');
  if ((m.scrollHeight - m.scrollTop - m.clientHeight) < 80) {
    $('scrollhint').classList.remove('show');
  }
}, true);

function escapeHtml(s) {
  return (s || '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
}

function _appendOptimistic(who, text) {
  // Render a message immediately without waiting for the log round-trip.
  // The /messages poll will dedup if the same content shows up later.
  const key = _msgKey({who, text});
  if (_seenKeys.has(key)) return;
  _seenKeys.add(key);
  const m = $('messages');
  const div = document.createElement('div');
  div.className = 'msg ' + who;
  div.innerHTML = `<span class="who">${who === 'you' ? 'You' : 'Oma'}</span>${escapeHtml(text)}`;
  m.appendChild(div);
  m.scrollTop = m.scrollHeight;
}

async function send() {
  const i = $('input'); const text = i.value.trim();
  if (!text) return;
  // Client-side slash commands — intercept BEFORE sending to Oma
  if (text === '/new' || text === '/reset') {
    i.value = '';
    $('reset_btn').click();
    return;
  }
  if (text === '/clear') {
    i.value = '';
    _seenKeys.clear();
    $('messages').innerHTML = '';
    return;
  }
  $('sendbtn').disabled = true;
  // Optimistically echo the user's line immediately
  _appendOptimistic('you', text);
  i.value = '';
  try {
    const r = await fetch('/send', {method:'POST', headers:{'Content-Type':'application/json'},
                                    body: JSON.stringify({text})});
    const d = await r.json();
    if (!d.ok) alert('send failed: ' + d.err);
    setTimeout(fetchMessages, 250);
  } catch (e) { alert('send error: ' + e); }
  finally { $('sendbtn').disabled = false; i.focus(); }
}

$('sendbtn').addEventListener('click', send);
$('input').addEventListener('keydown', e => { if (e.key === 'Enter') send(); });

// ============ Sidebar / page switching ============
function showPage(name) {
  document.querySelectorAll('.page').forEach(p => p.classList.remove('active'));
  document.querySelectorAll('.nav-link').forEach(a => a.classList.remove('active'));
  const page = document.getElementById('page-' + name);
  if (page) page.classList.add('active');
  const link = document.querySelector(`.nav-link[data-page="${name}"]`);
  if (link) link.classList.add('active');
  // Lazy load page-specific data
  if (name === 'history') loadHistory();
  if (name === 'channels') loadChannels();
  if (name === 'settings') loadSettings();
}
document.querySelectorAll('.nav-link').forEach(a => {
  a.addEventListener('click', () => showPage(a.dataset.page));
});

// ============ History page ============
let _histOffset = 0;
async function loadHistory() {
  try {
    const r = await fetch(`/history?offset=${_histOffset}&limit=100`);
    const d = await r.json();
    const list = document.getElementById('hist_list');
    list.innerHTML = d.messages.map(m =>
      `<div class="history-msg ${m.who}"><span class="who">${m.who === 'you' ? 'You' : 'Oma'}</span>${escapeHtml(m.text)}</div>`
    ).join('');
    document.getElementById('hist_meta').textContent =
      `${d.messages.length} of ${d.total} messages · offset ${d.offset}`;
  } catch (e) { document.getElementById('hist_list').textContent = 'load failed: ' + e; }
}
document.getElementById('hist_older').addEventListener('click', () => {
  _histOffset += 100; loadHistory();
});
document.getElementById('hist_newer').addEventListener('click', () => {
  _histOffset = Math.max(0, _histOffset - 100); loadHistory();
});

// ============ Channels page ============
async function loadChannels() {
  try {
    const r = await fetch('/channels'); const d = await r.json();
    const html = d.channels.map(c => {
      const badge = c.active ? '<span class="badge on">ACTIVE</span>'
                  : (c.available ? '<span class="badge off">available</span>'
                                 : '<span class="badge off">disabled</span>');
      const details = c.details.map(line => `<div class="row"><span class="k">·</span><span class="v">${escapeHtml(line)}</span></div>`).join('');
      return `<div style="margin-bottom:14px"><div class="row"><span class="k" style="font-weight:600;color:var(--fg)">${c.name}</span><span class="v">${badge}</span></div>${details}</div>`;
    }).join('');
    document.getElementById('channels_list').innerHTML = html;
  } catch (e) { document.getElementById('channels_list').textContent = 'load failed: ' + e; }
}

// ============ Settings page ============
async function loadSettings() {
  try {
    const r = await fetch('/settings'); const d = await r.json();
    const rt = document.getElementById('settings_runtime');
    rt.innerHTML = [
      ['swipl pid', d.swipl_pid || '—'],
      ['swipl cmd', d.swipl_cmd || '—'],
      ['git branch', d.git_branch],
      ['git commit', d.git_commit],
      ['Ollama base URL', d.ollama_base],
    ].map(([k,v]) => `<div class="row"><span class="k">${k}</span><span class="v">${escapeHtml(String(v))}</span></div>`).join('');

    const ps = document.getElementById('settings_paths');
    ps.innerHTML = d.paths.map(p =>
      `<div class="row"><span class="k">${p.label}</span><span class="v">${escapeHtml(p.path)} <span style="color:var(--dim)">(${p.kind} · ${p.size_mb} MB)</span></span></div>`
    ).join('');

    const ms = document.getElementById('settings_models');
    ms.innerHTML = d.model_formats.map(m =>
      `<div class="row"><span class="k">${escapeHtml(m.name)}</span><span class="v">${m.format}</span></div>`
    ).join('') || '<div class="row"><span class="v" style="color:var(--dim)">no models.yaml entries</span></div>';

    const ev = document.getElementById('settings_env');
    ev.innerHTML = Object.entries(d.env).map(([k,v]) =>
      `<div class="row"><span class="k">${k}</span><span class="v">${escapeHtml(v || '(empty)')}</span></div>`
    ).join('') || '<div class="row"><span class="v" style="color:var(--dim)">no env vars captured</span></div>';
  } catch (e) {
    document.getElementById('settings_runtime').textContent = 'load failed: ' + e;
  }
}

fetchStats(); fetchMessages();
setInterval(fetchStats, 2000);
setInterval(fetchMessages, 1500);
</script>
</body></html>
"""


class _ReusableServer(socketserver.TCPServer):
    allow_reuse_address = True
    daemon_threads = True


def main():
    # Background tps prober — non-blocking, refreshes every ~30s
    threading.Thread(target=_tps_refresh_worker, daemon=True).start()
    with _ReusableServer(("127.0.0.1", PORT), Handler) as httpd:
        print(f"Oma webui on http://127.0.0.1:{PORT}")
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            print("\nstopping")


if __name__ == "__main__":
    main()
