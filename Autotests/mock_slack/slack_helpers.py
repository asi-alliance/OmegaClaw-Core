"""Slack-flavored thin wrappers over the shared test infrastructure.

Mirrors `Autotests/mock_telegram/tg_helpers.py`: shared helpers (Checker,
dexec, make_prompt, wait_for_*) are reused unchanged; only the per-channel
prompt delivery differs. Here `sl_send_prompt(sl, prompt)` has the driver
bot post `prompt` into the shared channel that the agent bot polls.
"""
import os
import sys

_PARENT = os.path.normpath(os.path.join(os.path.dirname(__file__), ".."))
if _PARENT not in sys.path:
    sys.path.insert(0, _PARENT)

from helpers import (  # noqa: E402, F401
    Checker,
    dexec,
    dexec_root,
    make_prompt,
    wait_for_file,
    wait_for_file_mtime_change,
    wait_for_history_keyword,
    wait_for_history_block,
    wait_for_skill_call,
    wait_for_any_skill_call,
    wait_for_skill_match,
    find_skill_calls,
    read_history,
    get_mtime,
    get_size,
)


def sl_send_prompt(sl_driver, prompt):
    """Have the driver bot post `prompt` into the shared Slack channel.

    The agent's `channels/slack.py` polls `conversations.history` and
    routes the message through its auth gate (driver was bound as owner
    in the session-scoped `_sl_authenticate` fixture).
    """
    sl_driver.inject_user_message(prompt)
    return True
