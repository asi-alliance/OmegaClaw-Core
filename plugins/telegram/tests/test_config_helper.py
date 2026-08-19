import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import asyncio
import config_helper as ch


class _FakeClient:
    def __init__(self, moderations): self.moderations = moderations


class _FakeCategoryScores:
    def __init__(self, scores): self._scores = scores
    def model_dump(self): return self._scores

class _FakeModerationResult:
    def __init__(self, scores): self.category_scores = _FakeCategoryScores(scores)

class _FakeModerationResponse:
    def __init__(self, scores): self.results = [_FakeModerationResult(scores)]

class _FakeModerations:
    def __init__(self, scores): self._scores = scores
    async def create(self, input): return _FakeModerationResponse(self._scores)

class _FakeModerationsNoCall:
    async def create(self, input):
        raise AssertionError("moderations.create should not be called")


def test_is_category_blocked_blocked_path():
    orig = ch._get_openai_client
    ch._get_openai_client = lambda: _FakeClient(_FakeModerations({"violence": 0.95}))
    try:
        result = asyncio.run(ch.is_category_blocked("I will hurt you"))
        assert result is True, result
    finally:
        ch._get_openai_client = orig


def test_is_category_blocked_allowed_path():
    orig = ch._get_openai_client
    scores = {"violence": 0.01, "harassment": 0.01, "hate": 0.01, "self-harm": 0.01, "sexual/minors": 0.01}
    ch._get_openai_client = lambda: _FakeClient(_FakeModerations(scores))
    try:
        result = asyncio.run(ch.is_category_blocked("what a nice day"))
        assert result is False, result
    finally:
        ch._get_openai_client = orig


def test_is_category_blocked_empty_text_no_network():
    orig = ch._get_openai_client
    ch._get_openai_client = lambda: _FakeClient(_FakeModerationsNoCall())
    try:
        assert asyncio.run(ch.is_category_blocked("")) is False
        assert asyncio.run(ch.is_category_blocked("   ")) is False
    finally:
        ch._get_openai_client = orig


def test_client_not_built_at_import():
    # Regression: config_helper is imported whenever the plugin loads,
    # independent of which channel is active, so import must not eagerly
    # build a client (which would require OPENAI_API_KEY to be set).
    assert ch._openai_client is None or hasattr(ch._openai_client, "moderations")


def test_llm_classify_falls_back_without_key():
    # No OPENAI_API_KEY at all: client construction fails inside the try
    # block, so _llm_classify must fall back to use_model rather than raise.
    # use_model also has no key, so it degrades to False. Calls _llm_classify
    # directly (not is_category_blocked) with a non-empty category list, since
    # the profile ships no blocked_categories and an empty list short-circuits
    # before the client is ever touched.
    orig_client, orig_key = ch._openai_client, os.environ.pop("OPENAI_API_KEY", None)
    ch._openai_client = None
    try:
        result = asyncio.run(ch._llm_classify("I will hurt you", ["violence"]))
        assert result is False, result
    finally:
        ch._openai_client = orig_client
        if orig_key is not None:
            os.environ["OPENAI_API_KEY"] = orig_key


def test_get_spam_protection_config_keys():
    config = ch.get_spam_protection_config()
    expected_keys = {"time_window", "message_limit", "cooldown_duration", "admin_alert_threshold"}
    assert set(config.keys()) == expected_keys, config


def test_get_spam_protection_config_defaults_when_absent():
    orig_cache = ch._config_cache
    ch._config_cache = {}
    try:
        config = ch.get_spam_protection_config()
        assert config == {
            "time_window": 10,
            "message_limit": 5,
            "cooldown_duration": 120,
            "admin_alert_threshold": 3,
        }, config
    finally:
        ch._config_cache = orig_cache


if __name__ == "__main__":
    test_is_category_blocked_blocked_path()
    test_is_category_blocked_allowed_path()
    test_is_category_blocked_empty_text_no_network()
    test_client_not_built_at_import()
    test_llm_classify_falls_back_without_key()
    test_get_spam_protection_config_keys()
    test_get_spam_protection_config_defaults_when_absent()
    print("all config_helper tests passed")
