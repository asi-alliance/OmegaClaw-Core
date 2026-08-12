"""Unit tests for the WebSocket chat adapter (channels/wschat.py).

Pure-Python, no live server / no ``websockets`` package needed: the send path is monkeypatched,
so importing this exercises only stdlib. Runs under pytest and standalone
(`python3 Autotests/test_wschat.py`). Focused on the outbox flush semantics (regression for the
mid-flush message-loss bug found in PR #43 review).
"""
import os
import sys

_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
for _p in (os.path.join(_REPO_ROOT, "channels"), _REPO_ROOT):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import wschat  # noqa: E402


def _reset():
    wschat._outbox.clear()
    wschat._inbox.clear()


def test_drain_outbox_does_not_drop_unsent_after_midflush_failure():
    """Regression (PR #43 review): if a send fails midway through the flush, the failed payload
    AND all later unsent payloads must be requeued in order — none silently dropped."""
    _reset()
    for i in (1, 2, 3):
        wschat._outbox.append({"id": i})

    calls = []
    orig = wschat._send_json

    def flaky(payload, ws=None):
        calls.append(payload["id"])
        if payload["id"] == 2:
            raise RuntimeError("boom")

    wschat._send_json = flaky
    try:
        try:
            wschat._drain_outbox(ws="x")
        except RuntimeError:
            pass
        assert calls == [1, 2], calls
        # 2 (failed) and 3 (never attempted) are both preserved, in original order
        assert [p["id"] for p in wschat._outbox] == [2, 3], list(wschat._outbox)
    finally:
        wschat._send_json = orig
        _reset()


def test_drain_outbox_preserves_concurrent_enqueue_on_midflush_failure():
    """Regression (PR #264 review): the outbox lock is released during the send loop, so
    send_message() can enqueue a newer payload into the (cleared) outbox. A mid-flush failure
    must requeue the unsent tail WITHOUT silently displacing that concurrently-enqueued message,
    even when the tail fills deque(maxlen)."""
    _reset()
    # Full outbox so the requeued tail alone reaches maxlen — the overflow edge.
    for i in range(wschat._outbox.maxlen):
        wschat._outbox.append({"id": i})

    orig = wschat._send_json

    def flaky(payload, ws=None):
        # Fail on the very first send: the entire tail must be requeued. Simulate a concurrent
        # send_message() falling back to the outbox mid-flush (lock is free here).
        if payload["id"] == 0:
            wschat._outbox.append({"id": "CONCURRENT"})
            raise RuntimeError("boom")

    wschat._send_json = flaky
    try:
        try:
            wschat._drain_outbox(ws="x")
        except RuntimeError:
            pass
        ids = [p["id"] for p in wschat._outbox]
        assert "CONCURRENT" in ids, ids
        # Newer message kept; oldest tail entry dropped on overflow (FIFO, newest-wins).
        assert ids[-1] == "CONCURRENT", ids
        assert len(wschat._outbox) == wschat._outbox.maxlen, len(wschat._outbox)
    finally:
        wschat._send_json = orig
        _reset()


def test_drain_outbox_clears_on_full_success():
    _reset()
    for i in (1, 2, 3):
        wschat._outbox.append({"id": i})
    sent = []
    orig = wschat._send_json
    wschat._send_json = lambda payload, ws=None: sent.append(payload["id"])
    try:
        wschat._drain_outbox(ws="x")
        assert sent == [1, 2, 3]
        assert list(wschat._outbox) == []
    finally:
        wschat._send_json = orig
        _reset()


if __name__ == "__main__":
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_") and callable(v)]
    failed = 0
    for fn in fns:
        try:
            fn()
            print("ok:", fn.__name__)
        except AssertionError as e:
            failed += 1
            print("FAIL:", fn.__name__, e)
    if failed:
        sys.exit(1)
    print("\nAll {} wschat tests passed".format(len(fns)))
