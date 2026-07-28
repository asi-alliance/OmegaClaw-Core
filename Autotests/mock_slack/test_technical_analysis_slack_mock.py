"""
Mock variant of test_technical_analysis.

The live test exercises the external technical-analysis uAgent. Under
the mock the external skill is not reachable deterministically вЂ” the
mocked response delivers the analysis summary directly via (send ...).
The mock variant therefore narrows the assertion to "did the agent
surface a reply that contains TA indicators for the requested ticker";
the live variant remains the source of truth for skill invocation.

Run:
    pytest test_technical_analysis_mock.py -s
"""

from helpers import (
    Checker, find_skill_calls, make_prompt, wait_for_skill_match,
)
from slack_helpers import sl_send_prompt

TICKER = "AAPL"

ERROR_MARKERS = (
    "delivery failed", "delivery error", "deliverystatus",
    "technical-analysis failed", "technical analysis failed",
    "ta failed", "ta-failed", "skill failed",
    "skill is currently unavailable", "currently unavailable",
    "is unreachable", "not reachable", "unable to reach",
    "could not reach", "couldn't reach",
)

TA_INDICATORS = (
    "rsi", "macd", "sma", "ema", "wma", "dema", "tema", "kama",
    "stochastic", "willr", "adx", "atr",
    "moving average", "momentum",
    "bullish", "bearish",
    "buy signal", "sell signal", "strong buy", "strong sell",
    "support level", "resistance level",
    "trend", "indicator",
)


TA_SUMMARY = (
    f"{TICKER} (Apple) is showing bullish momentum: RSI is rising, MACD "
    "crossed above its signal line, and the 50-day SMA is above the "
    "200-day. Composite indicators point to a buy signal with strong "
    "trend strength."
)


def test_technical_analysis_slack_mock(llm, sl):
    with Checker(f"technical-analysis {TICKER} (mock)") as c:
        print(f"\n=== OmegaClaw: TA {TICKER} slack mock (run-id {c.run_id}) ===",
              flush=True)

        c.step("send prompt via Slack with mocked send response")
        prompt = make_prompt(
            c.run_id,
            f"Use the technical-analysis skill to get technical analysis for "
            f"ticker {TICKER}. Summarize in one line.",
        )
        llm.set_answer(prompt, f'(send "{TA_SUMMARY}")')
        sl_send_prompt(sl, prompt)
        c.ok("slack", f"run-id={c.run_id}")

        c.step("wait for a (send ...) carrying TA content for the ticker")

        def is_real_ta_summary(s):
            low = s.lower()
            if any(em in low for em in ERROR_MARKERS):
                return False
            mentions_ticker = TICKER.lower() in low or "apple" in low
            mentions_indicator = any(ind in low for ind in TA_INDICATORS)
            return mentions_ticker and mentions_indicator

        send_arg = wait_for_skill_match(
            c.run_id, "send", is_real_ta_summary, timeout=30,
        )
        if send_arg is None:
            all_sends = find_skill_calls(c.run_id, "send") or []
            last = all_sends[-1] if all_sends else "<none>"
            low_last = last.lower() if isinstance(last, str) else ""
            error_hits = [em for em in ERROR_MARKERS if em in low_last]
            if error_hits:
                c.fail("TA content",
                       f"send reported skill failure ({error_hits}). "
                       f"Last: {last!r}")
            c.fail("send content",
                   f"no TA indicators or ticker mention in any send. "
                   f"Last: {last!r}")
        body = send_arg.lower()
        matched = [ind for ind in TA_INDICATORS if ind in body]
        c.ok("send content", f"matched indicators: {', '.join(matched[:5])}")

        c.done()
