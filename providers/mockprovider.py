import os
import lib_llm_ext as llm
import providers

class MockProvider(providers.LLMProvider):

    def __init__(self):
        super().__init__()

    def start(self) -> None:
        self.delegate = MockProviderImpl()

    def stop(self) -> None:
        self.delegate.stop()

    def chat(self, prompt: str, max_tokens: int = 6000, reasoning_mode: str = "medium") -> str:
        return self.delegate.chat(prompt, max_tokens, reasoning_mode)

def loadOmegaPlugin():
    providers.registerLLMProvider("Test", MockProvider())

class MockProviderImpl(llm.AbstractAIProvider):
    """Test provider for mocking LLM output"""

    def __init__(self):
        super().__init__("Mockprovider")
        self._mock = None
        self._controller_ip = os.environ.get("TEST_SERVER_IP")

    def _llm_mock(self):
        if not self._mock:
            from Autotests.mock.llm import LlmMockAgent, LLM_MOCK_PORT
            self._mock = LlmMockAgent((self._controller_ip, LLM_MOCK_PORT))
        return self._mock

    @property
    def is_available(self) -> bool:
        return self._controller_ip is not None

    def chat(self, content: str, max_tokens: int = 6000, reasoning: str = "medium", **kwargs) -> str:
        return self._llm_mock().chat(content)

    def stop(self) -> None:
        if self._mock is not None:
            self._mock.stop(timeout=10)
            self._mock = None
