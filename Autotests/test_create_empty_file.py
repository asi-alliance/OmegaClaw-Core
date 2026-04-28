"""
Test: OmegaClaw creates an empty file hello.txt.

Run:
    pytest test_create_empty_file.py -s
"""
import time

from helpers import (
    Checker, dexec, make_prompt, send_prompt, wait_for_file,
)

TARGET_DIR = "/tmp/test_empty"
TARGET_FILE = "/tmp/test_empty/hello.txt"


def test_create_empty_file():
    with Checker("create empty file", cleanup_dirs=[TARGET_DIR]) as c:
        print(f"\n=== OmegaClaw: create empty file (run-id {c.run_id}) ===", flush=True)

        c.verify_clean()

        start_ts = int(time.time()) - 1

        c.step("send prompt via IRC")
        prompt = make_prompt(
            c.run_id,
            f"Create file hello.txt in {TARGET_DIR}/ directory "
            "(create the directory if needed). The file can be empty.",
        )
        if not send_prompt(prompt):
            c.fail("irc", "could not deliver prompt within 60s")
        c.ok("irc", f"run-id={c.run_id}")

        c.step(f"wait for {TARGET_FILE}")
        mtime = wait_for_file(TARGET_FILE, start_ts)
        if mtime is None:
            c.fail("file created", f"{TARGET_FILE} not created within timeout")
        c.ok("file created", f"after {mtime - start_ts}s")

        c.step("verify file exists via cat")
        res = dexec("cat", TARGET_FILE)
        if res.returncode != 0:
            c.fail("cat", f"cat failed: {res.stderr.strip()}")
        c.ok("cat", repr(res.stdout))

        c.done()
