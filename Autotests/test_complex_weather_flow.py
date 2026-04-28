"""End-to-end chain: search → write-file w.txt → write-file p.sh → shell.

Verifies the agent can sequence multiple skills and produce a final t.txt
holding a plausible temperature number. Graded 0/1/2.
"""
import re
import time

from helpers import (
    Checker, dexec, dexec_root, find_skill_calls, make_prompt,
    send_prompt, try_with_clarification, wait_for_file,
)

SEARCH_SKILLS = ("search", "tavily-search")

TARGET_DIR = "/tmp/wflow"
WEATHER_TXT = f"{TARGET_DIR}/w.txt"
SCRIPT_SH = f"{TARGET_DIR}/p.sh"
TEMP_ONLY = f"{TARGET_DIR}/t.txt"


def test_complex_weather_flow():
    with Checker("complex weather flow", cleanup_dirs=[TARGET_DIR]) as c:
        print(f"\n=== complex weather flow (run-id {c.run_id}) ===", flush=True)

        c.verify_clean()

        c.step("pre-create target dir 0777")
        dexec_root("mkdir", "-p", TARGET_DIR)
        dexec_root("chmod", "777", TARGET_DIR)
        c.ok("pre-create dir", TARGET_DIR)

        start_ts = int(time.time()) - 1

        c.step("send complex prompt via IRC")
        prompt = make_prompt(
            c.run_id,
            f"Search NY weather tomorrow in Celsius, save forecast to "
            f"{WEATHER_TXT}. Then build script {SCRIPT_SH} that extracts "
            f"the first Celsius number from {WEATHER_TXT} into "
            f"{TEMP_ONLY}. Make {SCRIPT_SH} executable, then run it. "
            f"NOTE: shell arg no apostrophes; write-file overwrites - "
            f"use append-file for extra lines.",
        )
        print(f"       prompt length: {len(prompt)} chars", flush=True)
        if not send_prompt(prompt):
            c.fail("irc", "could not deliver prompt within 60s")
        c.ok("irc", f"run-id={c.run_id}")

        c.step("wait for search call (graded)")

        def has_relevant_search():
            for skill in SEARCH_SKILLS:
                for a in find_skill_calls(c.run_id, skill) or []:
                    low = a.lower()
                    if "weather" in low or "new york" in low or " ny" in low:
                        return (skill, a)
            return None

        clarification = (
            f"Use open-meteo.com or wttr.in. Run exactly: (write-file "
            f"{SCRIPT_SH} #!/bin/bash) then (append-file {SCRIPT_SH} "
            f"grep -oE -?[0-9]+ {WEATHER_TXT} > {TEMP_ONLY}) then "
            f"(shell chmod +x {SCRIPT_SH}) then (shell {SCRIPT_SH})."
        )
        grade, hit = try_with_clarification(
            c, has_relevant_search, clarification,
            timeout_first=120, timeout_second=240,
        )
        c.set_grade(grade)
        if grade == Checker.GRADE_FAIL:
            c.fail("search invoked", "no relevant search/tavily-search call")
        skill, search_arg = hit
        c.ok(f"{skill} invoked", f"arg={search_arg!r} (grade={grade})")

        c.step(f"wait for {WEATHER_TXT}")
        mtime_w = wait_for_file(WEATHER_TXT, start_ts, timeout=240)
        if mtime_w is None:
            c.fail("w.txt", f"{WEATHER_TXT} not created within timeout")
        c.ok("w.txt", f"after {mtime_w - start_ts}s")

        c.step("verify (write-file ...) targeted w.txt")
        wf = find_skill_calls(c.run_id, "write-file") or []
        if not any(WEATHER_TXT in a for a in wf):
            c.fail("write-file w.txt", f"no write-file referencing {WEATHER_TXT}: {wf[:3]}")
        c.ok("write-file w.txt", f"{len(wf)} write-file calls")

        c.step(f"wait for {SCRIPT_SH}")
        mtime_s = wait_for_file(SCRIPT_SH, start_ts, timeout=240)
        if mtime_s is None:
            c.fail("script", f"{SCRIPT_SH} not created within timeout")
        c.ok("script", f"after {mtime_s - start_ts}s")

        c.step("verify (write-file ...) OR (shell ...) produced p.sh")
        sh = find_skill_calls(c.run_id, "shell") or []
        produced = any(SCRIPT_SH in a for a in wf) or any(SCRIPT_SH in a for a in sh)
        if not produced:
            c.fail("p.sh creation",
                   f"neither write-file nor shell mentioned {SCRIPT_SH}. "
                   f"wf={wf[:3]} sh={sh[:3]}")
        c.ok("p.sh creation", f"wf={len(wf)} sh={len(sh)}")

        c.step("check script is executable")
        perms = dexec("stat", "-c", "%A", SCRIPT_SH).stdout.strip()
        if "x" not in perms:
            c.fail("script perms", f"not executable: {perms}")
        c.ok("script perms", perms)

        c.step(f"wait for {TEMP_ONLY}")
        mtime_t = wait_for_file(TEMP_ONLY, start_ts, timeout=240)
        if mtime_t is None:
            c.fail("t.txt", f"{TEMP_ONLY} not created within timeout")
        c.ok("t.txt", f"after {mtime_t - start_ts}s")

        c.step("verify (shell ...) was invoked to run p.sh")
        if not any("p.sh" in a for a in sh):
            c.fail("shell invoked", f"no shell call referencing p.sh: {sh[:3]}")
        c.ok("shell invoked", f"{len(sh)} shell calls")

        c.step("verify t.txt contains a numeric temperature")
        content = dexec("cat", TEMP_ONLY).stdout.strip()
        if not content:
            c.fail("t.txt content", "file is empty")
        m = re.search(r"-?\d+(?:\.\d+)?", content)
        if not m:
            c.fail("t.txt numeric", f"no number in {content!r}")
        num = float(m.group(0))
        # English-language NY sources often produce raw °F; cap at 120 to
        # accept either scale for any plausible weather.
        if not (-60 <= num <= 120):
            c.fail("t.txt range", f"value {num} out of plausible range")
        if len(content) > 40:
            c.fail("t.txt tidy", f"content too long ({len(content)} chars)")
        c.ok("t.txt content", f"{content!r} (parsed {num})")

        c.done()
