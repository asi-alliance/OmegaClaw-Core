"""
Test: Omega runs dateupdate.sh 10 times, producing 10 lines in update.txt.

Graded 0/1/2: weaker models occasionally interpret "run 10 times" as a
single invocation (treating the script as a loop) and stop after one
line. The clarification turn explicitly enumerates ten shell calls so
the second attempt has no ambiguity.

Run:
    pytest test_run_repeated.py -s
"""
import time

from helpers import (
    Checker, dexec, dexec_root, find_skill_calls, make_prompt,
    send_prompt, try_with_clarification, wait_for_file,
)

TARGET_DIR = "/tmp/test_repeat"
SCRIPT_FILE = "/tmp/test_repeat/dateupdate.sh"
OUTPUT_FILE = "/tmp/test_repeat/update.txt"
SCRIPT_CONTENT = '#!/bin/sh\ndate >> /tmp/test_repeat/update.txt\n'
EXPECTED_RUNS = 10


def _line_count():
    res = dexec("cat", OUTPUT_FILE)
    if res.returncode != 0:
        return 0
    return len([l for l in res.stdout.strip().split("\n") if l.strip()])


def test_run_repeated():
    with Checker("run repeated script", cleanup_dirs=[TARGET_DIR]) as c:
        print(f"\n=== Omega: run 10x (run-id {c.run_id}) ===", flush=True)

        c.verify_clean()

        c.step("pre-create script")
        dexec_root("mkdir", "-p", TARGET_DIR)
        dexec_root("sh", "-c", f"cat > {SCRIPT_FILE} << 'ENDOFFILE'\n{SCRIPT_CONTENT}ENDOFFILE")
        dexec_root("chmod", "777", TARGET_DIR)
        dexec_root("chmod", "755", SCRIPT_FILE)
        if dexec("test", "-f", SCRIPT_FILE).returncode != 0:
            c.fail("pre-create", "could not create script")
        c.ok("pre-create")

        start_ts = int(time.time()) - 1

        c.step("send prompt via IRC")
        prompt = make_prompt(
            c.run_id,
            f"Run the script {SCRIPT_FILE} exactly 10 times in a row "
            f"by issuing 10 separate (shell {SCRIPT_FILE}) calls. The "
            f"script appends one date line to {OUTPUT_FILE} per run, so "
            f"the file must end up with exactly 10 lines.",
        )
        if not send_prompt(prompt):
            c.fail("irc", "could not deliver prompt within 60s")
        c.ok("irc", f"run-id={c.run_id}")

        c.step(f"wait for {OUTPUT_FILE}")
        mtime = wait_for_file(OUTPUT_FILE, start_ts, timeout=120)
        if mtime is None:
            c.fail("file created", f"{OUTPUT_FILE} not created within timeout")
        c.ok("file created", f"after {mtime - start_ts}s")

        c.step(f"wait for {EXPECTED_RUNS} lines (graded)")

        def has_enough_lines():
            return True if _line_count() >= EXPECTED_RUNS else None

        # Spell out ten separate shell calls so the second attempt has
        # zero room for "treat the script as a loop" misreading.
        repeated = " ".join(
            f"(shell {SCRIPT_FILE})" for _ in range(EXPECTED_RUNS)
        )
        clarification = (
            f"The file {OUTPUT_FILE} still has fewer than {EXPECTED_RUNS} "
            f"lines. Issue exactly {EXPECTED_RUNS} consecutive shell "
            f"calls now: {repeated}"
        )
        grade, _ = try_with_clarification(
            c, has_enough_lines, clarification,
            timeout_first=120, timeout_second=180,
        )
        c.set_grade(grade)
        if grade == Checker.GRADE_FAIL:
            sh = find_skill_calls(c.run_id, "shell") or []
            c.fail(
                "line count",
                f"only {_line_count()}/{EXPECTED_RUNS} lines after "
                f"clarification. shell calls={len(sh)}",
            )
        c.ok("line count", f"{_line_count()} lines (grade={grade})")

        c.step("verify mtime is fresh")
        mtime_after = int(dexec("stat", "-c", "%Y", OUTPUT_FILE).stdout.strip())
        if mtime_after < start_ts:
            c.fail("mtime check", f"{mtime_after} < {start_ts}")
        c.ok("mtime check", f"mtime={mtime_after} >= start={start_ts}")

        c.step("check every line carries date-like data")
        content = dexec("cat", OUTPUT_FILE).stdout
        lines = [l for l in content.strip().split("\n") if l.strip()]
        bad = [l for l in lines[:EXPECTED_RUNS] if sum(ch.isdigit() for ch in l) < 2]
        if bad:
            c.fail("date content", f"lines without date data: {bad!r}")
        c.ok("date content", f"all {EXPECTED_RUNS} lines contain date info")

        c.done()
