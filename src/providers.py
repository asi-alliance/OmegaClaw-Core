import logging

logger = logging.getLogger(__name__)

_llmProviderRegistry = {}

class LLMProvider:
    """LLM provider implementation"""

    def config(self, config: dict) -> None:
        """Configure LLM provider. Receives the subset of the command line
        parameters or configuration file keys which are started by "<id>_"
        prefix"""
        raise NotImplementedError()

    def chat(self, prompt: str, max_tokens: int = 6000, reasoning_mode: str = "medium") -> str:
        """Chat with LLM provider"""
        raise NotImplementedError()

def registerLLMProvider(id: str, provider: LLMProvider) -> None:
    """Register LLM provider in the registry"""
    global _llmProviderRegistry
    logger.info(f"registerLLMProvider: registering LLM provider {id}")
    _llmProviderRegistry[id] = provider

_llmprovider: LLMProvider = None

def llmProviderConfig(provider, config):
    """Select and configure one of the LLM providers registered by plugins"""
    global _llmprovider
    _llmprovider = _llmProviderRegistry.get(provider, None)
    if _llmprovider is None:
        _error("llmProviderConfig", f"LLM provider plugin {provider} is not registered")
    _llmprovider.config(config)

def llmProviderChat(prompt, max_tokens, reasoning_mode):
    """Chat via selected LLM provider"""
    global _llmprovider
    return _llmprovider.chat(prompt, max_tokens, reasoning_mode)
