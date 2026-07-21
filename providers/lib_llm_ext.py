import os, hashlib
import json
import time
import uuid
import openai
from typing import Optional, Tuple, Dict, Any

PROMPT_DELIMITER = ":-:-:-:"

from src.logger import get_logger
# Shared redactor (Issue #3) — kept dependency-light so logging never leaks secrets/PII.
try:
    from src.redaction import redact_secrets
except ImportError:  # pragma: no cover - flat import path
    from redaction import redact_secrets


logger = get_logger(__name__)


def _raw_logging_enabled() -> bool:
    return (os.environ.get("OMEGACLAW_DEBUG_LLM_RAW") or "").strip().lower() in {"1", "true", "yes", "on"}


def _log_raw(provider: str, model: str, raw: str) -> None:
    """Redacted, gated raw-response logging (Issue #3, ported onto the plugin providers package).

    Metadata only by default; the raw body is emitted (redacted via
    ``src.redaction.redact_secrets``) ONLY when ``OMEGACLAW_DEBUG_LLM_RAW`` is set. Optional JSONL
    sink via ``OMEGACLAW_LLM_LOG_PATH``. This replaces upstream's ``raw={raw!r}`` debug line, which
    would emit unredacted model output to the logs (a privacy regression for this fork)."""
    ts = time.strftime("%Y-%m-%d %H:%M:%S", time.gmtime())
    raw = raw or ""
    chars = len(raw)
    trace = uuid.uuid4().hex[:8]
    debug = _raw_logging_enabled()

    body = repr(redact_secrets(raw)) if debug else "<redacted; set OMEGACLAW_DEBUG_LLM_RAW=1>"
    # Issue #3 contract: the metadata line is ALWAYS observable (never gated behind a log level),
    # so it uses print rather than logger.debug (which config/logging.conf suppresses at INFO).
    print(f"[LLM_RAW] ts={ts} trace={trace} provider={provider} model={model} chars={chars} raw={body}")

    log_path = os.environ.get("OMEGACLAW_LLM_LOG_PATH")
    if log_path:
        record = {"ts": ts, "trace": trace, "provider": provider, "model": model, "chars": chars}
        if debug:
            record["raw"] = redact_secrets(raw)
        try:
            with open(log_path, "a", encoding="utf-8") as f:
                f.write(json.dumps(record, ensure_ascii=False) + "\n")
        except OSError as exc:  # best-effort; never break the chat path
            print(f"[LLM_RAW] WARNING could not write OMEGACLAW_LLM_LOG_PATH ({log_path}): {exc}")

def _split_system_user(content: str) -> Tuple[str, str]:
    """
    MeTTa sends:
        <system/context> :-:-:-: <last human/wakeup message>

    Keep the split intact so providers receive a real system prompt.
    """
    if PROMPT_DELIMITER not in content:
        return "", content.strip()

    sysmsg, _, usermsg = content.partition(PROMPT_DELIMITER)
    sysmsg = sysmsg.strip()
    usermsg = usermsg.strip()

    if not usermsg:
        usermsg = "EMPTY / NO NEW USER INPUT."

    return sysmsg, usermsg

def _stable_cache_key(provider: str, model: str, sysmsg: str) -> str:
    """
    Stable key for requests sharing the same system-prefix family.
    Do not include the user message here.
    """
    marker = " LAST_SKILL_USE_RESULTS: "
    stable = sysmsg.split(marker, 1)[0].strip()
    digest = hashlib.sha256(stable.encode("utf-8")).hexdigest()[:24]
    return f"{provider.lower()}:{model}:{digest}"


def _merge_dicts(base: Optional[Dict[str, Any]], extra: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    merged = dict(base or {})
    merged.update(extra or {})
    return merged

class AbstractAIProvider:
    def __init__(self, name: str):
        self._name = name

    @property
    def name(self) -> str:
        return self._name

    def chat(self, content: str, max_tokens: int = 6000, reasoning: str = "medium", **kwargs) -> str:
        raise NotImplementedError

    @property
    def is_available(self) -> bool:
        raise NotImplementedError

class AIProvider(AbstractAIProvider):
    """Lazy AI provider with on-demand initialization."""

    def __init__(self, name: str, var_name: str, model_name: str, base_url: str):
        super().__init__(name)
        self._var_name = var_name
        self._model_name = model_name
        self._base_url = base_url
        self._client = None  # lazy initialization

    def _ensure_client(self):
        """Initialize client on first use."""
        if self._client is None:
            self._client = self._create_client()

    def _create_client(self) -> Optional[openai.OpenAI]:
        """Create OpenAI client from environment."""
        proxy_url = os.environ.get("GATEWAY_URL")
        if proxy_url:
            prefix = self._name.lower()
            base_url = f"{proxy_url.rstrip('/')}/{prefix}/"
            logger.info(f"[AIProvider._create_client]: Connecting via proxy: {base_url}")
            return openai.OpenAI(
                    api_key="proxy",
                    base_url=base_url,
                    )
        if self._var_name in os.environ:
            return openai.OpenAI(api_key=os.environ.get(self._var_name), base_url=self._base_url)

        return None

    @property
    def is_available(self) -> bool:
        """Check if provider is configured (without initializing)."""
        return bool(os.environ.get("GATEWAY_URL")) or bool(os.environ.get(self._var_name))

    def _build_messages(self, content: str):
        sysmsg, usermsg = _split_system_user(content)

        if sysmsg:
            return [
                {"role": "system", "content": sysmsg},
                {"role": "user", "content": usermsg},
            ]

        return [{"role": "user", "content": usermsg}]

    def chat(self, content: str, max_tokens: int = 6000, reasoning: str = "medium", **kwargs) -> str:
        """Send chat request, initializing client if needed."""
        self._ensure_client()

        if self._client is None:
            raise RuntimeError(f"{self.name} not configured (set {self._var_name})")

        try:
            response = self._client.chat.completions.create(
                model=self._model_name,
                messages=self._build_messages(content),
                max_tokens=max_tokens,
                **kwargs
            )

            raw = response.choices[0].message.content or ""
            _log_raw(self._name, self._model_name, raw)
            resp = self._clean_text(raw)
            return resp
        except Exception as e:
            logger.exception(f"[AIProvider.chat]: Exception while communicating with LLM: {e}")
            return ""

    def _clean_text(self, text: str) -> str:
        """Unescape special characters."""
        return text.replace("_quote_", '"').replace("_apostrophe_", "'").replace("</arg_value>", " ") \
                    .replace("</tool_call>", " ").replace("<arg_value>", " ").replace("<tool_call>", " ")


_embedding_model = None

def initLocalEmbedding():
    model_name="intfloat/e5-large-v2"
    global _embedding_model
    os.environ["HF_HUB_OFFLINE"] = "1"
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
