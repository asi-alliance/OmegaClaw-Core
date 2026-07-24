import os
import openai
from typing import Optional, Dict, Any
import lib_llm_ext as llm
import providers
from src.logger import get_logger

logger = get_logger(__name__)

class OpenRouterProvider(providers.LLMProvider):

    def __init__(self):
        super().__init__()

    def config(self, config: dict) -> None:
        model = config.get("model", "z-ai/glm-5.2")
        self.delegate = OpenRouterProviderImpl("OpenRouter", "OPENROUTER_API_KEY",
                                               model, "https://openrouter.ai/api/v1")

    def chat(self, prompt: str, max_tokens: int = 6000, reasoning_mode: str = "medium") -> str:
        return self.delegate.chat(prompt, max_tokens, reasoning_mode)

def loadOmegaClawPlugin():
    providers.registerLLMProvider("OpenRouter", OpenRouterProvider())

class OpenRouterProviderImpl(llm.AIProvider):
    """OpenRouter provider with reasoning mode enabled (reasoning tokens excluded from the response)."""

    def _create_client(self) -> Optional[openai.OpenAI]:
        """Create OpenRouter client from environment."""
        proxy_url = os.environ.get("GATEWAY_URL")
        if proxy_url:
            base_url = f"{proxy_url.rstrip('/')}/openrouter/"
            logger.info(f"[OpenRouterProviderImpl._create_client]: Connecting via proxy: {base_url}")
            return openai.OpenAI(
                    api_key="proxy",
                    base_url=base_url,
                    )
        if self._var_name in os.environ:
            return openai.OpenAI(api_key=os.environ.get(self._var_name), base_url=self._base_url)

        return None

    def _openrouter_extra_body(self, content: str, max_tokens: int) -> Dict[str, Any]:
        sysmsg, _ = llm._split_system_user(content)
        body = {
            "reasoning": {
                "enabled": True,
                "max_tokens": max_tokens,
                "exclude": True,
            }
        }

        # Helps OpenRouter sticky-route requests for better cache locality.
        # Keep this stable per agent/session.
        session_id = os.environ.get("OPENROUTER_SESSION_ID")
        if not session_id and sysmsg:
            session_id = llm._stable_cache_key("openrouter", self._model_name, sysmsg)

        if session_id:
            body["session_id"] = session_id[:256]

        model = self._model_name.lower()

        # OpenRouter supports top-level cache_control for Anthropic Claude routes.
        if model.startswith("anthropic/"):
            body["cache_control"] = {
                "type": "ephemeral",
                "ttl": os.environ.get("OPENROUTER_CACHE_TTL", "5m"),
            }

        return body


    def chat(self, content: str, max_tokens: int = 6000, reasoning: str = "medium", **kwargs) -> str:
        extra_body = llm._merge_dicts(
            self._openrouter_extra_body(content, max_tokens),
            kwargs.pop("extra_body", None),
        )

        return super().chat(
            content=content,
            max_tokens=max_tokens,
            reasoning=reasoning,
            extra_body=extra_body,
            **kwargs,
        )
