"""
Test: OmegaClaw invokes (search ...) for "SingularityNet" and gets relevant info.

Run:
    pytest test_search_basic.py -s
"""
from helpers import (
    Checker, make_prompt, send_prompt, wait_for_any_skill_call,
    wait_for_skill_call, wait_for_history_keyword, find_skill_calls,
)

SEARCH_SKILLS = ("search", "tavily-search")


def test_search_basic():
    with Checker("search singularitynet") as c:
        print(f"\n=== OmegaClaw: basic search (run-id {c.run_id}) ===", flush=True)

        c.step("send prompt via IRC")
        prompt = make_prompt(
            c.run_id,
            "What is SingularityNet? Search the web and give me a short description.",
        )
        if not send_prompt(prompt):
            c.fail("irc", "could not deliver prompt within 60s")
        c.ok("irc", f"run-id={c.run_id}")

        c.step("verify agent invoked a search skill (search or tavily-search)")
        skill, arg = wait_for_any_skill_call(
            c.run_id, SEARCH_SKILLS, timeout=180, arg_substr="singularity",
        )
        if arg is None:
            seen = {s: find_skill_calls(c.run_id, s) or [] for s in SEARCH_SKILLS}
            c.fail("search invoked", f"no search/tavily with 'singularity' arg. Got: {seen}")
        c.ok(f"{skill} invoked", f"arg={arg!r}")

        c.step("verify (send ...) skill contains SingularityNet keywords")
        send_matched = wait_for_history_keyword(
            c.run_id,
            ["singularitynet", "singularity", "agi", "blockchain",
             "decentralized", "marketplace", "goertzel"],
            timeout=60,
        )
        if send_matched is None:
            c.fail("send content", "agent did not relay SingularityNet info to user")
        c.ok("send content", f"matched: {', '.join(send_matched[:4])}")

        c.done()
