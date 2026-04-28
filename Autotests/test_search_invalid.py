"""
Test: OmegaClaw invokes (search ...) for gibberish and reports no results.

Run:
    pytest test_search_invalid.py -s
"""
from helpers import (
    Checker, find_skill_calls, make_prompt, send_prompt,
    wait_for_any_skill_call, wait_for_skill_call, wait_for_skill_match,
)

GIBBERISH = "dfghjkgkfjghj"
SEARCH_SKILLS = ("search", "tavily-search")


def test_search_invalid():
    with Checker("search invalid") as c:
        print(f"\n=== OmegaClaw: invalid search (run-id {c.run_id}) ===", flush=True)

        c.step("send prompt via IRC")
        prompt = make_prompt(
            c.run_id,
            f"What is {GIBBERISH}? Search the web. "
            "If nothing found, say so explicitly.",
        )
        if not send_prompt(prompt):
            c.fail("irc", "could not deliver prompt within 60s")
        c.ok("irc", f"run-id={c.run_id}")

        c.step(f"verify agent invoked search/tavily-search with '{GIBBERISH}'")
        skill, arg = wait_for_any_skill_call(
            c.run_id, SEARCH_SKILLS, timeout=180, arg_substr=GIBBERISH,
        )
        if arg is None:
            seen = {s: find_skill_calls(c.run_id, s) or [] for s in SEARCH_SKILLS}
            c.fail("search invoked", f"no search/tavily with gibberish arg. Got: {seen}")
        c.ok(f"{skill} invoked", f"arg={arg!r}")

        c.step("verify (send ...) message indicates no results / unknown term")
        # Agent typically emits a preliminary "will search..." reply first and
        # only a later (send ...) contains the actual conclusion. Scan *every*
        # send call in the response window and wait until one matches a
        # negation phrase — up to 240s because searches can be slow.
        no_result_phrases = [
            "no results", "not found", "couldn't find", "could not find",
            "no information", "no matches", "no relevant", "unable to find",
            "nothing found", "no meaning", "nonsense", "random",
            "gibberish", "meaningless", "does not appear", "doesn't appear",
            "no data", "no specific", "unknown", "no coherent",
            "no hits", "returned nothing", "returned no",
        ]

        def has_negation(s):
            low = s.lower()
            return any(p in low for p in no_result_phrases)

        send_arg = wait_for_skill_match(
            c.run_id, "send", has_negation, timeout=240,
        )
        if send_arg is None:
            all_sends = find_skill_calls(c.run_id, "send") or []
            c.fail(
                "no-results reply",
                f"no 'not found' phrase in any send. Got {len(all_sends)} "
                f"send(s), last: {(all_sends[-1] if all_sends else '<none>')!r}",
            )
        matched = [p for p in no_result_phrases if p in send_arg.lower()]
        c.ok("no-results reply", f"matched: {', '.join(matched[:3])}")

        c.done()
