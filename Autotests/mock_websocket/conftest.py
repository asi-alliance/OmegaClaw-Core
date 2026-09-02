"""Pytest fixtures for the WebSocket test suite.

Transport: the agent's WebSocket channel (`channels/wschat.py`) connects to a
local mock server (`WsMockDriver`) that stands in for the ASI Create chat, so
no external service participates. The LLM is the deterministic Test provider,
shared with the other mock suites via `LlmMockController` on tcp:9765.

There is no message-level `auth <secret>` step: WebSocket auth is the handshake
bearer token (`Bearer test-token`), checked by the mock server on connect.

Mock-only speedups (as in mock/conftest.py): drop the live Checker teardown's
IRC cancel + 15s sleep and lower POLL, leaving Autotests/helpers.py untouched
for live runs.
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

import helpers  # noqa: E402
from llm import LlmMockController, LLM_MOCK_PORT  # noqa: E402
from ws_driver import WsMockDriver  # noqa: E402


WS_MOCK_PORT = int(os.environ.get("WS_MOCK_PORT") or 8770)
WS_TOKEN = os.environ.get("WS_TOKEN") or "test-token"


def _mock_checker_exit(self, _exc_type, _exc_val, _exc_tb):
    self.step("teardown: cleanup test artifacts")
    for path in self._cleanup_dirs:
        helpers.cleanup_dir(path)
        if helpers.dexec("test", "-e", path).returncode == 0:
            print(f"       [WARN] {path} still exists", flush=True)
        else:
            print(f"       removed {path}", flush=True)
    h_removed = helpers.history_cleanup_by_markers(self._cleanup_markers)
    print(f"       history: {h_removed} blocks removed", flush=True)
    c_removed = helpers.chromadb_cleanup_by_markers(self._cleanup_markers)
    print(f"       chromadb: {c_removed} vectors removed", flush=True)
    return False


helpers.POLL = 0.5
helpers.Checker.__exit__ = _mock_checker_exit


@pytest.fixture(scope="session")
def llm():
    controller = LlmMockController(("0.0.0.0", LLM_MOCK_PORT))
    try:
        yield controller
    finally:
        controller.stop(5)


@pytest.fixture(scope="session")
def ws():
    driver = WsMockDriver(WS_MOCK_PORT, token=WS_TOKEN)
    try:
        yield driver
    finally:
        driver.stop(5)
