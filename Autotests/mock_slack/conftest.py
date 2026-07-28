"""Pytest fixtures for the Slack mock test suite.

Architecture mirrors mock_telegram but for Slack: a second Slack bot
("driver") posts prompts into a shared channel where the agent bot is
also a member. The agent's `channels/slack.py` polls
`conversations.history` and routes the driver's messages through its
normal auth gate.

LLM responses are still mocked through the shared LlmMockController from
Autotests/mock/ — only the transport differs.

Required env vars for live runs:
- SL_DRIVER_TOKEN     — Bot User OAuth Token (xoxb-...) of the driver app
- SL_CHANNEL_ID       — channel id where both bots are members (C0...)
- SL_AGENT_USER_ID    — bot user id of the agent app (U0...)
- OMEGACLAW_AUTH_SECRET — agent auth secret (default 0000)
"""
import os
import sys

import pytest

_MOCK_DIR = os.path.normpath(os.path.join(os.path.dirname(__file__), "..", "mock"))
if _MOCK_DIR not in sys.path:
    sys.path.insert(0, _MOCK_DIR)

_SELF_DIR = os.path.dirname(__file__)
if _SELF_DIR not in sys.path:
    sys.path.insert(0, _SELF_DIR)

from llm import LlmMockController, LLM_MOCK_PORT  # noqa: E402

from real_driver import SlackRealDriver  # noqa: E402


AUTH_SECRET = os.environ.get("OMEGACLAW_AUTH_SECRET") or "0000"


@pytest.fixture(scope="session")
def llm():
    controller = LlmMockController(("0.0.0.0", LLM_MOCK_PORT))
    try:
        yield controller
    finally:
        controller.stop(5)


@pytest.fixture(scope="session")
def sl():
    driver_token = os.environ.get("SL_DRIVER_TOKEN")
    channel_id = os.environ.get("SL_CHANNEL_ID")
    agent_user_id = os.environ.get("SL_AGENT_USER_ID")
    if not (driver_token and channel_id and agent_user_id):
        pytest.skip(
            "SL_DRIVER_TOKEN, SL_CHANNEL_ID and SL_AGENT_USER_ID env vars "
            "are required (see Autotests/mock_slack/conftest.py docstring)"
        )
    driver = SlackRealDriver(driver_token, channel_id, agent_user_id)
    try:
        yield driver
    finally:
        driver.stop(5)


@pytest.hookimpl(hookwrapper=True)
def pytest_runtest_makereport(item, call):
    outcome = yield
    report = outcome.get_result()
    if report.when != "call":
        return
    sl = item.funcargs.get("sl")
    if sl is None or not hasattr(sl, "mirror"):
        return
    status = "PASS" if report.passed else ("FAIL" if report.failed else "SKIP")
    sl.mirror(f"{status} {item.name}")


@pytest.fixture(scope="session", autouse=True)
def _sl_authenticate(sl):
    """Bind the driver bot as the agent's authenticated owner.

    First sender of `auth <secret>` becomes the owner. Doing this once
    per session is enough — subsequent injects use the same driver bot.
    """
    sl.inject_user_message(f"auth {AUTH_SECRET}")
    print(f"[conftest] sent auth secret; waiting up to 30s for agent confirmation",
          flush=True)
    chat_id, text = sl.pop_agent_reply(timeout=30)
    if text is None:
        print("[conftest] no agent reply to auth (likely already authenticated "
              "from a prior run); proceeding", flush=True)
    else:
        print(f"[conftest] agent confirmed auth: chat={chat_id} text={text!r}",
              flush=True)
    extras = sl.drain_agent_replies(max_wait=3)
    if extras:
        print(f"[conftest] drained {len(extras)} extra agent replies post-auth",
              flush=True)
    yield
