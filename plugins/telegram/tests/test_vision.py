import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import vision as ov


class _FakeMessage:
    def __init__(self, content): self.content = content

class _FakeChoice:
    def __init__(self, content): self.message = _FakeMessage(content)

class _FakeResp:
    def __init__(self, content): self.choices = [_FakeChoice(content)]

class _FakeCompletions:
    def __init__(self, captured): self._captured = captured
    def create(self, model, messages, **kwargs):
        self._captured["model"] = model
        self._captured["messages"] = messages
        self._captured.update(kwargs)
        return _FakeResp("a red panda")

class _FakeChat:
    def __init__(self, captured): self.completions = _FakeCompletions(captured)

class _FakeClient:
    def __init__(self, captured): self.chat = _FakeChat(captured)


def _clear_selection():
    for var in ("VISION_PROVIDER", "VISION_MODEL"):
        os.environ.pop(var, None)


def test_vision_chat_builds_multimodal_request():
    captured = {}
    _clear_selection()
    orig = ov._make_client
    ov._make_client = lambda: _FakeClient(captured)
    try:
        parts = [{"type": "image_url", "image_url": {"url": "data:image/jpeg;base64,AAAA"}}]
        out = ov.vision_chat(parts, "describe it")
        assert out == "a red panda", out
        content = captured["messages"][0]["content"]
        assert content[0] == {"type": "text", "text": "describe it"}, content
        assert content[1] == parts[0], content
        # Anthropic's compat endpoint rejects a request without max_tokens.
        assert captured["max_tokens"] == 1024, captured
    finally:
        ov._make_client = orig


def test_defaults_to_anthropic():
    _clear_selection()
    name, cfg = ov._config()
    assert name == "Anthropic", name
    assert cfg["key_env"] == "ANTHROPIC_API_KEY", cfg
    assert ov._model() == "claude-haiku-4-5-20251001", ov._model()


def test_provider_and_model_are_selectable():
    _clear_selection()
    os.environ["VISION_PROVIDER"] = "OpenRouter"
    try:
        name, cfg = ov._config()
        assert name == "OpenRouter", name
        assert cfg["base_url"] == "https://openrouter.ai/api/v1", cfg
        assert ov._model() == "anthropic/claude-haiku-4.5", ov._model()
        os.environ["VISION_MODEL"] = "some/other-model"
        assert ov._model() == "some/other-model", ov._model()
    finally:
        _clear_selection()


def test_unknown_provider_raises():
    _clear_selection()
    os.environ["VISION_PROVIDER"] = "Nope"
    try:
        raised = False
        try:
            ov._config()
        except RuntimeError:
            raised = True
        assert raised, "expected RuntimeError for an unknown VISION_PROVIDER"
    finally:
        _clear_selection()


def test_vision_chat_requires_key():
    _clear_selection()
    orig_key = os.environ.pop("ANTHROPIC_API_KEY", None)
    try:
        raised = False
        try:
            ov.vision_chat([{"type": "image_url", "image_url": {"url": "x"}}], "p")
        except RuntimeError:
            raised = True
        assert raised, "expected RuntimeError when key missing"
    finally:
        if orig_key is not None:
            os.environ["ANTHROPIC_API_KEY"] = orig_key


if __name__ == "__main__":
    test_vision_chat_builds_multimodal_request()
    test_defaults_to_anthropic()
    test_provider_and_model_are_selectable()
    test_unknown_provider_raises()
    test_vision_chat_requires_key()
    print("all vision tests passed")
