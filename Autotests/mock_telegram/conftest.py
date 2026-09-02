"""Pytest fixtures for the Telegram test suite.

Transport: bot-to-bot via real api.telegram.org. A second "driver" bot
plays the test user. The driver sends `sendMessage(@agent, ...)` to the
agent bot and reads the agent's replies through its own `getUpdates`
inbox. Both bots must be opted into bot-to-bot mode in BotFather
(Bot API 10.0, May 2026).

Required environment:
- `TG_DRIVER_TOKEN`    — driver bot token (separate from the agent bot).
- `TG_BOT_TOKEN`       — agent bot token. The agent's @username is
                         auto-derived from this via Telegram's `getMe`
                         endpoint; alternatively set `TG_AGENT_USERNAME`
                         explicitly to skip the network probe.
- `TG_AGENT_USERNAME`  — optional override; if set, takes precedence
                         over the `getMe` auto-derivation.
- `TG_MIRROR_CHAT_ID`  — optional; chat id to mirror the bot-to-bot
                         conversation and per-test PASS/FAIL/SKIP lines.

The LLM mock (`LlmMockController` on tcp:9765) is shared with the IRC
mock suite — the agent uses the Test provider for deterministic answers;
only the message-delivery transport differs.

The autouse `_tg_authenticate` fixture sends `auth <secret>` once as the
driver bot so subsequent injects pass the adapter's first-user auth gate.
"""
import json
import os
import sys
import urllib.error
import urllib.request

import pytest

# Reuse the LLM mock harness from Autotests/mock/ without duplicating its code.
_MOCK_DIR = os.path.normpath(os.path.join(os.path.dirname(__file__), "..", "mock"))
if _MOCK_DIR not in sys.path:
    sys.path.insert(0, _MOCK_DIR)

# Allow this directory to import its own siblings (real_driver.py).
_SELF_DIR = os.path.dirname(__file__)
if _SELF_DIR not in sys.path:
    sys.path.insert(0, _SELF_DIR)

from llm import LlmMockController  # noqa: E402
from llm import LLM_MOCK_PORT as LLM_PORT_DEFAULT  # noqa: E402

from real_driver import RealTgDriver  # noqa: E402


AUTH_SECRET = os.environ.get("OMEGA_AUTH_SECRET") or "0000"


def _agent_username_from_bot_token(token):
    """Probe `https://api.telegram.org/bot<token>/getMe` and return the
    bot's `username` (without @), or `None` if the lookup fails."""
    if not token:
        return None
    url = f"https://api.telegram.org/bot{token}/getMe"
    try:
        with urllib.request.urlopen(url, timeout=10) as resp:
            data = json.loads(resp.read().decode("utf-8", errors="ignore"))
    except (urllib.error.URLError, json.JSONDecodeError, OSError) as exc:
        print(f"[conftest] getMe probe failed: {exc}", flush=True)
        return None
    if not data.get("ok"):
        print(f"[conftest] getMe returned not-ok: {data}", flush=True)
        return None
    return (data.get("result") or {}).get("username")


@pytest.fixture(scope="session")
def llm():
    controller = LlmMockController(("0.0.0.0", LLM_PORT_DEFAULT))
    try:
        yield controller
    finally:
        controller.stop(5)


@pytest.fixture(scope="session")
def tg():
    driver_token = os.environ.get("TG_DRIVER_TOKEN")
    if not driver_token:
        pytest.skip(
            "Telegram autotests require TG_DRIVER_TOKEN env var "
            "(see Autotests/mock_telegram/README.md)"
        )
    agent_username = os.environ.get("TG_AGENT_USERNAME")
    if not agent_username:
        derived = _agent_username_from_bot_token(os.environ.get("TG_BOT_TOKEN"))
        if not derived:
            pytest.skip(
                "Cannot determine the agent bot's username. Either set "
                "TG_AGENT_USERNAME explicitly, or set TG_BOT_TOKEN so the "
                "harness can derive it via Telegram's getMe endpoint."
            )
        agent_username = derived
        print(f"[conftest] derived TG_AGENT_USERNAME={agent_username!r} "
              f"via getMe", flush=True)
    mirror_chat_id = os.environ.get("TG_MIRROR_CHAT_ID") or None
    driver = RealTgDriver(driver_token, agent_username,
                          mirror_chat_id=mirror_chat_id)
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
    tg = item.funcargs.get("tg")
    if tg is None or not hasattr(tg, "mirror"):
        return
    status = "PASS" if report.passed else ("FAIL" if report.failed else "SKIP")
    tg.mirror(f"{status} {item.name}")


@pytest.fixture(scope="session", autouse=True)
def _tg_authenticate(tg):
    """Bind the driver bot as the authenticated owner of the agent's TG channel.

    The adapter's first-user auth gate accepts the first sender of
    `auth <secret>`; later senders are ignored. Doing this once per session
    is enough — all later injects use the same sender.
    """
    tg.inject_user_message(f"auth {AUTH_SECRET}")
    print(f"[conftest] sent auth secret; waiting up to 30s for agent confirmation",
          flush=True)
    # If the agent was already authenticated from a previous pytest run against
    # the same container, the adapter silently ignores the second auth — no
    # reply is sent. A short window is enough; tests will surface a real auth
    # failure on their own prompts anyway.
    chat_id, text = tg.pop_agent_reply(timeout=30)
    if text is None:
        print("[conftest] no agent reply to auth (likely already authenticated "
              "from a prior run); proceeding", flush=True)
    else:
        print(f"[conftest] agent confirmed auth: chat={chat_id} text={text!r}", flush=True)
    # Soak any extra greetings.
    extras = tg.drain_agent_replies(max_wait=3)
    if extras:
        print(f"[conftest] drained {len(extras)} extra agent replies post-auth", flush=True)
    yield
