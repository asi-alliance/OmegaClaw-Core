"""
Test: agent invokes the (metta ...) skill on explicit request.

The metta skill executes a MeTTa s-expression inside the agent. We ask the
agent to evaluate a tiny self-chosen MeTTa expression and report the result;
we accept any (metta ...) call and a follow-up (send ...) that references
the result. Agent can pick whichever expression it wants — the goal is to
exercise the skill, not to grade MeTTa semantics.

Run:
    pytest test_skill_metta.py -s
"""
import re

from helpers import (
    Checker, find_skill_calls, make_prompt, send_prompt,
    wait_for_skill_call, wait_for_skill_match,
)


# Phrases that indicate the metta skill failed instead of returning a real
# evaluation result. If any of these are in the agent's send, the test
# should not pass.
ERROR_MARKERS = (
    "metta failed", "metta-failed", "skill failed",
    "metta error", "evaluation failed", "evaluation error",
    "error:", "failed:", "delivery failed", "delivery error",
)


def test_skill_metta():
    with Checker("metta skill invocation") as c:
        print(f"\n=== Omega: metta skill (run-id {c.run_id}) ===", flush=True)

        c.step("send prompt asking agent to use metta skill")
        prompt = make_prompt(
            c.run_id,
            "Please demonstrate your `metta` skill: pick any short MeTTa "
            "expression you like, evaluate it via the metta skill, and tell "
            "me what it returned. One short reply is enough.",
        )
        if not send_prompt(prompt):
            c.fail("irc", "could not deliver prompt within 60s")
        c.ok("irc", f"run-id={c.run_id}")

        c.step("verify agent invoked (metta ...)")
        metta_arg = wait_for_skill_call(c.run_id, "metta", timeout=60)
        if metta_arg is None:
            c.fail("metta invoked", "no (metta ...) call within 240s")
        c.ok("metta invoked", f"arg={metta_arg[:80]!r}")

        c.step("verify agent's reply references the actual metta result")
        # Without this check, a barebones "I evaluated metta" send with no
        # actual value would pass — masking cases where the metta evaluator
        # silently returned nothing. Require the send to either contain a
        # digit (the most common simple-expression result) or one of the
        # explicit "result/return" phrases AND not be an error report.
        def has_metta_result(s):
            low = s.lower()
            if any(em in low for em in ERROR_MARKERS):
                return False
            mentions_metta = (
                "metta" in low
                or "evaluat" in low
                or "result" in low
                or "returned" in low
                or "expression" in low
            )
            has_value = bool(re.search(r"\d", s)) or "()" in s or "true" in low or "false" in low
            return mentions_metta and has_value
        send_arg = wait_for_skill_match(
            c.run_id, "send", has_metta_result, timeout=120,
        )
        if send_arg is None:
            sends = find_skill_calls(c.run_id, "send") or []
            last = sends[-1] if sends else "<none>"
            c.fail(
                "send result",
                f"no send referenced an actual metta result. "
                f"Got {len(sends)} send(s), last: {last!r}",
            )
        c.ok("send result", f"reply={send_arg[:120]!r}")

        c.done()
