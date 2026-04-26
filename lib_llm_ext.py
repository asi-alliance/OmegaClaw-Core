import os, json, re
import openai, httpx

# ----------------------------------------------------------------------------
# Per-model output-format config (loaded from models.yaml at module load)
# ----------------------------------------------------------------------------
_models_yaml = os.path.join(os.path.dirname(__file__), "models.yaml")
_model_formats = {}
try:
    import yaml
    if os.path.exists(_models_yaml):
        with open(_models_yaml) as _f:
            _cfg = yaml.safe_load(_f) or {}
        for _name, _spec in _cfg.items():
            if isinstance(_spec, dict):
                _model_formats[str(_name)] = (_spec.get("format") or "metta").lower()
            else:
                _model_formats[str(_name)] = "metta"
except Exception as _e:
    print(f"[lib_llm_ext] warning: could not load models.yaml ({_e}); defaulting all models to metta")

_DEFAULT_FORMAT = "metta"

# ----------------------------------------------------------------------------
# Per-skill canonical arg order for kwarg→positional MeTTa synthesis.
# Must stay in sync with the kwarg-shim rules in src/skills.metta.
# ----------------------------------------------------------------------------
_SKILL_ARG_ORDER = {
    "remember":           ["text"],
    "query":              ["text"],
    "episodes":           ["time"],
    "pin":                ["text"],
    "shell":              ["cmd"],
    "read-file":          ["filename"],
    "write-file":         ["filename", "content"],
    "append-file":        ["filename", "content"],
    "send":               ["text"],
    "search":             ["query"],
    "tavily-search":      ["query"],
    "technical-analysis": ["ticker"],
    "metta":              ["code"],
}

# ----------------------------------------------------------------------------
# Existing OpenAI clients + Ollama config (unchanged behavior)
# ----------------------------------------------------------------------------
def _init_openai_client(var_name, base_url):
    if var_name in os.environ:
        return openai.OpenAI(api_key=os.environ[var_name], base_url=base_url)
    else:
        return None

ASI_CLIENT = _init_openai_client(
    var_name="ASI_API_KEY",
    base_url="https://inference.asicloud.cudos.org/v1"
)

ANTHROPIC_CLIENT = _init_openai_client(
    var_name="ANTHROPIC_API_KEY",
    base_url="https://api.anthropic.com/v1/"
)

OLLAMA_BASE_URL = os.environ.get("OLLAMA_BASE_URL", "http://192.168.86.22:11434")
OLLAMA_MODEL    = os.environ.get("OLLAMA_MODEL", "deepseek-r1:14b")

CLAUDE_MODEL  = "claude-haiku-4-5-20251001"
MINIMAX_MODEL = "minimax/minimax-m2.7"

def _clean(text):
    return text.replace("_quote_", '"').replace("_apostrophe_", "'")

def _un_string_safe(text):
    """Reverse src/utils.metta:string-safe so JSON-mode models see real quotes
       in the prompt (especially in the JSON OUTPUT_FORMAT examples) instead
       of `_quote_` placeholders. Only applied for json/either formats; metta
       mode preserves the original wire format byte-for-byte."""
    if not text:
        return text
    return (text
            .replace("_quote_", '"')
            .replace("_apostrophe_", "'")
            .replace("_newline_", "\n"))

# ----------------------------------------------------------------------------
# Format adaptation helpers
# ----------------------------------------------------------------------------

# Strip ```json ... ``` or ``` ... ``` fences anywhere in the text.
_FENCE_RE = re.compile(r"```[a-zA-Z0-9_-]*\s*\n?|\n?\s*```", re.IGNORECASE)

def _strip_fences(text):
    return _FENCE_RE.sub("", text).strip()

# Strip <think>…</think> blocks emitted inline by reasoning models (R1, phi4-reasoning,
# QwQ, etc.) so they don't leak into Telegram messages or break JSON parsing.
_THINK_RE = re.compile(r"<think>[\s\S]*?</think>\s*", re.IGNORECASE)
# Some models emit only the opening tag and never close it within the budget.
# In that case strip everything from <think> onward (the actual answer was lost).
_THINK_OPEN_ONLY_RE = re.compile(r"<think>[\s\S]*$", re.IGNORECASE)

def _strip_thinking(text):
    if not text:
        return text
    text = _THINK_RE.sub("", text)
    text = _THINK_OPEN_ONLY_RE.sub("", text)
    return text.strip()

def _find_balanced_block(text):
    """Find the first balanced {...} or [...] block whose opening brace is
       outside any double-quoted string. Returns the substring or None."""
    in_str = False
    esc = False
    depth = 0
    start = -1
    open_ch = ""
    for i, c in enumerate(text):
        if esc:
            esc = False
            continue
        if c == '\\':
            esc = True
            continue
        if c == '"':
            in_str = not in_str
            continue
        if in_str:
            continue
        if depth == 0 and c in "{[":
            start = i
            open_ch = c
            depth = 1
            continue
        if depth > 0:
            if c == open_ch:
                depth += 1
            elif (open_ch == "{" and c == "}") or (open_ch == "[" and c == "]"):
                depth -= 1
                if depth == 0:
                    return text[start:i + 1]
    return None

def _metta_quote(value):
    """Render a Python value as a MeTTa string literal."""
    if not isinstance(value, str):
        try:
            value = json.dumps(value, ensure_ascii=False)
        except (TypeError, ValueError):
            value = str(value)
    return '"' + value.replace("\\", "\\\\").replace('"', '\\"') + '"'

def _normalize_call(call):
    """Accept either {"skill": ..., "args": {...}} or OpenAI tools-format
       {"function": {"name": ..., "arguments": str|dict}} (optionally wrapped
       in {"type":"function", "function": {...}}). Returns (skill, args_dict)
       or (None, {}) on failure."""
    if not isinstance(call, dict):
        return None, {}
    if "function" in call and isinstance(call["function"], dict):
        fn = call["function"]
        skill = fn.get("name", "")
        raw = fn.get("arguments", {})
        if isinstance(raw, str):
            try:
                args = json.loads(raw) if raw.strip() else {}
            except json.JSONDecodeError:
                args = {}
        elif isinstance(raw, dict):
            args = raw
        else:
            args = {}
        return (skill if isinstance(skill, str) and skill else None), args
    skill = call.get("skill") or call.get("name") or ""
    args = call.get("args") or call.get("arguments") or {}
    if isinstance(args, str):
        try:
            args = json.loads(args) if args.strip() else {}
        except json.JSONDecodeError:
            args = {}
    if not isinstance(skill, str) or not skill:
        return None, {}
    if not isinstance(args, dict):
        args = {}
    return skill, args

def _json_call_to_metta(call):
    """Translate one JSON call into a MeTTa s-expression string.
       Uses _SKILL_ARG_ORDER for known skills; falls back to JSON insertion
       order for anything else (forward-compat for new skills)."""
    skill, args = _normalize_call(call)
    if not skill:
        return None
    order = _SKILL_ARG_ORDER.get(skill)
    if order is None:
        order = list(args.keys())
    parts = [skill]
    for name in order:
        if name in args:
            parts.append(f"({name} {_metta_quote(args[name])})")
    if len(parts) == 1:
        return f"({skill})"
    return "(" + " ".join(parts) + ")"

def _adapt_response(model, text):
    """Transform a raw model response into a MeTTa s-expression string,
       per the model's configured format. The result is what loop.metta's
       sread will see. Models in metta-mode pass through untouched."""
    fmt = _model_formats.get(str(model), _DEFAULT_FORMAT)
    raw = (text or "").strip()
    if not raw:
        return raw
    if fmt == "metta":
        return raw
    # Strip <think>…</think> for json/either modes BEFORE doing anything else,
    # so reasoning-model thinking traces don't leak to Telegram or confuse the
    # JSON parser.
    raw = _strip_thinking(raw)
    if not raw:
        return ""
    if fmt == "either" and raw.startswith("("):
        return raw
    cleaned = _strip_fences(raw)
    block = _find_balanced_block(cleaned)
    if block is not None:
        try:
            parsed = json.loads(block)
            calls = parsed if isinstance(parsed, list) else [parsed]
            metta = []
            for c in calls:
                s = _json_call_to_metta(c)
                if s:
                    metta.append(s)
            if metta:
                return " ".join(metta)
            # JSON parsed cleanly but produced no callable skills
            # (commonly: model emitted `[]` to mean "no action this turn").
            # Return empty so the loop treats this as a no-op rather than
            # leaking the raw model text to Telegram.
            return ""
        except (json.JSONDecodeError, ValueError, TypeError):
            pass
    # Free-text fallback: only fires when JSON detection/parse failed.
    # Wraps the response as a send so the user at least sees what the
    # model produced instead of silent dead air. Strips fences first
    # so we don't ship literal ```json``` markers to Telegram.
    return f"(send (text {_metta_quote(_strip_fences(raw))}))"

# ----------------------------------------------------------------------------
# LLM call wrappers (now adapter-aware)
# ----------------------------------------------------------------------------

def _chat(client, model, content, max_tokens=6000):
    try:
        resp = client.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": content}],
            max_tokens=max_tokens,
            extra_body={
                "enable_thinking": True,
                "thinking_budget": 6000
            }
        )
        raw = _clean(resp.choices[0].message.content or "")
        return _adapt_response(model, raw)
    except Exception as e:
        print(f"[lib_llm_ext._chat] Exception while communicating with LLM: {e}")
        return ""

def useMiniMax(content):
    return _chat(
        client=ASI_CLIENT,
        model=MINIMAX_MODEL,
        content=content
    )

def useClaude(content):
    return _chat(
        client=ANTHROPIC_CLIENT,
        model=CLAUDE_MODEL,
        content=content
    )

def useGemma(content, num_predict=2000, timeout=600.0):
    """Despite the historical name, this hits Ollama at OLLAMA_BASE_URL with
       whatever model OLLAMA_MODEL is pointing at (gemma4, qwen, deepseek,
       etc.). The format adapter handles the per-model output convention.

       num_predict default lowered from 8000 → 2000: at 5 tok/s on slow models
       like Granite 4 H-Small that's still ~7 min worst-case rather than 27
       min, which avoids the long lockups during a single response. Most Oma
       turns produce 100-500 tokens anyway; 2000 is plenty of headroom."""
    fmt = _model_formats.get(OLLAMA_MODEL, _DEFAULT_FORMAT)
    if fmt in ("json", "either"):
        content = _un_string_safe(content)
    try:
        resp = httpx.post(
            f"{OLLAMA_BASE_URL}/api/chat",
            json={
                "model": OLLAMA_MODEL,
                "messages": [{"role": "user", "content": content}],
                "think": False,
                "stream": False,
                "options": {"num_predict": num_predict},
            },
            timeout=timeout,
        )
        resp.raise_for_status()
        raw = _clean(resp.json()["message"]["content"])
        return _adapt_response(OLLAMA_MODEL, raw)
    except Exception as e:
        print(f"[lib_llm_ext.useGemma] Exception while communicating with Ollama: {e}")
        return ""

# ----------------------------------------------------------------------------
# OUTPUT_FORMAT prompt hint (called from src/loop.metta getContext)
# ----------------------------------------------------------------------------

_METTA_HINT = (
    " OUTPUT_FORMAT: Up to 5 lines, do not wrap quotes around args, do not use variables:\n"
    " toolName1 arg1\n"
    " toolName2 arg2\n"
    " toolName3 arg3\n"
    " toolName4 arg4\n"
    " toolName5 arg5\n"
)

_JSON_HINT = (
    " OUTPUT_FORMAT: Reply with ONLY a JSON array of tool calls. No prose, no markdown fences, no <think> tags.\n"
    " Each call: {\"skill\": \"<name>\", \"args\": {\"<arg_name>\": <value>, ...}}\n"
    " Single example: [{\"skill\": \"send\", \"args\": {\"text\": \"hello\"}}]\n"
    " Two-call example: [{\"skill\": \"query\", \"args\": {\"text\": \"prior context\"}},\n"
    "                   {\"skill\": \"send\",  \"args\": {\"text\": \"working on it\"}}]\n"
    "\n"
    " WHEN TO REPLY WITH AN EMPTY ARRAY:\n"
    " If there is no new HUMAN_MESSAGE this turn AND no new tool result AND no error to report,\n"
    " your only valid output is the empty array: []\n"
    " Do NOT re-send earlier replies, do NOT invent new send calls, do NOT repeat questions\n"
    " you have already asked. Silence is correct. Wait for the next HUMAN_MESSAGE.\n"
    " Re-sending the same or paraphrased message is the most common bug — avoid it strictly.\n"
    "\n"
    " Skill names come from SKILLS above. Argument names by skill:\n"
    "   send/remember/query/pin: text\n"
    "   episodes: time\n"
    "   shell: cmd\n"
    "   read-file: filename\n"
    "   write-file/append-file: filename, content\n"
    "   search/tavily-search: query\n"
    "   technical-analysis: ticker\n"
    "   metta: code\n"
)

def _format_for_provider(provider_atom):
    """Map a (provider) atom from MeTTa to the active model's format."""
    provider = str(provider_atom).strip()
    if provider == "Anthropic":
        model = CLAUDE_MODEL
    elif provider == "Ollama":
        model = OLLAMA_MODEL
    elif provider == "ASICloud":
        model = MINIMAX_MODEL
    else:
        model = ""
    return _model_formats.get(model, _DEFAULT_FORMAT)

def get_output_format_hint(provider_atom):
    """Called from src/loop.metta. Returns the OUTPUT_FORMAT teaching block
       appropriate for the active model's expected output convention."""
    fmt = _format_for_provider(provider_atom)
    if fmt == "json":
        return _JSON_HINT
    if fmt == "either":
        return _METTA_HINT + "\n Alternatively, JSON tool-call format is also accepted:\n" + _JSON_HINT
    return _METTA_HINT

# ----------------------------------------------------------------------------
# Embedding model (unchanged)
# ----------------------------------------------------------------------------
_embedding_model = None

def initLocalEmbedding():
    model_name = "intfloat/e5-large-v2"
    global _embedding_model
    if _embedding_model is None:
        from sentence_transformers import SentenceTransformer
        _embedding_model = SentenceTransformer(model_name)
    return _embedding_model

def useLocalEmbedding(atom):
    global _embedding_model
    if _embedding_model is None:
        raise RuntimeError("Call initLocalEmbedding() first.")
    return _embedding_model.encode(
        atom,
        normalize_embeddings=True
    ).tolist()
