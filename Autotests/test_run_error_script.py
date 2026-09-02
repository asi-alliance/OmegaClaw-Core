"""
Test: Omega runs a script with a syntax error and reports the error.

Run:
    pytest test_run_error_script.py -s
"""
import time

from helpers import (
    Checker,
    dexec,
    dexec_root,
    make_prompt,
    send_prompt,
    wait_for_file,
    try_with_clarification,
)

TARGET_DIR = "/tmp/test_error"
SCRIPT_FILE = "/tmp/test_error/broken.sh"
OUTPUT_FILE = "/tmp/test_error/output.txt"

BROKEN_SCRIPT = """#!/bin/sh
echo "start"
if [
echo "unreachable"
"""


def test_run_error_script():
    with Checker("run error script", cleanup_dirs=[TARGET_DIR]) as c:
        print(f"\n=== Omega: error script (run-id {c.run_id}) ===", flush=True)

        c.verify_clean()

        c.step("pre-create broken script")
        dexec_root("mkdir", "-p", TARGET_DIR)
        dexec_root(
            "sh",
            "-c",
            f"cat > {SCRIPT_FILE} << 'ENDOFFILE'\n{BROKEN_SCRIPT}ENDOFFILE",
        )
        dexec_root("chmod", "777", TARGET_DIR)
        dexec_root("chmod", "755", SCRIPT_FILE)

        if dexec("test", "-f", SCRIPT_FILE).returncode != 0:
            c.fail("pre-create", "could not create broken script")

        c.ok("pre-create")

        start_ts = int(time.time()) - 1

        c.step("send prompt via IRC")
        prompt = make_prompt(
            c.run_id,
            f"Run the script {SCRIPT_FILE} and save BOTH stdout and stderr "
            f"to {OUTPUT_FILE}. Use shell redirection `2>&1` so every error "
            f"message lands in the file too. Do not fix the script.",
        )

        if not send_prompt(prompt):
            c.fail("irc", "could not deliver prompt within 60s")

        c.ok("irc", f"run-id={c.run_id}")

        c.step(f"wait for {OUTPUT_FILE}")

        def output_has_error():
            if dexec("test", "-f", OUTPUT_FILE).returncode != 0:
                return None

            content = dexec("cat", OUTPUT_FILE).stdout
            content_lc = content.lower()

            error_indicators = [
                "error",
                "syntax",
                "unexpected",
                "missing",
                "not found",
            ]

            has_error = any(w in content_lc for w in error_indicators)
            has_start = "start" in content_lc

            if has_error and has_start:
                return content

            return None

        clarification = (
            f"Rerun the broken script exactly like this:\n"
            f"`sh {SCRIPT_FILE} > {OUTPUT_FILE} 2>&1; "
            f"echo EXIT_CODE:$? >> {OUTPUT_FILE}`\n"
            f"The file {OUTPUT_FILE} must contain both stdout and stderr. "
            f"Do not fix {SCRIPT_FILE}."
        )

        grade, content = try_with_clarification(
            c,
            output_has_error,
            clarification,
            timeout_first=60,
            timeout_second=120,
        )

        c.set_grade(grade)

        if grade == Checker.GRADE_FAIL:
            existing = ""
            if dexec("test", "-f", OUTPUT_FILE).returncode == 0:
                existing = dexec("cat", OUTPUT_FILE).stdout
            c.fail(
                "error reported",
                f"no error keywords in output: {repr(existing[:300])}",
            )

        mtime = wait_for_file(OUTPUT_FILE, start_ts)
        if mtime is None:
            c.fail("output created", f"{OUTPUT_FILE} not created within timeout")

        c.ok("output created", f"after {mtime - start_ts}s")

        c.step("check output contains stdout and error indication")
        content = dexec("cat", OUTPUT_FILE).stdout
        content_lc = content.lower()

        if "start" not in content_lc:
            c.fail("stdout captured", f"stdout not found in output: {repr(content[:300])}")

        c.ok("stdout captured", "'start' found")

        error_indicators = ["error", "syntax", "unexpected", "missing", "not found"]
        found = [w for w in error_indicators if w in content_lc]

        if not found:
            c.fail("error reported", f"no error keywords in output: {repr(content[:300])}")

        c.ok("error reported", f"found: {', '.join(found)}")

        c.step("check container still running")
        res = dexec("echo", "alive")

        if res.returncode != 0 or "alive" not in res.stdout:
            c.fail("container alive", "container not responding")

        c.ok("container alive")

        c.done()