"""
Override the live suite's session-scoped cleanup with a no-op: these tests don't
write agent history or ChromaDB entries, so there is nothing to scrub.
"""
import pytest


@pytest.fixture(scope="session", autouse=True)
def _post_session_cleanup():
    yield
