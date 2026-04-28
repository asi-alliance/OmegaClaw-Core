"""
Test: OmegaClaw runs dateupdate.sh 10 times, producing 10 lines in update.txt.

Run:
    pytest test_run_repeated.py -s
"""
import time

from helpers import (
    Checker, dexec, dexec_root, make_prompt, send_prompt, wait_for_file,
)

TARGET_DIR = "/tmp/test_repeat"
SCRIPT_FILE = "/tmp/test_repeat/dateupdate.sh"
OUTPUT_FILE = "/tmp/test_repeat/update.txt"
SCRIPT_CONTENT = '#!/bin/sh\ndate >> /tmp/test_repeat/update.txt\n'


def test_run_repeated():
    with Checker("run repeated script", cleanup_dirs=[TARGET_DIR]) as c:
        print(f"\n=== OmegaClaw: run 10x (run-id {c.run_id}) ===", flush=True)

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
            f"Run the script {SCRIPT_FILE} exactly 10 times in a row. "
            f"The script appends a date line to {OUTPUT_FILE} each time it runs.",
        )
        if not send_prompt(prompt):
            c.fail("irc", "could not deliver prompt within 60s")
        c.ok("irc", f"run-id={c.run_id}")

        c.step(f"wait for {OUTPUT_FILE}")
        mtime = wait_for_file(OUTPUT_FILE, start_ts)
        if mtime is None:
            c.fail("file created", f"{OUTPUT_FILE} not created within timeout")
        c.ok("file created", f"after {mtime - start_ts}s")

        c.step("check mtime is after test start")
        if mtime < start_ts:
            c.fail("mtime check", f"{mtime} < {start_ts}")
        c.ok("mtime check", f"mtime={mtime} >= start={start_ts}")

        c.step("wait for 10 lines (agent may need time)")
        deadline = time.time() + 120
        lines = []
        while time.time() < deadline:
            content = dexec("cat", OUTPUT_FILE).stdout
            lines = [l for l in content.strip().split("\n") if l.strip()]
            if len(lines) >= 10:
                break
            time.sleep(3)
        if len(lines) < 10:
            c.fail("line count", f"expected 10 lines, got {len(lines)}")
        c.ok("line count", f"{len(lines)} lines")

        c.step("check lines contain date-like data")
        bad_lines = [l for l in lines[:10] if sum(ch.isdigit() for ch in l) < 2]
        if bad_lines:
            c.fail("date content", f"lines without date data: {repr(bad_lines)}")
        c.ok("date content", "all 10 lines contain date info")

        c.done()
