"""
Test: a chat prompt is appended to history.metta as an s-expression record
that quotes our REQ-tag, together with the agent's skill-invocation response.

Notes on format: the new agent writes history as top-level s-exp records
`("YYYY-MM-DD HH:MM:SS" (...skills...))`. The old `HUMAN_MESSAGE:` line
format is no longer emitted — we anchor on the REQ-tag the agent echoes
back in a skill argument.

Run:
    pytest test_memory_history.py -s
"""
import time

from helpers import (
    HISTORY_FILE, Checker, _history_block_for_run_id, find_skill_calls,
    get_mtime, get_size, make_prompt, read_history, send_prompt,
    wait_for_skill_call,
)


def test_memory_history():
    with Checker("history append") as c:
        print(f"\n=== OmegaClaw: history append (run-id {c.run_id}) ===", flush=True)

        c.step("capture initial history state")
        mtime_before = get_mtime(HISTORY_FILE)
        size_before = get_size(HISTORY_FILE)
        if mtime_before is None or size_before is None:
            c.fail("history", f"{HISTORY_FILE} missing or inaccessible")
        c.ok("history initial", f"mtime={mtime_before}, size={size_before}")

        time.sleep(2)

        c.step("send prompt via IRC")
        prompt = make_prompt(
            c.run_id,
            f"Acknowledge with one short line that you received marker {c.run_id}.",
        )
        if not send_prompt(prompt):
            c.fail("irc", "could not deliver prompt within 60s")
        c.ok("irc", f"run-id={c.run_id}")

        c.step("verify history contains an s-exp record quoting our REQ-tag")
        deadline = time.time() + 180
        block = None
        while time.time() < deadline:
            block = _history_block_for_run_id(read_history(), c.run_id)
            if block:
                break
            time.sleep(2)
        if not block:
            c.fail("history record", "no s-exp record referencing REQ-{run_id}")
        c.ok("history record", f"{len(block)} chars since first REQ-{c.run_id}")

        c.step("verify history contains (send ...) or (pin ...) for our run_id")
        send_arg = wait_for_skill_call(c.run_id, "send", timeout=120)
        pin_calls = find_skill_calls(c.run_id, "pin") or []
        if send_arg is None and not pin_calls:
            c.fail(
                "agent s-exp",
                "no (send ...) or (pin ...) call recorded in history for our run_id",
            )
        c.ok(
            "agent s-exp",
            f"send={'yes' if send_arg else 'no'}, pin={len(pin_calls)}",
        )

        c.step("check history mtime and size grew")
        mtime_after = get_mtime(HISTORY_FILE)
        size_after = get_size(HISTORY_FILE)
        if mtime_after is None or mtime_after <= mtime_before:
            c.fail("history mtime", f"before={mtime_before}, after={mtime_after}")
        if size_after is None or size_after <= size_before:
            c.fail("history size", f"before={size_before}, after={size_after}")
        c.ok(
            "history grew",
            f"mtime {mtime_before}->{mtime_after}, "
            f"size +{size_after - size_before} bytes",
        )

        c.done()
