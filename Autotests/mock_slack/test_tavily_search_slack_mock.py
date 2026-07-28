"""
Mock variant of test_tavily_search.

The live test exercises the external Tavily uAgent. Under the mock the
external skill is not reachable in a deterministic way вЂ” the mocked
response delivers the answer directly via (send ...). The mock variant
therefore narrows the assertion to "did the agent surface a reply that
contains Fetch.ai-specific content"; the live variant remains the
source of truth for skill invocation.

Run:
    pytest test_tavily_search_mock.py -s
"""

from helpers import (
    Checker, find_skill_calls, make_prompt, wait_for_skill_match,
)
from slack_helpers import sl_send_prompt


# Strict Fetch.ai-specific keywords вЂ” deliberately excludes bare "ai"
# and "agent" so a generic delivery-failure message cannot pass.
FETCH_KEYWORDS = (
    "fetch.ai", "fetch ai", "fet ",
    "asi alliance", "asi-alliance", "alliance",
    "humayun", "humayun sheikh",
    "uagent", "u-agent",
    "decentralized", "blockchain",
    "token",
)

ERROR_MARKERS = (
    "delivery failed", "delivery error", "deliverystatus",
    "tavily search failed", "tavily-search failed", "tavily failed",
    "skill failed", "skill is currently unavailable",
    "currently unavailable", "is unreachable", "not reachable",
    "unable to reach", "could not reach", "couldn't reach",
)


FETCH_SUMMARY = (
    "Fetch.ai (FET) is a decentralized AI blockchain platform powering "
    "autonomous economic agents (uAgents). Recent news covers the ASI "
    "Alliance roadmap, FET token activity, and integration work with "
    "SingularityNET and CUDOS."
)


def test_tavily_search_slack_mock(llm, sl):
    with Checker("tavily-search invocation (slack mock)") as c:
        print(f"\n=== OmegaClaw: tavily slack mock (run-id {c.run_id}) ===",
              flush=True)

        c.step("send prompt via Slack with mocked send response")
        prompt = make_prompt(
            c.run_id,
            "Use the tavily-search skill (not regular search) for query "
            "'Fetch.ai latest news'. Summarize what Tavily returns.",
        )
        llm.set_answer(prompt, f'(send "{FETCH_SUMMARY}")')
        sl_send_prompt(sl, prompt)
        c.ok("slack", f"run-id={c.run_id}")

        c.step("wait for a (send ...) carrying real Fetch.ai content")

        def is_real_fetch_summary(s):
            low = s.lower()
            if any(em in low for em in ERROR_MARKERS):
                return False
            return any(kw in low for kw in FETCH_KEYWORDS)

        send_arg = wait_for_skill_match(
            c.run_id, "send", is_real_fetch_summary, timeout=30,
        )
        if send_arg is None:
            all_sends = find_skill_calls(c.run_id, "send") or []
            last = all_sends[-1] if all_sends else "<none>"
            low_last = last.lower() if isinstance(last, str) else ""
            error_hits = [em for em in ERROR_MARKERS if em in low_last]
            if error_hits:
                c.fail("tavily content",
                       f"send reported skill failure ({error_hits}). "
                       f"Last: {last!r}")
            c.fail("send content",
                   f"no Fetch-related keywords in any send. Last: {last!r}")
        body = send_arg.lower()
        matched = [k for k in FETCH_KEYWORDS if k in body]
        c.ok("send content", f"matched: {', '.join(matched[:4])}")

        c.done()
