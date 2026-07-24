import os
import lib_llm_ext as llm
import providers
from src.logger import get_logger

logger = get_logger(__name__)

class OpenAIProvider(providers.LLMProvider):

    def __init__(self):
        super().__init__()

    def config(self, config: dict) -> None:
        model = config.get("model", "gpt-5.5")
        self.delegate = OpenAIProviderImpl("OpenAI", "OPENAI_API_KEY",
                                           model, "https://api.openai.com/v1")

    def chat(self, prompt: str, max_tokens: int = 6000, reasoning_mode: str = "medium") -> str:
        return self.delegate.chat(prompt, max_tokens, reasoning_mode)

def loadOmegaClawPlugin():
    providers.registerLLMProvider("OpenAI", OpenAIProvider())

class OpenAIProviderImpl(llm.AIProvider):
    """OpenAI provider using the Responses API (reasoning models)."""

    def chat(self, content: str, max_tokens: int = 6000, reasoning: str = "medium", **kwargs) -> str:
        """Send chat request via the Responses API, initializing client if needed."""
        self._ensure_client()

        if self._client is None:
            raise RuntimeError(f"{self.name} not configured (set {self._var_name})")

        sysmsg, usermsg = llm._split_system_user(content)

        try:
            create_kwargs = {
                "instructions": sysmsg,
                "model": self._model_name,
                "input": usermsg,
                "max_output_tokens": max_tokens,
                "reasoning": {"effort": reasoning},
                "prompt_cache_key": os.environ.get("OPENAI_PROMPT_CACHE_KEY", llm._stable_cache_key("openai", self._model_name, sysmsg)),
            }
            # GPT-5.5 supports only 24h; GPT-5.4 also supports extended retention.
            if self._model_name.startswith(("gpt-5.5", "gpt-5.4")):
                create_kwargs["prompt_cache_retention"] = "24h"

            create_kwargs.update(kwargs)

            response = self._client.responses.create(**create_kwargs)

            usage = getattr(response, "usage", None)
            if usage:
                input_tokens = getattr(usage, "input_tokens", None)
                output_tokens = getattr(usage, "output_tokens", None)
                total_tokens = getattr(usage, "total_tokens", None)
                details = getattr(usage, "input_tokens_details", None)
                cached_tokens = getattr(details, "cached_tokens", None) if details else None

                logger.info(
                    f"[LLM_USAGE] provider={self._name} model={self._model_name} "
                    f"input_tokens={input_tokens} output_tokens={output_tokens} "
                    f"total_tokens={total_tokens} cached_tokens={cached_tokens}"
                )

            raw = response.output_text or ""
            llm._log_raw(self._name, self._model_name, raw)
            return self._clean_text(raw)
        except Exception as e:
            logger.exception(f"[OpenAIProviderImpl.chat]: Exception while communicating with LLM: {e}")
            return ""
