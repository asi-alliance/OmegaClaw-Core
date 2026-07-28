"""Unit test for channels/slack.py `_slack_unwrap`.

Pure function over text; no Slack API, no driver bot, no agent. The local
`sl` / `_sl_authenticate` fixtures shadow the session-scoped ones in
conftest.py so this file runs without SL_DRIVER_TOKEN, SL_CHANNEL_ID, or
SL_AGENT_USER_ID set.

Run:
    pytest test_slack_unwrap.py -s
"""
import os
import sys

import pytest

_PARENT = os.path.normpath(os.path.join(os.path.dirname(__file__), "..", ".."))
if _PARENT not in sys.path:
    sys.path.insert(0, _PARENT)

from channels.slack import _slack_unwrap  # noqa: E402


@pytest.fixture(scope="session")
def sl():
    yield None


@pytest.fixture(scope="session", autouse=True)
def _sl_authenticate(sl):
    yield


class TestSlackUnwrap:

    def test_empty(self):
        assert _slack_unwrap("") == ""

    def test_none(self):
        assert _slack_unwrap(None) is None

    def test_plain_passthrough(self):
        assert _slack_unwrap("plain text") == "plain text"

    def test_bare_url(self):
        assert _slack_unwrap("<https://example.com>") == "https://example.com"

    def test_url_with_display(self):
        assert _slack_unwrap("<https://example.com|click here>") == "click here"

    def test_mailto_with_display(self):
        assert _slack_unwrap("<mailto:a@b.com|email me>") == "email me"

    def test_html_entities(self):
        assert _slack_unwrap("&lt;tag&gt; &amp; more") == "<tag> & more"

    def test_mixed_url_and_entities(self):
        assert (_slack_unwrap("see <https://a.com|here> &amp; <https://b.com>")
                == "see here & https://b.com")

    def test_url_with_empty_display(self):
        assert _slack_unwrap("<https://a.com|>") == ""

    def test_entities_outside_url_wrappers(self):
        assert _slack_unwrap("a < b &amp;&amp; c > d") == "a < b && c > d"
