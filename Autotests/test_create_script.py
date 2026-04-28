"""
Test: OmegaClaw creates date.sh that prints the current date.

Run:
    pytest test_create_script.py -s
"""
import time
from datetime import datetime, timezone

from helpers import (
    Checker, dexec, make_prompt, send_prompt, wait_for_file,
)

TARGET_DIR = "/tmp/test_script"
TARGET_FILE = "/tmp/test_script/date.sh"


def test_create_date_script():
    with Checker("create date.sh", cleanup_dirs=[TARGET_DIR]) as c:
        print(f"\n=== OmegaClaw: create date.sh (run-id {c.run_id}) ===", flush=True)

        c.verify_clean()

        start_ts = int(time.time()) - 1

        c.step("send prompt via IRC")
        prompt = make_prompt(
            c.run_id,
            f"Create a file {TARGET_FILE} with a shell script inside that will "
            "display the current date. Make it executable. "
            "Create the directory if needed.",
        )
        if not send_prompt(prompt):
            c.fail("irc", "could not deliver prompt within 60s")
        c.ok("irc", f"run-id={c.run_id}")

        c.step(f"wait for {TARGET_FILE}")
        # Agent builds the script via a python script-to-file pattern
        # (shell-quoting of a shebang + executable bit is unreliable for it),
        # which takes 2-3 autonomous-loop iterations. Default WAIT=120s was
        # tight — bumped to 240s to absorb that.
        mtime = wait_for_file(TARGET_FILE, start_ts, timeout=240)
        if mtime is None:
            c.fail("file created", f"{TARGET_FILE} not created within timeout")
        c.ok("file created", f"after {mtime - start_ts}s")

        c.step("check file is executable")
        perms = dexec("stat", "-c", "%A", TARGET_FILE).stdout.strip()
        if "x" not in perms:
            c.fail("permissions", f"not executable: {perms}")
        c.ok("permissions", perms)

        c.step("run script and compare date")
        res = dexec("sh", TARGET_FILE)
        if res.returncode != 0:
            c.fail("run script", f"exit code {res.returncode}: {res.stderr.strip()}")
        script_output = res.stdout.strip()
        today_str = datetime.now(timezone.utc).strftime("%Y")
        if today_str not in script_output:
            now_local = datetime.now().strftime("%Y")
            if now_local not in script_output:
                c.fail("date check", f"output does not contain current year: {repr(script_output)}")
        c.ok("date check", repr(script_output))

        c.done()
