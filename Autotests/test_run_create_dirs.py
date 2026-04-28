"""
Test: OmegaClaw creates a script that makes numbered directories, then runs it.

Run:
    pytest test_run_create_dirs.py -s
"""
import time

from helpers import (
    Checker, dexec, make_prompt, send_prompt, wait_for_file,
)

TARGET_DIR = "/tmp/test_dirs"


def test_run_create_dirs():
    with Checker("create dirs script", cleanup_dirs=[TARGET_DIR]) as c:
        print(f"\n=== OmegaClaw: create dirs script (run-id {c.run_id}) ===", flush=True)

        c.verify_clean()

        start_ts = int(time.time()) - 1

        c.step("send prompt via IRC")
        prompt = make_prompt(
            c.run_id,
            f"Create a script {TARGET_DIR}/mkdirs.sh that creates 3 directories "
            f"named test1, test2, test3 inside {TARGET_DIR}/. "
            "Create the directory if needed, make the script executable, "
            "and then run the script.",
        )
        if not send_prompt(prompt):
            c.fail("irc", "could not deliver prompt within 60s")
        c.ok("irc", f"run-id={c.run_id}")

        c.step("wait for script file")
        mtime = wait_for_file(f"{TARGET_DIR}/mkdirs.sh", start_ts)
        if mtime is None:
            c.fail("script created", "mkdirs.sh not created within timeout")
        c.ok("script created", f"after {mtime - start_ts}s")

        c.step("check directories exist")
        missing = []
        for name in ["test1", "test2", "test3"]:
            if dexec("test", "-d", f"{TARGET_DIR}/{name}").returncode != 0:
                missing.append(name)
        if missing:
            c.fail("dirs exist", f"missing: {', '.join(missing)}")
        c.ok("dirs exist", "test1, test2, test3")

        c.step("check directory timestamps")
        all_ok = True
        for name in ["test1", "test2", "test3"]:
            res = dexec("stat", "-c", "%Y", f"{TARGET_DIR}/{name}")
            if res.returncode != 0 or int(res.stdout.strip()) < start_ts:
                all_ok = False
        if not all_ok:
            c.fail("dir timestamps", "some directories have stale mtime")
        c.ok("dir timestamps", f"all >= {start_ts}")

        c.done()
