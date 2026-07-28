"""WebSocket-flavored thin wrappers over the shared IRC test infrastructure.

The shared `Autotests/helpers.py` is built around an IRC `send_prompt`. For the
WebSocket suite we substitute that with `ws_send_prompt(ws, prompt)`, which has
the mock WS server deliver a `user_message` frame to the agent.

Everything else — `Checker`, `dexec`, `wait_for_file`, history/skill waiters,
prompt envelope — is reused unchanged.
"""
import os
import sys

_PARENT = os.path.normpath(os.path.join(os.path.dirname(__file__), ".."))
if _PARENT not in sys.path:
    sys.path.insert(0, _PARENT)

from helpers import (  # noqa: E402, F401  (re-exported for tests)
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


def ws_send_prompt(ws_driver, prompt):
    """Deliver `prompt` to the agent over the mock WebSocket transport.

    Mirrors the role of `helpers.send_prompt` in the IRC suite — the mock
    server sends a `user_message` frame the agent picks up on its next drain.
    """
    ws_driver.inject_user_message(prompt)
    return True
