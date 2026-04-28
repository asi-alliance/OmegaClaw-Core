"""
Test: OmegaClaw invokes (technical-analysis "AAPL") via the external agent.

Run:
    pytest test_technical_analysis.py -s
"""
from helpers import (
    Checker, find_skill_calls, make_prompt, send_prompt,
    wait_for_skill_call,
)

TICKER = "AAPL"


def test_technical_analysis():
    with Checker(f"technical-analysis {TICKER}") as c:
        print(f"\n=== OmegaClaw: technical-analysis {TICKER} (run-id {c.run_id}) ===",
              flush=True)

        c.step("send prompt via IRC")
        prompt = make_prompt(
            c.run_id,
            f"Use the technical-analysis skill to get technical analysis for "
            f"ticker {TICKER}. Summarize in one line.",
        )
        if not send_prompt(prompt):
            c.fail("irc", "could not deliver prompt within 60s")
        c.ok("irc", f"run-id={c.run_id}")

        c.step(f"verify agent invoked (technical-analysis ...) with {TICKER}")
        arg = wait_for_skill_call(
            c.run_id, "technical-analysis", timeout=240, arg_substr=TICKER,
        )
        if arg is None:
            all_calls = find_skill_calls(c.run_id, "technical-analysis") or []
            c.fail(
                "TA invoked",
                f"no (technical-analysis \"{TICKER}\"). Got: {all_calls[:3]}",
            )
        if arg.upper() != TICKER:
            c.fail("TA ticker", f"called with {arg!r}, expected {TICKER}")
        c.ok("TA invoked", f"arg={arg!r}")

        c.step("verify agent sent analysis summary with (send ...)")
        send_arg = wait_for_skill_call(c.run_id, "send", timeout=180)
        if send_arg is None:
            c.fail("send invoked", "agent did not relay TA result")
        body = send_arg.lower()
        indicators = [
            TICKER.lower(), "apple", "rsi", "macd", "sma", "ema",
            "buy", "sell", "bullish", "bearish", "trend", "signal",
            "momentum", "oversold", "overbought",
        ]
        matched = [k for k in indicators if k in body]
        if not matched:
            c.fail("send content", f"no TA indicators in send: {send_arg!r}")
        c.ok("send content", f"matched: {', '.join(matched[:5])}")

        c.done()
