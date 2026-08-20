import os
import sys
import types

_HERE = os.path.dirname(os.path.abspath(__file__))
_PLUGIN_DIR = os.path.dirname(_HERE)
_REPO_ROOT = os.path.dirname(os.path.dirname(_PLUGIN_DIR))

for _path in (_REPO_ROOT, os.path.join(_REPO_ROOT, "src"), _PLUGIN_DIR):
    sys.path.insert(0, _path)

os.environ.setdefault("OPENAI_API_KEY", "test-key")

import gateway
import vision
import media_handler as mh


def _with_gateway(url):
    """Point gateway.gateway_url at `url` and return a restore function."""
    original = gateway.gateway_url
    gateway.gateway_url = lambda: url
    return lambda: setattr(gateway, "gateway_url", original)


def test_direct_calls_read_the_key_from_the_environment():
    restore = _with_gateway("")
    os.environ["OPENROUTER_API_KEY"] = "sk-direct"
    try:
        base, key = gateway.upstream("openrouter", "https://openrouter.ai/api/v1",
                                      "OPENROUTER_API_KEY")
        assert base == "https://openrouter.ai/api/v1", base
        assert key == "sk-direct", key
    finally:
        restore()
        del os.environ["OPENROUTER_API_KEY"]


def test_missing_key_is_reported_rather_than_guessed():
    restore = _with_gateway("")
    os.environ.pop("SOME_ABSENT_KEY", None)
    try:
        base, key = gateway.upstream("openrouter", "https://x/", "SOME_ABSENT_KEY")
        assert key is None, key
    finally:
        restore()


def test_behind_the_proxy_no_key_is_needed():
    """The entrypoint scrubs every API key and the proxy holds them instead, so
    code inside the container has nothing to read. Calls must go to the proxy."""
    restore = _with_gateway("http://localhost:8080")
    os.environ.pop("OPENROUTER_API_KEY", None)
    try:
        base, key = gateway.upstream("openrouter", "https://openrouter.ai/api/v1",
                                      "OPENROUTER_API_KEY")
        assert base == "http://localhost:8080/openrouter/", base
        assert key == gateway.PROXY_KEY, key
    finally:
        restore()


def test_vision_client_targets_the_proxy_route():
    """describe-image must work with no ANTHROPIC_API_KEY in the environment."""
    restore = _with_gateway("http://localhost:8080")
    saved = os.environ.pop("ANTHROPIC_API_KEY", None)
    created = {}

    fake_openai = types.ModuleType("openai")

    class _Client:
        def __init__(self, api_key=None, base_url=None):
            created["api_key"] = api_key
            created["base_url"] = base_url

    fake_openai.OpenAI = _Client
    real_openai = sys.modules.get("openai")
    sys.modules["openai"] = fake_openai
    try:
        vision._make_client()
        assert created["base_url"] == "http://localhost:8080/anthropic/", created
        assert created["api_key"] == gateway.PROXY_KEY, created
    finally:
        if real_openai is not None:
            sys.modules["openai"] = real_openai
        else:
            del sys.modules["openai"]
        if saved is not None:
            os.environ["ANTHROPIC_API_KEY"] = saved
        restore()


def test_image_generation_posts_to_the_proxy_route():
    restore = _with_gateway("http://localhost:8080")
    saved = os.environ.pop("OPENROUTER_API_KEY", None)
    posted = {}

    fake_requests = types.ModuleType("requests")

    class _Resp:
        def raise_for_status(self): pass
        def json(self): return {"data": [{"b64_json": "AAAA"}]}

    def _post(url, headers=None, json=None, timeout=None):
        posted["url"] = url
        return _Resp()

    fake_requests.post = _post
    real_requests = sys.modules.get("requests")
    sys.modules["requests"] = fake_requests
    try:
        out = mh._generate_image_bytes("a red panda")
        assert out is not None, "generation must succeed behind the proxy"
        assert posted["url"] == "http://localhost:8080/openrouter/images", posted
    finally:
        if real_requests is not None:
            sys.modules["requests"] = real_requests
        else:
            del sys.modules["requests"]
        if saved is not None:
            os.environ["OPENROUTER_API_KEY"] = saved
        restore()


if __name__ == "__main__":
    test_direct_calls_read_the_key_from_the_environment()
    test_missing_key_is_reported_rather_than_guessed()
    test_behind_the_proxy_no_key_is_needed()
    test_vision_client_targets_the_proxy_route()
    test_image_generation_posts_to_the_proxy_route()
    print("all gateway tests passed")
