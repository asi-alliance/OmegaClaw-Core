"""Agent initialises a local git repo, creates a file and commits it."""
import time

from helpers import (
    Checker, dexec, dexec_root, find_skill_calls, make_prompt, send_prompt,
    setup_git_in_container, teardown_git_in_container,
    try_with_clarification, wait_for_file,
)

TARGET_DIR = "/tmp/git_local"
COMMIT_FILE = "hello.txt"


def test_git_local_commit():
    with Checker("git local commit", cleanup_dirs=[TARGET_DIR]) as c:
        print(f"\n=== git local commit (run-id {c.run_id}) ===", flush=True)

        c.verify_clean()

        c.step("pre-create target dir + git author identity")
        dexec_root("mkdir", "-p", TARGET_DIR)
        dexec_root("chmod", "777", TARGET_DIR)
        # author identity is required, but no token: pass a placeholder.
        ok, detail = setup_git_in_container(token="dummy-not-used-here")
        if not ok:
            c.fail("git setup", detail)
        c.ok("git setup")

        start_ts = int(time.time()) - 1
        marker = f"omegaclaw run {c.run_id}"
        c.add_cleanup_marker(marker)

        c.step("send prompt via IRC")
        prompt = make_prompt(
            c.run_id,
            f"Initialise a new git repository at {TARGET_DIR}/. "
            f"Create file {TARGET_DIR}/{COMMIT_FILE} with content "
            f"'{marker}'. Then run `git add` and `git commit` with "
            f"message 'add hello {c.run_id}'.",
        )
        if not send_prompt(prompt):
            c.fail("irc", "could not deliver prompt within 60s")
        c.ok("irc", f"run-id={c.run_id}")

        c.step(f"wait for {COMMIT_FILE} on disk")
        mtime = wait_for_file(f"{TARGET_DIR}/{COMMIT_FILE}", start_ts, timeout=180)
        if mtime is None:
            c.fail(COMMIT_FILE, f"{COMMIT_FILE} not created within timeout")
        c.ok(COMMIT_FILE, f"after {mtime - start_ts}s")

        c.step("wait for .git directory and at least one commit (graded)")

        def has_commit():
            if dexec("test", "-d", f"{TARGET_DIR}/.git").returncode != 0:
                return None
            res = dexec_root("git", "-C", TARGET_DIR, "log", "--format=%H %s", "-1")
            line = res.stdout.strip() if res.returncode == 0 else ""
            return line or None

        clarification = (
            f"Stage and commit the file: run `git -C {TARGET_DIR} add -A` "
            f"and `git -C {TARGET_DIR} commit -m 'add hello {c.run_id}'`."
        )
        grade, head = try_with_clarification(
            c, has_commit, clarification,
            timeout_first=120, timeout_second=180,
        )
        c.set_grade(grade)
        if grade == Checker.GRADE_FAIL:
            c.fail("git commit", "no commit in repo after clarification")
        c.ok("git commit", f"HEAD={head!r} (grade={grade})")

        c.step("verify commit message contains run_id")
        msg = dexec_root("git", "-C", TARGET_DIR, "log", "--format=%s", "-1").stdout
        if str(c.run_id) not in msg:
            print(f"       [WARN] run_id not in subject: {msg.strip()!r}", flush=True)
        c.ok("commit message", msg.strip())

        c.step(f"verify {COMMIT_FILE} is tracked in HEAD")
        ls = dexec_root("git", "-C", TARGET_DIR, "ls-tree", "-r", "--name-only", "HEAD")
        if COMMIT_FILE not in ls.stdout.split():
            c.fail("tracked file", f"{COMMIT_FILE} not in HEAD: {ls.stdout!r}")
        c.ok("tracked file", COMMIT_FILE)

        c.step("verify agent invoked shell with git commands")
        sh_calls = find_skill_calls(c.run_id, "shell") or []
        git_calls = [a for a in sh_calls if "git " in a or a.strip().startswith("git")]
        if not git_calls:
            print(f"       [WARN] no shell call mentioned 'git'", flush=True)
        c.ok("shell git", f"{len(git_calls)}/{len(sh_calls)} shell calls used git")

        teardown_git_in_container()
        c.done()
