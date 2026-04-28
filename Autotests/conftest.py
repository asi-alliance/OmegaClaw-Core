"""
Session-level cleanup: after the entire pytest session finishes, re-run the
legacy cleanup to catch any test artifacts the agent wrote AFTER per-test
teardown ran (agent is autonomous and may produce `remember` calls with a
delay).
"""
import time

import pytest

from cleanup_legacy import LEGACY_MARKERS
from helpers import (
    chromadb_cleanup_by_markers, history_cleanup_by_markers,
)


@pytest.fixture(scope="session", autouse=True)
def _post_session_cleanup():
    yield
    print("\n>> post-session cleanup (grace period 15s)", flush=True)
    time.sleep(15)
    h = history_cleanup_by_markers(LEGACY_MARKERS)
    c = chromadb_cleanup_by_markers(LEGACY_MARKERS)
    print(f"   [final] history={h} blocks, chromadb={c} vectors", flush=True)
