"""
Test: OmegaClaw invokes (search ...) for Valencia weather and reports temperature.

Cross-check temperature against open-meteo.com API.

Run:
    pytest test_search_weather.py -s
"""
import json
import re
import urllib.request

from helpers import (
    Checker, find_skill_calls, make_prompt, send_prompt,
    wait_for_any_skill_call, wait_for_skill_call, wait_for_skill_match,
)

SEARCH_SKILLS = ("search", "tavily-search")

VALENCIA_LAT = 39.47
VALENCIA_LON = -0.38
OPEN_METEO_URL = (
    f"https://api.open-meteo.com/v1/forecast?"
    f"latitude={VALENCIA_LAT}&longitude={VALENCIA_LON}&current_weather=true"
)


def fetch_reference_weather():
    req = urllib.request.Request(OPEN_METEO_URL, headers={"User-Agent": "smoke/1.0"})
    with urllib.request.urlopen(req, timeout=15) as r:
        data = json.loads(r.read().decode())
    return data.get("current_weather", {})


def test_search_weather():
    with Checker("search weather valencia") as c:
        print(f"\n=== OmegaClaw: Valencia weather (run-id {c.run_id}) ===", flush=True)

        c.step("fetch reference weather from open-meteo")
        ref = fetch_reference_weather()
        if ref.get("temperature") is None:
            c.fail("open-meteo", f"no temperature in response: {ref}")
        ref_temp = float(ref["temperature"])
        c.ok("open-meteo", f"reference temp={ref_temp}°C")

        c.step("send prompt via IRC")
        prompt = make_prompt(
            c.run_id,
            "What's the weather in Valencia Spain today? "
            "Search the web and tell me temperature in Celsius.",
        )
        if not send_prompt(prompt):
            c.fail("irc", "could not deliver prompt within 60s")
        c.ok("irc", f"run-id={c.run_id}")

        c.step("verify agent invoked a search skill with Valencia query")
        skill, arg = wait_for_any_skill_call(
            c.run_id, SEARCH_SKILLS, timeout=180, arg_substr="valencia",
        )
        if arg is None:
            seen = {s: find_skill_calls(c.run_id, s) or [] for s in SEARCH_SKILLS}
            c.fail("search invoked", f"no search/tavily with 'valencia' arg. Got: {seen}")
        c.ok(f"{skill} invoked", f"arg={arg!r}")

        c.step("verify agent sent a (send ...) with a plausible temperature")
        # Agent often emits a preliminary "will search..." (send ...) first,
        # and only a later one carries the actual number. Scan every send in
        # the response window and wait until one contains a plausible Celsius
        # value; 240s because searches can be slow.
        def has_plausible_temp(s):
            nums = [float(n) for n in re.findall(r"-?\d+(?:\.\d+)?", s)
                    if -20 <= float(n) <= 50]
            return bool(nums)

        send_arg = wait_for_skill_match(
            c.run_id, "send", has_plausible_temp, timeout=240,
        )
        if send_arg is None:
            all_sends = find_skill_calls(c.run_id, "send") or []
            c.fail(
                "send with temp",
                f"no (send ...) with plausible temperature number. "
                f"Got {len(all_sends)} send(s), last: "
                f"{(all_sends[-1] if all_sends else '<none>')!r}",
            )
        c.ok("send invoked", f"{len(send_arg)} chars")

        c.step("cross-check temperature with open-meteo (±10°C tolerance)")
        numbers = [float(n) for n in re.findall(r"-?\d+(?:\.\d+)?", send_arg)
                   if -20 <= float(n) <= 50]
        in_range = [n for n in numbers if abs(n - ref_temp) <= 10]
        if not in_range:
            c.fail(
                "cross-check",
                f"agent temps {numbers} vs open-meteo {ref_temp}°C (all >10°C off)",
            )
        c.ok("cross-check", f"{in_range} within ±10°C of {ref_temp}°C")

        c.done()
