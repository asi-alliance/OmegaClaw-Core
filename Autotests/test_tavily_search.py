"""
Test: OmegaClaw invokes (tavily-search ...) when asked explicitly.

Run:
    pytest test_tavily_search.py -s
"""
from helpers import (
    Checker, find_skill_calls, make_prompt, send_prompt,
    wait_for_skill_call,
)


def test_tavily_search():
    with Checker("tavily-search invocation") as c:
        print(f"\n=== OmegaClaw: tavily-search (run-id {c.run_id}) ===", flush=True)

        c.step("send prompt via IRC asking for tavily-search")
        prompt = make_prompt(
            c.run_id,
            "Use the tavily-search skill (not regular search) for query "
            "'Fetch.ai latest news'. Summarize what Tavily returns.",
        )
        if not send_prompt(prompt):
            c.fail("irc", "could not deliver prompt within 60s")
        c.ok("irc", f"run-id={c.run_id}")

        c.step("verify agent invoked (tavily-search ...) with Fetch.ai query")
        arg = wait_for_skill_call(
            c.run_id, "tavily-search", timeout=240, arg_substr="fetch",
        )
        if arg is None:
            all_calls = find_skill_calls(c.run_id, "tavily-search") or []
            c.fail(
                "tavily-search invoked",
                f"no (tavily-search ...) with 'fetch' arg. Got: {all_calls[:3]}",
            )
        c.ok("tavily-search invoked", f"arg={arg!r}")

        c.step("verify agent did NOT fall back to regular (search ...)")
        regular_search = find_skill_calls(c.run_id, "search") or []
        if regular_search:
            print(f"       [WARN] agent also used plain (search ...): {regular_search[:2]}",
                  flush=True)
        c.ok("no search fallback" if not regular_search else "mixed skills",
             f"{len(regular_search)} plain search calls")

        c.step("verify agent sent summary back with (send ...)")
        send_arg = wait_for_skill_call(c.run_id, "send", timeout=120)
        if send_arg is None:
            c.fail("send invoked", "agent did not relay tavily results")
        body = send_arg.lower()
        keywords = ["fetch", "fetch.ai", "ai", "blockchain", "agent",
                    "asi", "crypto", "token", "alliance"]
        matched = [k for k in keywords if k in body]
        if not matched:
            c.fail("send content", f"no Fetch-related keywords in send: {send_arg!r}")
        c.ok("send content", f"matched: {', '.join(matched[:4])}")

        c.done()
