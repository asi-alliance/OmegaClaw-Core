"""Agent searches for Valencia weather and reports a temperature in °C.

Cross-checked against the open-meteo.com API (±10°C tolerance).
Graded 0/1/2: a weak model may stall on source-website clarification.
"""
import json
import re
import urllib.request

from helpers import (
    Checker, find_skill_calls, make_prompt, send_prompt,
    try_with_clarification, wait_for_skill_match,
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
        print(f"\n=== Valencia weather (run-id {c.run_id}) ===", flush=True)

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

        c.step("wait for search call with Valencia query (graded)")

        def has_valencia_search():
            for skill in SEARCH_SKILLS:
                for a in find_skill_calls(c.run_id, skill) or []:
                    if "valencia" in a.lower():
                        return (skill, a)
            return None

        clarification = (
            "Use any reliable weather website (e.g. open-meteo.com, "
            "weather.com or wttr.in) and search for the current temperature "
            "in Valencia Spain in Celsius."
        )
        grade, hit = try_with_clarification(
            c, has_valencia_search, clarification,
            timeout_first=120, timeout_second=240,
        )
        c.set_grade(grade)
        if grade == Checker.GRADE_FAIL:
            seen = {s: find_skill_calls(c.run_id, s) or [] for s in SEARCH_SKILLS}
            c.fail("search invoked", f"no search/tavily with 'valencia'. Got: {seen}")
        skill, arg = hit
        c.ok(f"{skill} invoked", f"arg={arg!r} (grade={grade})")

        c.step("wait for (send ...) carrying a plausible Celsius temperature")

        def has_plausible_temp(s):
            return any(-20 <= float(n) <= 50
                       for n in re.findall(r"-?\d+(?:\.\d+)?", s))

        send_arg = wait_for_skill_match(
            c.run_id, "send", has_plausible_temp, timeout=240,
        )
        if send_arg is None:
            all_sends = find_skill_calls(c.run_id, "send") or []
            last = all_sends[-1] if all_sends else "<none>"
            c.fail("send with temp", f"no send with plausible temp. Last: {last!r}")
        c.ok("send invoked", f"{len(send_arg)} chars")

        c.step("cross-check temperature with open-meteo (±10°C)")
        nums = [float(n) for n in re.findall(r"-?\d+(?:\.\d+)?", send_arg)
                if -20 <= float(n) <= 50]
        in_range = [n for n in nums if abs(n - ref_temp) <= 10]
        if not in_range:
            c.fail("cross-check", f"agent temps {nums} vs open-meteo {ref_temp}°C")
        c.ok("cross-check", f"{in_range} within ±10°C of {ref_temp}°C")

        c.done()
