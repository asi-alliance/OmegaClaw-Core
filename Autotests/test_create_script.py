"""
Test: Omega creates date.sh that prints the current date.

Run:
    pytest test_create_script.py -s
"""
import time
from datetime import datetime, timezone

from helpers import (
    Checker, dexec, make_prompt, send_prompt, try_with_clarification,
    wait_for_file,
)

TARGET_DIR = "/tmp/test_script"
TARGET_FILE = "/tmp/test_script/date.sh"


def _current_year_strs():
    return {
        datetime.now(timezone.utc).strftime("%Y"),
        datetime.now().strftime("%Y"),
    }


def test_create_date_script():
    with Checker("create date.sh", cleanup_dirs=[TARGET_DIR]) as c:
        print(f"\n=== Omega: create date.sh (run-id {c.run_id}) ===", flush=True)

        c.verify_clean()

        start_ts = int(time.time()) - 1

        c.step("send prompt via IRC")
        prompt = make_prompt(
            c.run_id,
            f"Create a file {TARGET_FILE} with a shell script inside that will "
            "display the current date. Make it executable. "
            "Create the directory if needed. "
            "IMPORTANT: pass the full script body in ONE write-file call, "
            "with literal \\n between lines, e.g. "
            f'(write-file {TARGET_FILE} "#!/bin/bash\\ndate"). '
            "Do NOT split the body into separate (date) calls.",
        )
        if not send_prompt(prompt):
            c.fail("irc", "could not deliver prompt within 60s")
        c.ok("irc", f"run-id={c.run_id}")

        c.step(f"wait for {TARGET_FILE} executable with valid date output (graded)")
        years = _current_year_strs()

        def script_runs_ok():
            if dexec("test", "-x", TARGET_FILE).returncode != 0:
                return None
            res = dexec("sh", TARGET_FILE)
            if res.returncode != 0:
                return None
            out = res.stdout.strip()
            if any(y in out for y in years):
                return out
            return None

        clarification = (
            f"The script {TARGET_FILE} is missing the date command. "
            f"Run EXACTLY ONE skill call: "
            f'(write-file {TARGET_FILE} "#!/bin/bash\\ndate\\n") '
            f"— the body must include both the shebang and the literal word date "
            f"in a single quoted string (use the two characters \\ and n for the "
            f"line break). Then (shell chmod +x {TARGET_FILE})."
        )
        grade, output = try_with_clarification(
            c, script_runs_ok, clarification,
            timeout_first=120, timeout_second=180,
        )
        c.set_grade(grade)
        if grade == Checker.GRADE_FAIL:
            present = dexec("test", "-f", TARGET_FILE).returncode == 0
            perms = (
                dexec("stat", "-c", "%A", TARGET_FILE).stdout.strip()
                if present else "<missing>"
            )
            content = (
                dexec("cat", TARGET_FILE).stdout if present else ""
            )
            c.fail(
                "date check",
                f"script never produced current year. "
                f"present={present} perms={perms} content={content!r}",
            )
        c.ok("file created", f"executable, output={output!r} (grade={grade})")

        c.step("check file is executable")
        perms = dexec("stat", "-c", "%A", TARGET_FILE).stdout.strip()
        if "x" not in perms:
            c.fail("permissions", f"not executable: {perms}")
        c.ok("permissions", perms)

        c.step("verify run output contains current year")
        if not any(y in output for y in years):
            c.fail("date check", f"output does not contain current year: {output!r}")
        c.ok("date check", repr(output))

        c.done()
