"""
Test: agent invokes (pin ...) to track multi-step task state.

Per system prompt the agent is taught: "use only pin for task state, and
remember for items that could be valuable in the future". So we give a
multi-step task with an explicit *current step*, and expect a (pin ...)
call that captures the running progress (a step number, the running task
name, or a "done/todo" marker).

We do NOT verify the literal content of the pin — different models pin
different phrasings. We only verify that pin was called in this turn AND
that its argument references either our run-id or a step keyword.

Run:
    pytest test_skill_pin.py -s
"""
from helpers import (
    Checker, find_skill_calls, make_prompt, send_prompt,
    wait_for_skill_call, wait_for_skill_match,
)


STEP_KEYWORDS = ("step", "alpha", "beta", "gamma", "restart", "server", "done")


def test_skill_pin():
    with Checker("pin skill invocation") as c:
        print(f"\n=== Omega: pin skill (run-id {c.run_id}) ===", flush=True)

        c.step("send a multi-step task that needs pinning")
        prompt = make_prompt(
            c.run_id,
            "I'm restarting three servers in order: alpha, beta, gamma. "
            "I just finished restarting alpha. Use the `pin` skill to keep "
            "track of where I am in this checklist so we don't lose state, "
            "and acknowledge with one short send.",
        )
        if not send_prompt(prompt):
            c.fail("irc", "could not deliver prompt within 60s")
        c.ok("irc", f"run-id={c.run_id}")

        c.step("verify agent invoked (pin ...) with task-state content")
        def is_task_state_pin(arg):
            low = arg.lower()
            return any(kw in low for kw in STEP_KEYWORDS) or str(c.run_id) in arg
        pin_arg = wait_for_skill_match(
            c.run_id, "pin", is_task_state_pin, timeout=60,
        )
        if pin_arg is None:
            calls = find_skill_calls(c.run_id, "pin") or []
            c.fail(
                "pin invoked",
                f"no (pin ...) referencing servers/steps. "
                f"Got {len(calls)} calls, first: {[a[:80] for a in calls[:3]]}",
            )
        matched = [kw for kw in STEP_KEYWORDS if kw in pin_arg.lower()]
        c.ok("pin invoked", f"matched={matched}, arg={pin_arg[:80]!r}")

        c.step("verify agent acknowledged via (send ...)")
        send_arg = wait_for_skill_call(c.run_id, "send", timeout=60)
        if send_arg is None:
            c.fail("send invoked", "agent did not acknowledge via send")
        c.ok("send invoked", f"reply={send_arg[:80]!r}")

        c.done()
