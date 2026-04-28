import os, openai
from typing import Optional

class AIProvider:
    """Lazy AI provider with on-demand initialization."""

    def __init__(self, name: str, var_name: str, model_name: str, base_url: str):
        self._name = name
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
        if self._var_name in os.environ:
            if self._var_name == "OLLAMA_API_KEY":
                llm_server_local_url = os.environ.get("LLM_SERVER_LOCAL_URL")
                if llm_server_local_url:
                    self._base_url = llm_server_local_url.rstrip("/") + "/v1"
                elif not self._base_url.endswith("/v1"):
                    self._base_url = self._base_url.rstrip("/") + "/v1"

            return openai.OpenAI(api_key=os.environ.get(self._var_name), base_url=self._base_url)

        return None

    @property
    def is_available(self) -> bool:
        """Check if provider is configured (without initializing)."""
        return bool(os.environ.get(self._var_name))

    def chat(self, model: str, content: str, max_tokens: int = 6000) -> str:
        """Send chat request, initializing client if needed."""
        self._ensure_client()

        if self._client is None:
            raise RuntimeError(f"{self._name} not configured (set {self._var_name})")

        response = self._client.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": content}],
            max_tokens=max_tokens
        )

        return self._clean_text(response.choices[0].message.content)

    def _clean_text(self, text: str) -> str:
        """Unescape special characters."""
        return text.replace("_quote_", '"').replace("_apostrophe_", "'")



# Provider registry - lazy, no initialization yet
_provider_registry = {}


def _register_provider(name: str, var_name: str, model_name: str, base_url: str):
    """Register a provider configuration (no instantiation yet)."""
    _provider_registry[name] = AIProvider(name, var_name, model_name, base_url)


def _get_provider(name: str) -> Optional[AIProvider]:
    """Get or create provider instance on demand."""
    return _provider_registry.get(name)


# Register all providers (cheap - just stores config)
_register_provider(name="ASICloud", var_name="ASI_API_KEY", model_name="minimax/minimax-m2.5", base_url="https://inference.asicloud.cudos.org/v1")
_register_provider(name="Anthropic", var_name="ANTHROPIC_API_KEY", model_name="claude-opus-4-6", base_url="https://api.anthropic.com/v1/")
_register_provider(name="Ollama-local", var_name="OLLAMA_API_KEY", model_name="qwen3.5:9b", base_url="http://localhost:11434/v1")
# At the moment the OpenAI model call is in PeTTa, just init a default config here
_register_provider(name="OpenAI", var_name="OPENAI_API_KEY", model_name="gpt-5.4", base_url="https://api.openai.com/v1")


def callProvider(provider_name: str, content: str, max_tokens: int = 6000) -> str:
    """Generic dispatcher for MeTTa."""
    provider = _get_provider(provider_name)
    if not provider or not provider.is_available:
        raise RuntimeError(f"Provider '{provider_name}' not available")
    return provider.chat(model=provider._model_name, content=content, max_tokens=max_tokens)



_embedding_model = None

def initLocalEmbedding():
    model_name="intfloat/e5-large-v2"
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



