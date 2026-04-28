"""
Test: complex flow verifying a chain of skill invocations:
  (search ...) -> (write-file ... w.txt) -> (write-file ... p.sh) -> (shell ...).
Plus filesystem-level verification of the final t.txt output.

Short paths/prompt to stay under IRC 512-byte line limit.

Run:
    pytest test_complex_weather_flow.py -s
"""
import re
import time

from helpers import (
    Checker, dexec, dexec_root, find_skill_calls, make_prompt,
    send_prompt, wait_for_any_skill_call, wait_for_file,
    wait_for_skill_call,
)

SEARCH_SKILLS = ("search", "tavily-search")

TARGET_DIR = "/tmp/wflow"
WEATHER_TXT = f"{TARGET_DIR}/w.txt"
SCRIPT_SH = f"{TARGET_DIR}/p.sh"
TEMP_ONLY = f"{TARGET_DIR}/t.txt"


def test_complex_weather_flow():
    with Checker("complex weather flow", cleanup_dirs=[TARGET_DIR]) as c:
        print(f"\n=== OmegaClaw: complex weather flow (run-id {c.run_id}) ===", flush=True)

        c.verify_clean()

        c.step("pre-create target dir writable by agent")
        dexec_root("mkdir", "-p", TARGET_DIR)
        dexec_root("chmod", "777", TARGET_DIR)
        c.ok("pre-create dir", TARGET_DIR)

        start_ts = int(time.time()) - 1

        c.step("send complex prompt via IRC")
        prompt = make_prompt(
            c.run_id,
            f"Search NY weather tomorrow (temperature in Celsius), save "
            f"forecast to {WEATHER_TXT}, make shell script {SCRIPT_SH} that "
            f"extracts first Celsius temperature number from {WEATHER_TXT} "
            f"into {TEMP_ONLY} (the value must be in °C, not °F). "
            f"Make {SCRIPT_SH} executable with chmod +x, then run it.",
        )
        print(f"       prompt length: {len(prompt)} chars", flush=True)
        if not send_prompt(prompt):
            c.fail("irc", "could not deliver prompt within 60s")
        c.ok("irc", f"run-id={c.run_id}")

        c.step("verify search/tavily-search was invoked for weather query")
        skill, search_arg = wait_for_any_skill_call(
            c.run_id, SEARCH_SKILLS, timeout=240,
        )
        if search_arg is None:
            c.fail("search invoked", "no search or tavily-search call in response")
        low = search_arg.lower()
        if "weather" not in low and "new york" not in low and " ny" not in low:
            c.fail("search query", f"search arg unrelated to NY weather: {search_arg!r}")
        c.ok(f"{skill} invoked", f"arg={search_arg!r}")

        c.step(f"wait for {WEATHER_TXT} on disk")
        mtime_w = wait_for_file(WEATHER_TXT, start_ts, timeout=240)
        if mtime_w is None:
            c.fail("w.txt", f"{WEATHER_TXT} not created within timeout")
        c.ok("w.txt", f"after {mtime_w - start_ts}s")

        c.step("verify (write-file ...) targeted w.txt")
        wf_calls = find_skill_calls(c.run_id, "write-file") or []
        if not any(WEATHER_TXT in a for a in wf_calls):
            c.fail(
                "write-file w.txt",
                f"no (write-file ...) call referencing {WEATHER_TXT}. Got: {wf_calls[:3]}",
            )
        c.ok("write-file w.txt", f"{len(wf_calls)} write-file calls total")

        c.step(f"wait for {SCRIPT_SH} on disk")
        mtime_s = wait_for_file(SCRIPT_SH, start_ts, timeout=240)
        if mtime_s is None:
            c.fail("script", f"{SCRIPT_SH} not created within timeout")
        c.ok("script", f"after {mtime_s - start_ts}s")

        c.step("verify (write-file ...) OR (shell ...) produced p.sh")
        shell_calls = find_skill_calls(c.run_id, "shell") or []
        produced = (
            any(SCRIPT_SH in a for a in wf_calls)
            or any(SCRIPT_SH in a for a in shell_calls)
        )
        if not produced:
            c.fail(
                "p.sh creation",
                f"neither write-file nor shell mentioned {SCRIPT_SH}. "
                f"wf={wf_calls[:3]} sh={shell_calls[:3]}",
            )
        c.ok("p.sh creation", f"wf={len(wf_calls)}, shell={len(shell_calls)}")

        c.step("check script is executable")
        perms = dexec("stat", "-c", "%A", SCRIPT_SH).stdout.strip()
        if "x" not in perms:
            c.fail("script perms", f"not executable: {perms}")
        c.ok("script perms", perms)

        c.step(f"wait for {TEMP_ONLY} on disk")
        mtime_t = wait_for_file(TEMP_ONLY, start_ts, timeout=240)
        if mtime_t is None:
            c.fail("t.txt", f"{TEMP_ONLY} not created within timeout")
        c.ok("t.txt", f"after {mtime_t - start_ts}s")

        c.step("verify (shell ...) was invoked to run p.sh")
        if not any("p.sh" in a for a in shell_calls):
            c.fail(
                "shell invoked",
                f"no (shell ...) call referencing p.sh. Got: {shell_calls[:3]}",
            )
        c.ok("shell invoked", f"{len(shell_calls)} shell calls")

        c.step("verify t.txt contains just a numeric temperature")
        content = dexec("cat", TEMP_ONLY).stdout.strip()
        if not content:
            c.fail("t.txt content", "file is empty")
        m = re.search(r"-?\d+(?:\.\d+)?", content)
        if not m:
            c.fail("t.txt numeric", f"no number in {content!r}")
        num = float(m.group(0))
        # Tolerant range: plausible Celsius is [-60; 60], but agents often
        # produce raw Fahrenheit from US sources (NY forecast is commonly
        # reported in °F on english-language sites). 120 caps the upper
        # end of both scales for any earth-realistic weather.
        if not (-60 <= num <= 120):
            c.fail("t.txt range", f"value {num} out of plausible temp range")
        if len(content) > 40:
            c.fail("t.txt tidy", f"content too long ({len(content)} chars): {content[:100]!r}")
        c.ok("t.txt content", f"{content!r} (parsed {num})")

        c.done()
