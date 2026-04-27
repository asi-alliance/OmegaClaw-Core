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
import sys
import threading
import time
import urllib.request
from urllib.parse import urlparse

PORT = 22333  # RAW nod: 23 enigma + 33 (apple of discord). The fnord is a feature.
LOG_PATH = "/tmp/omegaclaw.log"
IN_FIFO = "/tmp/oma-in"
REPO_ROOT = os.path.dirname(os.path.abspath(__file__))


def load_local_env():
    """Load repo-local secrets/config without committing them.

    Values already present in the process environment win, so shell/systemd
    config can override .env.local cleanly.
    """
    path = os.path.join(REPO_ROOT, ".env.local")
    if not os.path.exists(path):
        return
    try:
        with open(path) as f:
            for raw in f:
                line = raw.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                key, value = line.split("=", 1)
                key = key.strip()
                value = value.strip().strip('"').strip("'")
                if key and key not in os.environ:
                    os.environ[key] = value
    except Exception as e:
        print(f"[webui] warning: could not load .env.local: {e}")


load_local_env()
OLLAMA_BASE = os.environ.get("OLLAMA_BASE_URL", "http://192.168.86.22:11434")
SRC_DIR = os.path.join(REPO_ROOT, "src")
if SRC_DIR not in sys.path:
    sys.path.insert(0, SRC_DIR)
import risk_register

# --- caching -----------------------------------------------------------------
_ollama_cache = {"ts": 0, "data": {}}
_OLLAMA_CACHE_TTL = 5.0
_openai_models_cache = {"ts": 0, "models": [], "err": ""}
_OPENAI_MODELS_CACHE_TTL = 300.0
_anthropic_models_cache = {"ts": 0, "models": [], "err": ""}
_ANTHROPIC_MODELS_CACHE_TTL = 300.0
_deepseek_models_cache = {"ts": 0, "models": [], "err": ""}
_DEEPSEEK_MODELS_CACHE_TTL = 300.0

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


def _cmd_arg_value(cmd, key):
    m = re.search(r"(?:^|\s)" + re.escape(key) + r"=([^\s]+)", cmd or "")
    return m.group(1) if m else ""


def active_provider_model():
    pid, cmd = find_swipl()
    provider = _cmd_arg_value(cmd, "provider") or "Ollama"
    llm = _cmd_arg_value(cmd, "LLM")
    env = {}
    if pid:
        try:
            env = dict(
                p.split("=", 1)
                for p in open(f"/proc/{pid}/environ").read().split("\0")
                if "=" in p
            )
        except Exception:
            env = {}
    if provider == "OpenAI":
        model = llm or env.get("OPENAI_MODEL") or os.environ.get("OPENAI_MODEL", "gpt-5.5")
    elif provider == "Ollama":
        state = ollama_state()
        model = env.get("OLLAMA_MODEL") or (
            state["loaded"][0]["name"] if state.get("loaded") else ""
        )
    elif provider == "Anthropic":
        model = llm or env.get("ANTHROPIC_MODEL") or os.environ.get("ANTHROPIC_MODEL", "claude-opus-4-6")
    elif provider == "DeepSeek":
        model = llm or env.get("DEEPSEEK_MODEL") or os.environ.get("DEEPSEEK_MODEL", "deepseek-v4-pro")
    else:
        model = llm or ""
    return {"provider": provider, "model": model, "route": f"{provider.lower()}:{model}" if model else ""}


def _is_openai_text_model(model_id):
    mid = (model_id or "").lower()
    if not mid.startswith(("gpt-", "chatgpt-", "o1", "o3", "o4")):
        return False
    excluded = (
        "audio", "realtime", "image", "embedding", "moderation", "transcribe",
        "tts", "whisper", "sora", "dall-e", "computer-use", "search-preview",
    )
    return not any(x in mid for x in excluded)


def _openai_sort_key(model_id):
    mid = model_id.lower()
    family_rank = 0 if mid.startswith("gpt-5") else 1 if mid.startswith("gpt-4") else 2
    size_rank = 2 if "nano" in mid or "mini" in mid else 0
    return (family_rank, size_rank, mid)


def openai_model_ids():
    load_local_env()
    if not os.environ.get("OPENAI_API_KEY"):
        return [], ""
    now = time.time()
    if now - _openai_models_cache["ts"] < _OPENAI_MODELS_CACHE_TTL:
        return list(_openai_models_cache["models"]), _openai_models_cache["err"]
    try:
        req = urllib.request.Request(
            "https://api.openai.com/v1/models",
            headers={"Authorization": f"Bearer {os.environ['OPENAI_API_KEY']}"},
        )
        with urllib.request.urlopen(req, timeout=10) as r:
            data = json.load(r)
        ids = sorted(
            {m.get("id", "") for m in data.get("data", []) if _is_openai_text_model(m.get("id", ""))},
            key=_openai_sort_key,
        )
        _openai_models_cache.update({"ts": now, "models": ids, "err": ""})
    except Exception as e:
        _openai_models_cache.update({"ts": now, "models": [], "err": f"OpenAI model list failed: {e}"})
    return list(_openai_models_cache["models"]), _openai_models_cache["err"]


def _anthropic_sort_key(model_id):
    mid = model_id.lower()
    family_rank = 0 if "opus" in mid else 1 if "sonnet" in mid else 2 if "haiku" in mid else 3
    return (family_rank, mid)


def anthropic_model_ids():
    load_local_env()
    if not os.environ.get("ANTHROPIC_API_KEY"):
        return [], ""
    now = time.time()
    if now - _anthropic_models_cache["ts"] < _ANTHROPIC_MODELS_CACHE_TTL:
        return list(_anthropic_models_cache["models"]), _anthropic_models_cache["err"]
    try:
        req = urllib.request.Request(
            "https://api.anthropic.com/v1/models",
            headers={
                "x-api-key": os.environ["ANTHROPIC_API_KEY"],
                "anthropic-version": os.environ.get("ANTHROPIC_VERSION", "2023-06-01"),
            },
        )
        with urllib.request.urlopen(req, timeout=10) as r:
            data = json.load(r)
        ids = sorted(
            {m.get("id", "") for m in data.get("data", []) if str(m.get("id", "")).startswith("claude-")},
            key=_anthropic_sort_key,
        )
        _anthropic_models_cache.update({"ts": now, "models": ids, "err": ""})
    except Exception as e:
        fallback = [os.environ.get("ANTHROPIC_MODEL", "claude-opus-4-6")]
        _anthropic_models_cache.update({"ts": now, "models": fallback, "err": f"Anthropic model list failed: {e}"})
    return list(_anthropic_models_cache["models"]), _anthropic_models_cache["err"]


def _deepseek_sort_key(model_id):
    mid = model_id.lower()
    if mid == "deepseek-v4-pro":
        rank = 0
    elif mid == "deepseek-v4-flash":
        rank = 1
    elif mid == "deepseek-reasoner":
        rank = 2
    elif mid == "deepseek-chat":
        rank = 3
    else:
        rank = 4
    return (rank, mid)


def deepseek_model_ids():
    load_local_env()
    if not os.environ.get("DEEPSEEK_API_KEY"):
        return [], ""
    now = time.time()
    if now - _deepseek_models_cache["ts"] < _DEEPSEEK_MODELS_CACHE_TTL:
        return list(_deepseek_models_cache["models"]), _deepseek_models_cache["err"]
    fallback = ["deepseek-v4-pro", "deepseek-v4-flash", "deepseek-reasoner", "deepseek-chat"]
    try:
        base_url = os.environ.get("DEEPSEEK_BASE_URL", "https://api.deepseek.com").rstrip("/")
        req = urllib.request.Request(
            f"{base_url}/models",
            headers={"Authorization": f"Bearer {os.environ['DEEPSEEK_API_KEY']}"},
        )
        with urllib.request.urlopen(req, timeout=10) as r:
            data = json.load(r)
        ids = sorted(
            {m.get("id", "") for m in data.get("data", []) if str(m.get("id", "")).startswith("deepseek-")},
            key=_deepseek_sort_key,
        )
        if not ids:
            ids = fallback
        _deepseek_models_cache.update({"ts": now, "models": ids, "err": ""})
    except Exception:
        _deepseek_models_cache.update({"ts": now, "models": fallback, "err": ""})
    return list(_deepseek_models_cache["models"]), _deepseek_models_cache["err"]


def model_routes():
    load_local_env()
    state = ollama_state()
    routes = []
    for name in state.get("available", []):
        routes.append({
            "id": f"ollama:{name}",
            "label": f"Local · {name}",
            "provider": "Ollama",
            "model": name,
            "available": True,
        })
    openai_key_set = bool(os.environ.get("OPENAI_API_KEY"))
    openai_model = os.environ.get("OPENAI_MODEL", "gpt-5.5")
    openai_label = os.environ.get("OPENAI_DISPLAY_NAME", "ChatGPT 5.5")
    openai_models, openai_err = openai_model_ids()
    if openai_model and openai_model not in openai_models:
        openai_models.insert(0, openai_model)
    for model in openai_models:
        label = f"{openai_label} · OpenAI API ({model})" if model == openai_model else f"OpenAI · {model}"
        routes.append({
            "id": f"openai:{model}",
            "label": label,
            "provider": "OpenAI",
            "model": model,
            "available": openai_key_set and not openai_err,
            "reason": "" if openai_key_set and not openai_err
                      else (openai_err or "set OPENAI_API_KEY in .env.local"),
        })
    anthropic_key_set = bool(os.environ.get("ANTHROPIC_API_KEY"))
    anthropic_model = os.environ.get("ANTHROPIC_MODEL", "claude-opus-4-6")
    anthropic_models, anthropic_err = anthropic_model_ids()
    if anthropic_model and anthropic_model not in anthropic_models:
        anthropic_models.insert(0, anthropic_model)
    for model in anthropic_models:
        label = f"Claude · {model}"
        routes.append({
            "id": f"anthropic:{model}",
            "label": label,
            "provider": "Anthropic",
            "model": model,
            "available": anthropic_key_set and not anthropic_err,
            "reason": "" if anthropic_key_set and not anthropic_err
                      else (anthropic_err or "set ANTHROPIC_API_KEY in .env.local"),
        })
    deepseek_key_set = bool(os.environ.get("DEEPSEEK_API_KEY"))
    deepseek_model = os.environ.get("DEEPSEEK_MODEL", "deepseek-v4-pro")
    deepseek_label = os.environ.get("DEEPSEEK_DISPLAY_NAME", "DeepSeek V4 Pro")
    deepseek_models, deepseek_err = deepseek_model_ids()
    if deepseek_model and deepseek_model not in deepseek_models:
        deepseek_models.insert(0, deepseek_model)
    for model in deepseek_models:
        label = f"{deepseek_label} · DeepSeek API ({model})" if model == deepseek_model else f"DeepSeek · {model}"
        routes.append({
            "id": f"deepseek:{model}",
            "label": label,
            "provider": "DeepSeek",
            "model": model,
            "available": deepseek_key_set and not deepseek_err,
            "reason": "" if deepseek_key_set and not deepseek_err
                      else (deepseek_err or "set DEEPSEEK_API_KEY in .env.local"),
        })
    return routes


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
        ("prompt-esther.txt", os.path.join(repo, "memory", "prompt-esther.txt")),
        ("risks.jsonl", risk_register.RISK_PATH),
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
                             "OPENAI_API_KEY", "OPENAI_MODEL", "OPENAI_DISPLAY_NAME",
                             "OPENAI_BASE_URL", "OPENAI_REASONING_EFFORT",
                             "OMEGACLAW_PROMPT_FILE", "OMEGACLAW_RISK_REGISTER",
                             "ANTHROPIC_API_KEY", "ANTHROPIC_MODEL", "ANTHROPIC_VERSION",
                             "DEEPSEEK_API_KEY", "DEEPSEEK_MODEL", "DEEPSEEK_BASE_URL",
                             "DEEPSEEK_DISPLAY_NAME", "DEEPSEEK_THINKING",
                             "DEEPSEEK_REASONING_EFFORT"):
                        if k == "OMEGACLAW_AUTH_SECRET" and v:
                            v = "(set)"
                        elif k in ("ANTHROPIC_API_KEY", "OPENAI_API_KEY", "DEEPSEEK_API_KEY") and v:
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


def _route_from_id(route_id):
    provider, sep, model = (route_id or "").partition(":")
    if not sep or not provider or not model:
        raise ValueError("route must be provider:model")
    provider = {
        "ollama": "Ollama",
        "openai": "OpenAI",
        "anthropic": "Anthropic",
        "deepseek": "DeepSeek",
    }.get(provider.lower())
    if not provider:
        raise ValueError("unsupported provider")
    return provider, model


def _set_run_arg(args, key, value):
    out = []
    replaced = False
    prefix = key + "="
    for arg in args:
        if arg.startswith(prefix):
            if value:
                out.append(prefix + value)
            replaced = True
        else:
            out.append(arg)
    if value and not replaced:
        out.append(prefix + value)
    return out


def context_budget_for_route(provider, model):
    model_l = (model or "").lower()
    if provider == "Ollama":
        if any(name in model_l for name in ("granite", "gemma", "phi4", "qwen", "deepseek", "glm", "mistral")):
            return {
                "maxHistory": "12000",
                "maxFeedback": "12000",
                "maxRecallItems": "8",
                "maxEpisodeRecallLines": "12",
            }
        return {
            "maxHistory": "16000",
            "maxFeedback": "16000",
            "maxRecallItems": "10",
            "maxEpisodeRecallLines": "12",
        }
    if provider in ("OpenAI", "Anthropic", "DeepSeek"):
        return {
            "maxHistory": "42000",
            "maxFeedback": "30000",
            "maxRecallItems": "16",
            "maxEpisodeRecallLines": "20",
        }
    return {
        "maxHistory": "24000",
        "maxFeedback": "16000",
        "maxRecallItems": "10",
        "maxEpisodeRecallLines": "12",
    }


def append_switch_marker(provider, model, budget):
    try:
        path = os.path.join(REPO_ROOT, "memory", "history.metta")
        with open(path, "a", encoding="utf-8") as f:
            f.write(
                f'("{time.strftime("%Y-%m-%d %H:%M:%S")}" MODEL_SWITCH: '
                f'provider={provider} model={model} '
                f'maxHistory={budget.get("maxHistory")} maxFeedback={budget.get("maxFeedback")})\n'
            )
    except OSError:
        pass


def relaunch_swipl(route_id):
    """Kill the running swipl Oma and relaunch with a provider/model route.
       Preserves secrets/config by reading /proc env and passing env directly
       into the child process, never via shell-expanded export commands."""
    pid, _cmd = find_swipl()
    if not pid:
        return False, "no swipl currently running"
    try:
        provider, model = _route_from_id(route_id)
    except ValueError as e:
        return False, str(e)
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

    child_env = os.environ.copy()
    for key in (
        "OMEGACLAW_AUTH_SECRET", "OMEGACLAW_PROMPT_FILE", "OMEGACLAW_RISK_REGISTER",
        "OLLAMA_BASE_URL", "OLLAMA_MODEL", "OPENAI_API_KEY", "OPENAI_MODEL",
        "OPENAI_BASE_URL", "OPENAI_REASONING_EFFORT", "ANTHROPIC_API_KEY",
        "ANTHROPIC_MODEL", "ANTHROPIC_VERSION", "DEEPSEEK_API_KEY",
        "DEEPSEEK_MODEL", "DEEPSEEK_BASE_URL", "DEEPSEEK_DISPLAY_NAME",
        "DEEPSEEK_THINKING", "DEEPSEEK_REASONING_EFFORT", "ASI_API_KEY",
    ):
        if env.get(key) and key not in child_env:
            child_env[key] = env[key]
    if provider == "Ollama":
        child_env["OLLAMA_MODEL"] = model
    elif provider == "OpenAI":
        child_env["OPENAI_MODEL"] = model
    elif provider == "Anthropic":
        child_env["ANTHROPIC_MODEL"] = model
    elif provider == "DeepSeek":
        child_env["DEEPSEEK_MODEL"] = model
    budget = context_budget_for_route(provider, model)
    run_args = _set_run_arg(run_args, "provider", provider)
    run_args = _set_run_arg(run_args, "LLM", model if provider in ("OpenAI", "Anthropic", "DeepSeek") else "")
    for key, value in budget.items():
        run_args = _set_run_arg(run_args, key, value)
    append_switch_marker(provider, model, budget)
    args_str = " ".join(shlex.quote(a) for a in run_args)
    # Stop existing swipl, give it a moment, then relaunch.
    subprocess.run(["pkill", "-TERM", "-f", "[s]wipl.*main.pl"], check=False)
    time.sleep(2)
    subprocess.run(["pkill", "-KILL", "-f", "[s]wipl.*main.pl"], check=False)
    time.sleep(1)
    launch = (
        "cd /home/omaclaw/PeTTa && "
        "source .venv/bin/activate && "
        ": > /tmp/omegaclaw.log && "
        f"nohup setsid sh run.sh {args_str} </dev/null "
        ">>/tmp/omegaclaw.log 2>&1 & disown"
    )
    try:
        subprocess.Popen(
            ["bash", "-c", launch],
            stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL, start_new_session=True, env=child_env,
        )
    except Exception as e:
        return False, f"launch failed: {e}"
    return True, f"swapped to {provider} · {model}"


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
            active = active_provider_model()
            return self._json({
                "running": pid is not None,
                "pid": pid,
                "model": active["model"] or (loaded["name"] if loaded else "?"),
                "provider": active["provider"],
                "active_route": active["route"],
                "vram_mb": loaded["vram_mb"] if loaded else 0,
                "available_models": ollama["available"],
                "model_routes": model_routes(),
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
        if path == "/risks":
            try:
                risks = json.loads(risk_register.list_risks())
                dash = json.loads(risk_register.dashboard_data())
                return self._json({"ok": True, "risks": risks.get("risks", []), "dashboard": dash})
            except Exception as e:
                return self._json({"ok": False, "err": str(e)}, 500)
        if path == "/heatmap":
            try:
                return self._json(json.loads(risk_register.dashboard_data()))
            except Exception as e:
                return self._json({"ok": False, "err": str(e)}, 500)
        if path == "/ecosystem":
            try:
                return self._json(json.loads(risk_register.ecosystem_data()))
            except Exception as e:
                return self._json({"ok": False, "err": str(e)}, 500)
        if path == "/org":
            try:
                qs = dict(p.split("=", 1) for p in (urlparse(self.path).query or "").split("&") if "=" in p)
                return self._json(json.loads(risk_register.org_data(qs.get("id", ""))))
            except Exception as e:
                return self._json({"ok": False, "err": str(e)}, 500)
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

        if path == "/risks":
            try:
                result = json.loads(risk_register.append_risk(body))
                return self._json(result, 200 if result.get("ok") else 400)
            except Exception as e:
                return self._json({"ok": False, "err": str(e)}, 500)

        if path == "/demo/seed":
            try:
                result = json.loads(risk_register.seed_demo_data())
                return self._json(result, 200 if result.get("ok") else 500)
            except Exception as e:
                return self._json({"ok": False, "err": str(e)}, 500)

        if path == "/switch":
            target = (body.get("route") or body.get("model") or "").strip()
            if not target:
                return self._json({"ok": False, "err": "no model"}, 400)
            if ":" not in target:
                target = f"ollama:{target}"
            routes = {r["id"]: r for r in model_routes()}
            if target not in routes:
                return self._json({"ok": False, "err": f"unknown model route {target}"}, 400)
            if not routes[target].get("available"):
                return self._json({"ok": False, "err": routes[target].get("reason") or "route unavailable"}, 400)
            ok, msg = relaunch_swipl(target)
            return self._json({"ok": ok, "msg": msg}, 200 if ok else 500)

        if path == "/reset":
            # Level-1 reset: kill + relaunch swipl with the SAME model.
            # Wipes in-process MeTTa state (&prevmsg, &lastsend, &loops, etc.)
            # and per-channel state (auth set, recent-sends dedup) without
            # touching history.metta or chroma_db (long-term memory preserved).
            active = active_provider_model()
            if not active["route"]:
                return self._json({"ok": False, "err": "no current model route detected"}, 500)
            ok, msg = relaunch_swipl(active["route"])
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
  .badge.low { background: #2ea043; color: #fff; }
  .badge.medium { background: #d29922; color: #0d1117; }
  .badge.high { background: #db6d28; color: #fff; }
  .badge.critical { background: var(--warn); color: #fff; }
  .risk-grid { display:grid; grid-template-columns: repeat(4, 1fr); gap:8px; margin-bottom: 12px; }
  .risk-card { border: 1px solid var(--border); border-radius: 6px; padding: 10px 12px;
               background: rgba(255,255,255,0.02); margin-bottom: 8px; }
  .risk-card .title { color: var(--fg); font-weight: 600; margin-bottom: 6px; }
  .risk-card .meta { color: var(--dim); font-size: 11px; line-height: 1.5; }
  .risk-card .desc { color: var(--fg); font-size: 12px; margin-top: 6px; white-space: pre-wrap; }
  .risk-form { display:grid; grid-template-columns: 1.5fr 0.8fr 0.8fr 1fr; gap:8px; margin-bottom: 10px; }
  .risk-form textarea { grid-column: 1 / -1; min-height: 64px; resize: vertical;
                        background: var(--card); color: var(--fg); border:1px solid var(--border);
                        border-radius:4px; padding:8px 10px; font-family: inherit; font-size:12px; }
  .heatmap { border-collapse: collapse; width: 100%; table-layout: fixed; }
  .heatmap th, .heatmap td { border: 1px solid var(--border); text-align: center;
                             padding: 10px; min-height: 42px; }
  .heatmap th { color: var(--dim); font-weight: 500; font-size: 11px; }
  .heatmap td { color: var(--fg); font-weight: 700; }
  .heat-0 { background: rgba(255,255,255,0.02); color: var(--dim) !important; }
  .heat-1 { background: rgba(46,160,67,0.35); }
  .heat-2 { background: rgba(210,153,34,0.42); }
  .heat-3 { background: rgba(219,109,40,0.48); }
  .heat-4 { background: rgba(255,123,114,0.55); }
  .viz-wrap { display:grid; grid-template-columns: 1.3fr 0.9fr; gap:12px; align-items: stretch; }
  .network-panel { min-height: 420px; border: 1px solid var(--border); border-radius: 6px;
                   background: radial-gradient(circle at 50% 50%, rgba(22,212,212,0.08), rgba(255,255,255,0.02) 48%, rgba(217,70,239,0.04));
                   padding: 14px; overflow: hidden; }
  .org-chart { display:flex; flex-direction:column; gap:10px; min-width: 0; }
  .command-row { border:1px solid rgba(22,212,212,0.45); border-radius:6px;
                 background: linear-gradient(135deg, rgba(22,212,212,0.11), rgba(217,70,239,0.07));
                 padding:10px; }
  .nexi-head { display:flex; align-items:center; gap:10px; margin-bottom:8px; }
  .nexi-mark { width:32px; height:32px; border-radius:50%;
               background: radial-gradient(circle at 35% 30%, #fff, var(--snet-teal) 38%, var(--snet-magenta));
               box-shadow: 0 0 18px rgba(22,212,212,0.22); flex-shrink:0; }
  .nexi-kicker { color:var(--dim); font-size:10px; text-transform:uppercase; letter-spacing:.5px; }
  .nexi-title { color:var(--fg); font-size:15px; font-weight:700; }
  .nexi-copy { color:var(--fg); font-size:12px; line-height:1.45; margin:6px 0 10px; max-width: 900px; }
  .defense-row { border:1px solid rgba(48,54,61,0.85); border-radius:6px;
                 background: rgba(13,17,23,0.72); padding:10px; }
  .defense-head { display:flex; align-items:baseline; justify-content:space-between;
                  gap:10px; margin-bottom:8px; }
  .defense-title { font-weight:700; font-size:12px; color:var(--fg); }
  .defense-note { color:var(--dim); font-size:10px; text-align:right; }
  .defense-cards { display:grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap:8px; }
  .defense-row.assurance .defense-cards { grid-template-columns: repeat(3, minmax(0, 1fr)); }
  .defense-row.domain .defense-cards { grid-template-columns: repeat(3, minmax(0, 1fr)); }
  .org-card { border:1px solid var(--border); border-left:4px solid var(--snet-teal);
              border-radius:6px; padding:9px 10px; min-height:84px;
              background: rgba(255,255,255,0.025); cursor:pointer; transition: border-color .15s, background .15s; }
  .org-card:hover { border-color: var(--accent); background: rgba(121,192,255,0.08); }
  .org-card.line1 { border-left-color: var(--you); }
  .org-card.line2 { border-left-color: var(--snet-teal); }
  .org-card.line3 { border-left-color: var(--snet-magenta); }
  .org-card.command { border-left-color: var(--accent); background: rgba(121,192,255,0.08); border-color: rgba(121,192,255,0.45); }
  .org-card.domain { border-left-color: var(--oma); }
  .org-card.primary { background: rgba(22,212,212,0.08); border-color: rgba(22,212,212,0.5); }
  .org-card .org-card-name { color:var(--fg); font-size:13px; font-weight:700; margin-bottom:4px; }
  .org-card .org-card-role { color:var(--dim); font-size:10px; line-height:1.35; }
  .org-card .org-card-meta { margin-top:8px; display:flex; gap:5px; flex-wrap:wrap; }
  .mini-pill { color:var(--dim); border:1px solid rgba(110,118,129,0.5); border-radius:10px;
               padding:1px 6px; font-size:9px; white-space:nowrap; }
  .flow-strip { display:grid; grid-template-columns:1fr auto 1fr; align-items:center; color:var(--dim);
                font-size:10px; gap:8px; padding:1px 8px; }
  .flow-strip:before, .flow-strip:after { content:""; height:1px; background:linear-gradient(90deg, transparent, rgba(121,192,255,0.45), transparent); }
  .flow-strip span { color:var(--snet-teal); white-space:nowrap; }
  .line-band { border-left: 3px solid var(--border); padding: 8px 10px; margin-bottom: 8px;
               background: rgba(255,255,255,0.02); border-radius: 4px; }
  .line-band.l1 { border-left-color: var(--you); }
  .line-band.l2 { border-left-color: var(--snet-teal); }
  .line-band.l3 { border-left-color: var(--snet-magenta); }
  .report { padding: 8px 0; border-bottom: 1px solid rgba(48,54,61,0.7); }
  .report:last-child { border-bottom: 0; }
  .report .r-head { color: var(--fg); font-weight: 600; font-size: 12px; }
  .report .r-meta { color: var(--dim); font-size: 10px; margin-top: 2px; }
  .report-builder { display:grid; grid-template-columns: 1fr 1fr 1fr; gap:8px; margin-bottom:12px; }
  .report-builder label { display:flex; flex-direction:column; gap:4px; color:var(--dim); font-size:10px;
                          text-transform:uppercase; letter-spacing:.4px; }
  .report-builder select, .report-builder input { width:100%; box-sizing:border-box; }
  .report-actions { display:flex; gap:8px; align-items:center; flex-wrap:wrap; margin:8px 0 2px; }
  .report-preview { border:1px solid var(--border); border-radius:6px; background:rgba(255,255,255,0.02);
                    padding:14px; white-space:pre-wrap; line-height:1.5; font-size:12px; max-height:520px; overflow:auto; }
  .report-matrix { width:100%; border-collapse:collapse; table-layout:fixed; font-size:11px; }
  .report-matrix th, .report-matrix td { border:1px solid var(--border); padding:8px; vertical-align:top; }
  .report-matrix th { color:var(--dim); font-weight:600; text-align:left; }
  .report-matrix td { color:var(--fg); overflow-wrap:anywhere; }
  .org-hero { display:grid; grid-template-columns: 1fr 1fr 1fr; gap:8px; margin-bottom:12px; }
  .org-title { font-size: 20px; font-weight: 700; color: var(--snet-teal); margin-bottom: 4px; }
  .org-sub { color: var(--dim); font-size: 12px; line-height: 1.5; }
  .chip { display:inline-block; border:1px solid var(--border); color:var(--fg);
          padding:3px 7px; border-radius:12px; margin:2px; font-size:10px; background:rgba(255,255,255,0.02); }
  @media (max-width: 980px) {
    .viz-wrap { grid-template-columns: 1fr; }
    .risk-grid { grid-template-columns: repeat(2, 1fr); }
    .report-builder { grid-template-columns: 1fr; }
    .defense-cards, .defense-row.assurance .defense-cards, .defense-row.domain .defense-cards { grid-template-columns: 1fr; }
  }
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
    <a class="nav-link" data-page="ecosystem">Ecosystem</a>
    <a class="nav-link" data-page="history">History</a>
    <a class="nav-link" data-page="risks">Risks</a>
    <a class="nav-link" data-page="heatmap">Heatmap</a>
    <a class="nav-link" data-page="reports">Reports</a>
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

    <!-- ============ Page: Ecosystem ============ -->
    <div class="page" id="page-ecosystem">
      <div class="page-content">
        <div class="section">
          <h2>SingularityNET ecosystem risk cockpit</h2>
          <div class="pager">
            <button id="seed_demo">Seed sample dashboard</button>
            <span>Demo data: synthetic reports from autonomous agents mapped to NIST IR 8286.</span>
          </div>
          <div class="viz-wrap">
            <div class="network-panel" id="network_panel">loading…</div>
            <div>
              <div class="line-band l1"><strong>Line 1</strong><br><span style="color:var(--dim)">Operational owners: NuNet and Hyperon agents report local control and system telemetry.</span></div>
              <div class="line-band l2"><strong>Line 2</strong><br><span style="color:var(--dim)">Risk function: Oma synthesizes governance, ethics, model, and evidence signals.</span></div>
              <div class="line-band l3"><strong>Line 3</strong><br><span style="color:var(--dim)">Oversight: AgentGriff provides independent InterNetwork Defense CRO challenge, claims review, fallback accountability, and board-facing evidence review.</span></div>
              <div class="section" style="margin:10px 0 0;padding:10px 12px">
                <h2>Incoming agent reports</h2>
                <div id="report_feed">loading…</div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>

    <!-- ============ Page: Organization detail ============ -->
    <div class="page" id="page-org">
      <div class="page-content">
        <div class="section">
          <button id="org_back" class="reset" style="margin:0 0 10px 0">← ecosystem</button>
          <div class="org-title" id="org_name">Organization</div>
          <div class="org-sub" id="org_summary">loading…</div>
        </div>
        <div class="org-hero">
          <div class="tile"><div class="label">Line of defense</div><div class="value" id="org_line">—</div></div>
          <div class="tile"><div class="label">Mapped risks</div><div class="value" id="org_risk_count">—</div></div>
          <div class="tile"><div class="label">Agent reports</div><div class="value" id="org_report_count">—</div></div>
        </div>
        <div class="section">
          <h2>Control focus</h2>
          <div id="org_controls">loading…</div>
        </div>
        <div class="section">
          <h2>Mapped risks</h2>
          <div id="org_risks">loading…</div>
        </div>
        <div class="section">
          <h2>Autonomous agent reports</h2>
          <div id="org_reports">loading…</div>
        </div>
        <div class="section">
          <h2>Next actions</h2>
          <div id="org_actions">loading…</div>
        </div>
      </div>
    </div>

    <!-- ============ Page: Risks ============ -->
    <div class="page" id="page-risks">
      <div class="page-content">
        <div class="section">
          <h2>Risk Radar</h2>
          <div class="risk-grid">
            <div class="tile"><div class="label">Open risks</div><div class="value" id="risk_open">—</div></div>
            <div class="tile"><div class="label">Critical</div><div class="value" id="risk_critical">—</div></div>
            <div class="tile"><div class="label">High</div><div class="value" id="risk_high">—</div></div>
            <div class="tile"><div class="label">Need attention</div><div class="value" id="risk_attention">—</div></div>
          </div>
          <div id="risk_list">loading…</div>
        </div>
        <div class="section">
          <h2>AI system intake</h2>
          <div class="risk-form">
            <input type="text" id="risk_title" placeholder="Risk title">
            <input type="text" id="risk_owner" placeholder="Decision owner">
            <input type="text" id="risk_likelihood" placeholder="Likelihood 1-5">
            <input type="text" id="risk_impact" placeholder="Impact 1-5">
            <textarea id="risk_desc" placeholder="Use case, evidence, recommendation, residual risk, required human approval"></textarea>
          </div>
          <button id="risk_add">Add draft risk</button>
        </div>
      </div>
    </div>

    <!-- ============ Page: Heatmap ============ -->
    <div class="page" id="page-heatmap">
      <div class="page-content">
        <div class="section">
          <h2>Likelihood x Impact Heatmap</h2>
          <div id="heatmap_table">loading…</div>
        </div>
        <div class="section">
          <h2>Risks needing attention</h2>
          <div id="attention_list">loading…</div>
        </div>
      </div>
    </div>

    <!-- ============ Page: Reports ============ -->
    <div class="page" id="page-reports">
      <div class="page-content">
        <div class="section">
          <h2>Compliance Report Generator</h2>
          <div class="report-builder">
            <label>Framework
              <select id="report_framework">
                <option value="nist-ai-rmf">NIST AI RMF</option>
                <option value="iso-42001">ISO/IEC 42001</option>
                <option value="eu-ai-act">EU AI Act</option>
                <option value="nist-ir-8286">NIST IR 8286</option>
                <option value="combined">Combined board pack</option>
              </select>
            </label>
            <label>Report Type
              <select id="report_type">
                <option value="executive">Executive brief</option>
                <option value="controls">Controls evidence matrix</option>
                <option value="assessment">Risk and impact assessment</option>
                <option value="audit">Audit readiness note</option>
              </select>
            </label>
            <label>Scope
              <input type="text" id="report_scope" value="SingularityNET agentic AI ecosystem">
            </label>
            <label>Audience
              <input type="text" id="report_audience" value="CRO / Chief Ethics Officer / board-risk committee">
            </label>
            <label>Owner
              <input type="text" id="report_owner" value="Esther Galfalvi">
            </label>
            <label>Period
              <input type="text" id="report_period" value="Current review cycle">
            </label>
          </div>
          <div class="report-actions">
            <button id="report_generate">Generate draft</button>
            <button id="report_copy" class="reset">copy markdown</button>
            <span id="report_status" style="color:var(--dim); font-size:11px">Drafts support governance workflows; they do not certify compliance.</span>
          </div>
        </div>
        <div class="section">
          <h2>Draft Report</h2>
          <div id="report_brief" class="report-preview">loading…</div>
        </div>
        <div class="section">
          <h2>Controls-to-Evidence Matrix</h2>
          <div id="report_matrix">loading…</div>
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
    // Populate provider-aware model dropdown.
    const sel = $('model_select');
    const routes = (d.model_routes || (d.available_models || []).map(m => ({
      id: `ollama:${m}`, label: m, available: true
    })));
    const availKey = routes.map(r => `${r.id}:${r.available ? 1 : 0}`).join(',');
    if (availKey !== _availSeen) {
      _availSeen = availKey;
      sel.innerHTML = routes.map(r =>
        `<option value="${escapeHtml(r.id)}"${r.id === d.active_route ? ' selected' : ''}${r.available ? '' : ' disabled'}>${escapeHtml(r.label)}${r.available ? '' : ' · unavailable'}</option>`
      ).join('');
    } else if (sel.value !== d.active_route && !sel.dataset.userSwitching) {
      // Sync selection if active route changed externally
      sel.value = d.active_route;
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
  const label = e.target.options[e.target.selectedIndex]?.textContent || target;
  const ok = confirm(`Swap Oma to "${label}"? This kills swipl and relaunches; in-flight conversation will reset.`);
  if (!ok) {
    // revert UI selection on cancel
    fetchStats();
    return;
  }
  e.target.dataset.userSwitching = '1';
  e.target.disabled = true;
  try {
    const r = await fetch('/switch', {method:'POST', headers:{'Content-Type':'application/json'},
                                      body: JSON.stringify({route: target})});
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
  if (name === 'ecosystem') loadEcosystem();
  if (name === 'risks') loadRisks();
  if (name === 'heatmap') loadHeatmap();
  if (name === 'reports') loadReport();
  if (name === 'channels') loadChannels();
  if (name === 'settings') loadSettings();
}
document.querySelectorAll('.nav-link').forEach(a => {
  a.addEventListener('click', () => showPage(a.dataset.page));
});

// ============ History page ============
let _histOffset = 0;
let _currentOrgId = '';
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

// ============ Ecosystem page ============
async function loadEcosystem() {
  try {
    const r = await fetch('/ecosystem'); const d = await r.json();
    const nodes = d.nodes || [];
    const reports = d.reports || [];
    const risks = (d.dashboard || {}).top_risks || [];
    const reportCounts = {};
    const riskCounts = {};
    for (const rep of reports) {
      const risk = risks.find(x => x.id === rep.mapped_risk);
      const key = nodes.find(n => rep.source.toLowerCase().startsWith(n.label.toLowerCase()))?.id
               || nodes.find(n => (risk?.id || '').toLowerCase().includes(n.id))?.id;
      if (key) reportCounts[key] = (reportCounts[key] || 0) + 1;
    }
    for (const risk of risks) {
      const text = `${risk.id || ''} ${risk.title || ''} ${risk.description || ''}`.toLowerCase();
      for (const n of nodes) {
        if (text.includes(n.id) || text.includes((n.label || '').toLowerCase())) {
          riskCounts[n.id] = (riskCounts[n.id] || 0) + 1;
        }
      }
    }
    const lineMeta = {
      1: ['Line 1 · Risk Owner Agents', 'Model agnostic · current config: local GPU mix'],
      2: ['Line 2 · Risk Manager Agents', 'Model agnostic · current config: larger local models + API; sample route ChatGPT 5.5'],
      3: ['Line 3 · AgentGriff CRO Challenge', 'Model agnostic · current config: Claude Opus 4.7'],
    };
    const renderCard = n => `
      <div class="org-card ${escapeHtml(n.tier || '')} line${n.line || 0}${n.id === 'oma' ? ' primary' : ''}" data-org="${escapeHtml(n.id)}">
        <div class="org-card-name">${escapeHtml(n.label)}</div>
        <div class="org-card-role">${escapeHtml(n.role || n.summary || '')}</div>
        <div class="org-card-meta">
          <span class="mini-pill">${escapeHtml(n.owner || 'owner tbd')}</span>
          ${(n.models || []).slice(0, 3).map(m => `<span class="mini-pill">${escapeHtml(m)}</span>`).join('')}
          <span class="mini-pill">${riskCounts[n.id] || 0} risks</span>
          <span class="mini-pill">${reportCounts[n.id] || 0} reports</span>
        </div>
      </div>`;
    const command = nodes.find(n => n.tier === 'command');
    const assurance = nodes.filter(n => n.tier === 'assurance');
    const domains = nodes.filter(n => n.tier === 'domain');
    let html = '<div class="org-chart" role="img" aria-label="Oma above NIST IR 8286 assurance lines org chart">';
    if (command) {
      html += `<div class="command-row">
        <div class="nexi-head">
          <div class="nexi-mark"></div>
          <div>
            <div class="nexi-kicker">Esther Galfalvi's AI governance companion</div>
            <div class="nexi-title">Nexi supports Esther across all three assurance lines</div>
          </div>
        </div>
        <div class="defense-head">
          <div class="defense-title">Top layer · Nexi reporting to Esther</div>
          <div class="defense-note">Dynamic model routing · current examples: ChatGPT 5.5 primary, Claude Opus 4.7 fallback, local IBM Granite for ISO/IEC 42001 support</div>
        </div>
        <div class="defense-cards">${renderCard(command)}</div>
      </div>
      <div class="flow-strip"><span>Nexi gathers assurance signals; AgentGriff can challenge evidence and provide third-party CRO advice</span></div>`;
    }
    html += '<div class="defense-row assurance"><div class="defense-head"><div class="defense-title">Assurance agent layers</div><div class="defense-note">NIST IR 8286 lines reporting upward into Nexi, with AgentGriff available for independent challenge</div></div><div class="defense-cards">';
    for (const line of [1, 2, 3]) {
      html += assurance.filter(n => n.line === line).map(renderCard).join('');
    }
    html += '</div></div><div class="flow-strip"><span>sub-org Line 1 and Line 2 agents feed the assurance layers</span></div>';
    for (const line of [1, 2, 3]) {
      const [title, note] = lineMeta[line];
      html += `<div class="defense-row line${line}">
        <div class="defense-head">
          <div class="defense-title">${title}</div>
          <div class="defense-note">${note}</div>
        </div>
        <div class="defense-cards">${assurance.filter(n => n.line === line).map(renderCard).join('')}</div>
      </div>`;
    }
    html += `<div class="defense-row domain">
      <div class="defense-head">
        <div class="defense-title">SingularityNET ecosystem domains</div>
        <div class="defense-note">Each domain can host Line 1 risk-owner agents, Line 2 risk-manager agents, and optional Line 3 internal-audit agents; model routes stay dynamic</div>
      </div>
      <div class="defense-cards">${domains.map(renderCard).join('')}</div>
    </div>`;
    html += '</div>';
    $('network_panel').innerHTML = html;
    document.querySelectorAll('#network_panel .org-card').forEach(el => {
      el.addEventListener('click', () => openOrg(el.dataset.org));
    });
    $('report_feed').innerHTML = (d.reports || []).map(rep => `
      <div class="report">
        <div class="r-head">Line ${rep.line} · ${escapeHtml(rep.agent)}</div>
        <div>${escapeHtml(rep.summary)}</div>
        <div class="r-meta">${escapeHtml(rep.source)} · maps to ${escapeHtml(rep.mapped_risk)} · confidence ${escapeHtml(String(rep.confidence))}</div>
      </div>
    `).join('');
  } catch (e) { $('network_panel').textContent = 'load failed: ' + e; }
}

async function openOrg(id) {
  _currentOrgId = id;
  showPage('org');
  await loadOrg(id);
}

async function loadOrg(id) {
  try {
    const r = await fetch(`/org?id=${encodeURIComponent(id)}`); const d = await r.json();
    if (!d.ok) throw new Error(d.err || 'unknown org');
    const org = d.org || {};
    $('org_name').textContent = org.label || id;
    $('org_summary').textContent = `${org.role || ''} · ${org.summary || ''}`;
    $('org_line').textContent = org.line ? `Line ${org.line}` : '—';
    $('org_risk_count').textContent = (d.risks || []).length;
    $('org_report_count').textContent = (d.reports || []).length;
    $('org_controls').innerHTML = (org.controls || []).map(x => `<span class="chip">${escapeHtml(x)}</span>`).join('');
    $('org_actions').innerHTML = (org.actions || []).map(x => `<button class="reset" style="margin:3px 6px 3px 0">${escapeHtml(x)}</button>`).join('');
    $('org_risks').innerHTML = renderRiskCards(d.risks || []);
    $('org_reports').innerHTML = (d.reports || []).map(rep => `
      <div class="report">
        <div class="r-head">Line ${rep.line} · ${escapeHtml(rep.agent)}</div>
        <div>${escapeHtml(rep.summary)}</div>
        <div class="r-meta">${escapeHtml(rep.source)} · maps to ${escapeHtml(rep.mapped_risk)} · confidence ${escapeHtml(String(rep.confidence))}</div>
      </div>
    `).join('') || '<div class="row"><span class="v" style="color:var(--dim)">No agent reports mapped yet.</span></div>';
  } catch (e) {
    $('org_name').textContent = id || 'Organization';
    $('org_summary').textContent = 'load failed: ' + e;
  }
}

$('org_back').addEventListener('click', () => showPage('ecosystem'));

async function seedDemo() {
  const btn = $('seed_demo');
  btn.disabled = true;
  try {
    const r = await fetch('/demo/seed', {method:'POST', headers:{'Content-Type':'application/json'}, body:'{}'});
    const d = await r.json();
    if (!d.ok) return alert('seed failed: ' + (d.err || 'unknown'));
    await loadEcosystem();
    await loadRisks();
    alert(`Seeded ${d.inserted} sample risks. Total structured risks: ${d.total}.`);
  } catch (e) { alert('seed error: ' + e); }
  finally { btn.disabled = false; }
}
$('seed_demo').addEventListener('click', seedDemo);

// ============ Risk pages ============
function riskBadge(tier) {
  const t = (tier || 'low').toLowerCase();
  return `<span class="badge ${escapeHtml(t)}">${escapeHtml(t.toUpperCase())}</span>`;
}

function renderRiskCards(rows) {
  if (!rows || rows.length === 0) {
    return '<div class="row"><span class="v" style="color:var(--dim)">No structured risks captured yet.</span></div>';
  }
  return rows.map(r => `
    <div class="risk-card">
      <div class="title">${escapeHtml(r.title || 'Untitled risk')} ${riskBadge(r.risk_tier)}</div>
      <div class="meta">
        ${escapeHtml(r.id || '')} · status ${escapeHtml(r.status || 'open')} · score ${escapeHtml(String(r.priority || 0))}
        · L${escapeHtml(String(r.likelihood || 0))} x I${escapeHtml(String(r.impact || 0))}
      </div>
      <div class="meta">owner ${escapeHtml(r.decision_owner || 'unassigned')} · review ${escapeHtml(r.next_review_date || 'not set')}</div>
      ${r.description ? `<div class="desc">${escapeHtml(r.description)}</div>` : ''}
    </div>
  `).join('');
}

async function loadRisks() {
  try {
    const r = await fetch('/risks'); const d = await r.json();
    const dash = d.dashboard || {};
    const tiers = dash.by_tier || {};
    $('risk_open').textContent = dash.open || 0;
    $('risk_critical').textContent = tiers.critical || 0;
    $('risk_high').textContent = tiers.high || 0;
    $('risk_attention').textContent = (dash.attention || []).length;
    $('risk_list').innerHTML = renderRiskCards(d.risks || []);
  } catch (e) { $('risk_list').textContent = 'load failed: ' + e; }
}

async function addRisk() {
  const title = $('risk_title').value.trim();
  const description = $('risk_desc').value.trim();
  if (!title && !description) return alert('Add a title or description first.');
  const payload = {
    title: title || description.slice(0, 80),
    description,
    decision_owner: $('risk_owner').value.trim(),
    likelihood: $('risk_likelihood').value.trim(),
    impact: $('risk_impact').value.trim(),
    framework: 'NIST AI RMF / ISO 42001 / NIST IR 8286',
    status: 'open'
  };
  const btn = $('risk_add');
  btn.disabled = true;
  try {
    const r = await fetch('/risks', {method:'POST', headers:{'Content-Type':'application/json'},
                                    body: JSON.stringify(payload)});
    const d = await r.json();
    if (!d.ok) return alert('risk add failed: ' + (d.err || 'unknown'));
    ['risk_title','risk_owner','risk_likelihood','risk_impact','risk_desc'].forEach(id => $(id).value = '');
    loadRisks();
  } catch (e) { alert('risk add error: ' + e); }
  finally { btn.disabled = false; }
}
$('risk_add').addEventListener('click', addRisk);

async function loadHeatmap() {
  try {
    const r = await fetch('/heatmap'); const d = await r.json();
    const heat = d.heatmap || [[0,0,0,0,0],[0,0,0,0,0],[0,0,0,0,0],[0,0,0,0,0],[0,0,0,0,0]];
    let html = '<table class="heatmap"><thead><tr><th>Impact \\ Likelihood</th>';
    for (let l = 1; l <= 5; l++) html += `<th>${l}</th>`;
    html += '</tr></thead><tbody>';
    for (let impact = 5; impact >= 1; impact--) {
      html += `<tr><th>${impact}</th>`;
      for (let likelihood = 1; likelihood <= 5; likelihood++) {
        const count = (heat[impact - 1] || [])[likelihood - 1] || 0;
        const score = likelihood * impact;
        const level = count === 0 ? 0 : (score >= 20 ? 4 : score >= 12 ? 3 : score >= 6 ? 2 : 1);
        html += `<td class="heat-${level}">${count || '—'}</td>`;
      }
      html += '</tr>';
    }
    html += '</tbody></table>';
    $('heatmap_table').innerHTML = html;
    $('attention_list').innerHTML = renderRiskCards(d.attention || []);
  } catch (e) { $('heatmap_table').textContent = 'load failed: ' + e; }
}

async function loadReport() {
  try {
    await generateComplianceReport();
  } catch (e) { $('report_brief').textContent = 'load failed: ' + e; }
}

function reportProfile(framework) {
  const profiles = {
    'nist-ai-rmf': {
      title: 'NIST AI RMF Governance Report',
      note: 'Uses NIST AI RMF 1.0 as the default AI governance frame and maps current risks to Govern, Map, Measure, and Manage.',
      controls: ['Govern: policies, roles, accountability, risk appetite', 'Map: context, impacts, stakeholders, intended use', 'Measure: evaluation, monitoring, evidence, uncertainty', 'Manage: treatment, escalation, residual risk, review cadence'],
      caution: 'This draft supports NIST AI RMF workflow documentation; it is not a certification or external attestation.'
    },
    'iso-42001': {
      title: 'ISO/IEC 42001 AIMS Support Report',
      note: 'Organizes evidence for AI management system planning, operation, review, and improvement.',
      controls: ['Leadership and role clarity', 'AI risk and impact assessment', 'Operational planning and monitoring', 'Documented information and evidence', 'Management review and corrective action'],
      caution: 'This draft helps prepare audit evidence for an AIMS; it does not certify ISO/IEC 42001 conformity.'
    },
    'eu-ai-act': {
      title: 'EU AI Act Readiness Report',
      note: 'Frames current risks around risk classification, human oversight, transparency, data governance, logging, and post-market monitoring.',
      controls: ['Risk classification and intended purpose', 'Human oversight', 'Transparency and user information', 'Data governance and evidence', 'Logging, monitoring, and incident handling'],
      caution: 'This draft supports readiness analysis only; legal classification and conformity assessment require qualified review.'
    },
    'nist-ir-8286': {
      title: 'NIST IR 8286 Enterprise Risk Integration Report',
      note: 'Shows how Line 1, Line 2, and Line 3 agent reports roll up into enterprise risk decisions.',
      controls: ['Line 1 operational ownership', 'Line 2 risk management synthesis', 'Line 3 independent review', 'Risk appetite and escalation', 'Board-risk reporting'],
      caution: 'This draft supports ERM alignment and board-risk preparation; it is not an assurance opinion.'
    },
    combined: {
      title: 'Combined AI Governance Board Pack',
      note: 'Combines NIST AI RMF, ISO/IEC 42001, EU AI Act readiness, and NIST IR 8286 enterprise risk framing.',
      controls: ['Governance and accountability', 'Risk and impact assessment', 'Human oversight and approval', 'Evidence and logging', 'Incident, treatment, and review cadence'],
      caution: 'This is a consolidated governance artifact for decision support; it does not certify compliance.'
    }
  };
  return profiles[framework] || profiles.combined;
}

function reportTypeLabel(type) {
  return {
    executive: 'Executive brief',
    controls: 'Controls evidence matrix',
    assessment: 'Risk and impact assessment',
    audit: 'Audit readiness note'
  }[type] || 'Executive brief';
}

function classifyControl(profile, risk) {
  const text = `${risk.framework || ''} ${(risk.control_mapping || []).join(' ')} ${risk.description || ''}`.toLowerCase();
  if (text.includes('incident') || text.includes('monitor')) return profile.controls.find(x => /monitor|manage|operation|post-market|Line 1/i.test(x)) || profile.controls[0];
  if (text.includes('impact') || text.includes('map') || text.includes('consent') || text.includes('data')) return profile.controls.find(x => /impact|map|data|classification|context/i.test(x)) || profile.controls[0];
  if (text.includes('audit') || text.includes('line 3') || text.includes('evidence') || text.includes('documented')) return profile.controls.find(x => /evidence|audit|Line 3|documented|logging/i.test(x)) || profile.controls[0];
  if (text.includes('govern') || text.includes('owner') || text.includes('approval')) return profile.controls.find(x => /govern|role|oversight|accountability|approval/i.test(x)) || profile.controls[0];
  return profile.controls[0];
}

function riskLine(r) {
  return `- ${r.id || 'RISK'}: ${r.title || 'Untitled'} [${(r.risk_tier || 'low').toUpperCase()}] L${r.likelihood || 0} x I${r.impact || 0}; owner: ${r.decision_owner || 'unassigned'}; approval: ${r.required_human_approval || 'not specified'}.`;
}

function evidenceText(r) {
  const ev = Array.isArray(r.evidence_sources) ? r.evidence_sources : [];
  return ev.length ? ev.join('; ') : 'Evidence source not attached yet';
}

async function generateComplianceReport() {
  const [riskResp, ecoResp] = await Promise.all([fetch('/risks'), fetch('/ecosystem')]);
  const riskData = await riskResp.json();
  const ecoData = await ecoResp.json();
  const risks = riskData.risks || [];
  const dash = riskData.dashboard || {};
  const reports = ecoData.reports || [];
  const framework = $('report_framework').value;
  const type = $('report_type').value;
  const profile = reportProfile(framework);
  const scope = $('report_scope').value.trim() || 'AI system portfolio';
  const audience = $('report_audience').value.trim() || 'governance leadership';
  const owner = $('report_owner').value.trim() || 'decision owner';
  const period = $('report_period').value.trim() || 'current period';
  const tiers = dash.by_tier || {};
  const top = [...risks].sort((a, b) => (b.priority || 0) - (a.priority || 0)).slice(0, 6);
  const attention = dash.attention || [];
  const open = dash.open || risks.filter(r => (r.status || 'open') !== 'closed').length;
  const reportLines = reports.slice(0, 6).map(r => `- Line ${r.line} ${r.agent}: ${r.summary} (${r.source}; maps to ${r.mapped_risk})`);
  const controlRows = top.map(r => ({
    control: classifyControl(profile, r),
    risk: `${r.id || ''}: ${r.title || ''}`,
    evidence: evidenceText(r),
    gap: attention.find(x => x.id === r.id) ? 'Needs owner, evidence, treatment, review date, or escalation completion' : 'Evidence present for draft review',
    owner: r.decision_owner || 'unassigned',
  }));
  const decisions = top.filter(r => ['critical', 'high'].includes((r.risk_tier || '').toLowerCase()) || r.required_human_approval).map(riskLine);
  const sections = [
    `# ${profile.title}`,
    `Report type: ${reportTypeLabel(type)}`,
    `Scope: ${scope}`,
    `Audience: ${audience}`,
    `Owner: ${owner}`,
    `Period: ${period}`,
    '',
    '## Executive Summary',
    `${profile.note} Current portfolio posture shows ${open} open risks: ${tiers.critical || 0} critical, ${tiers.high || 0} high, ${tiers.medium || 0} medium, and ${tiers.low || 0} low. ${attention.length} item(s) need attention before this pack should be treated as board-ready.`,
    '',
    '## Governance Language',
    profile.caution,
    '',
    '## Decisions Needed',
    decisions.length ? decisions.join('\\n') : '- No high-priority decision items identified in the structured risk register.',
    '',
    '## Top Risk Register Items',
    top.length ? top.map(riskLine).join('\\n') : '- No structured risks captured yet.',
    '',
    '## Assurance Inputs',
    reportLines.length ? reportLines.join('\\n') : '- No autonomous agent reports available.',
    '',
    '## Framework Focus Areas',
    profile.controls.map(x => `- ${x}`).join('\\n'),
    '',
    '## Evidence Gaps and Next Steps',
    attention.length ? attention.slice(0, 8).map(r => `- ${r.id}: ${r.title || 'Untitled risk'} needs completion before final approval.`).join('\\n') : '- No immediate evidence gaps flagged by the dashboard.',
  ];
  if (type === 'controls') {
    sections.splice(8, 0, '## Controls Evidence Summary', controlRows.map(x => `- ${x.control}: ${x.risk}; evidence: ${x.evidence}; gap: ${x.gap}`).join('\\n'));
  } else if (type === 'assessment') {
    sections.splice(8, 0, '## Risk and Impact Assessment', top.map(r => `- ${r.title}: likelihood ${r.likelihood || 0}, impact ${r.impact || 0}, residual risk: ${r.residual_risk || 'not documented'}, treatment: ${r.treatment || 'not documented'}.`).join('\\n'));
  } else if (type === 'audit') {
    sections.splice(8, 0, '## Audit Readiness', `Evidence readiness is strongest where risk entries include owner, approval path, evidence sources, treatment, and next review date. ${attention.length} item(s) should be remediated before an external audit or board assurance review.`);
  }
  const markdown = sections.join('\\n');
  $('report_brief').textContent = markdown;
  $('report_brief').dataset.markdown = markdown;
  $('report_matrix').innerHTML = `
    <table class="report-matrix">
      <thead><tr><th>Framework focus</th><th>Mapped risk</th><th>Evidence</th><th>Gap / action</th><th>Owner</th></tr></thead>
      <tbody>
        ${controlRows.map(x => `<tr><td>${escapeHtml(x.control)}</td><td>${escapeHtml(x.risk)}</td><td>${escapeHtml(x.evidence)}</td><td>${escapeHtml(x.gap)}</td><td>${escapeHtml(x.owner)}</td></tr>`).join('') || '<tr><td colspan="5">No risk evidence available.</td></tr>'}
      </tbody>
    </table>`;
  $('report_status').textContent = `Generated ${reportTypeLabel(type)} for ${profile.title}.`;
}

['report_framework','report_type'].forEach(id => $(id).addEventListener('change', generateComplianceReport));
['report_scope','report_audience','report_owner','report_period'].forEach(id => $(id).addEventListener('input', () => {
  clearTimeout(window._reportTimer);
  window._reportTimer = setTimeout(generateComplianceReport, 350);
}));
$('report_generate').addEventListener('click', generateComplianceReport);
$('report_copy').addEventListener('click', async () => {
  const text = $('report_brief').dataset.markdown || $('report_brief').textContent || '';
  try {
    await navigator.clipboard.writeText(text);
    $('report_status').textContent = 'Copied report markdown to clipboard.';
  } catch (e) {
    $('report_status').textContent = 'Clipboard unavailable; select the draft text manually.';
  }
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


class _ReusableServer(socketserver.ThreadingMixIn, socketserver.TCPServer):
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
