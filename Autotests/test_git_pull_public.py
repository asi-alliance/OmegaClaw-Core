"""Agent clones a public git repository over anonymous HTTPS."""
from helpers import (
    Checker, dexec, dexec_root, find_skill_calls, get_git_remote,
    make_prompt, send_prompt, try_with_clarification,
)

TARGET_DIR = "/tmp/git_pull"


def test_git_pull_public():
    remote = get_git_remote()

    with Checker("git pull from public repo", cleanup_dirs=[TARGET_DIR]) as c:
        print(f"\n=== git pull public (run-id {c.run_id}) ===", flush=True)

        c.verify_clean()

        c.step("pre-create parent dir")
        dexec_root("mkdir", "-p", TARGET_DIR)
        dexec_root("chmod", "777", TARGET_DIR)
        c.ok("pre-create dir", TARGET_DIR)

        c.step("send prompt via IRC")
        prompt = make_prompt(
            c.run_id,
            f"Clone the public git repository {remote} into {TARGET_DIR}/. "
            "Use anonymous HTTPS, no credentials are needed. "
            "After cloning, list the files in the repository root.",
        )
        if not send_prompt(prompt):
            c.fail("irc", "could not deliver prompt within 60s")
        c.ok("irc", f"run-id={c.run_id}")

        c.step("wait for .git directory in clone (graded)")

        def has_clone():
            return True if dexec("test", "-d", f"{TARGET_DIR}/.git").returncode == 0 else None

        clarification = (
            f"Run `git clone {remote} {TARGET_DIR}` (or, if {TARGET_DIR} "
            f"already exists, `git -C {TARGET_DIR} clone {remote} .`)."
        )
        grade, _ = try_with_clarification(
            c, has_clone, clarification,
            timeout_first=120, timeout_second=180,
        )
        c.set_grade(grade)
        if grade == Checker.GRADE_FAIL:
            c.fail("clone", f".git not present at {TARGET_DIR} after clarification")
        c.ok("clone", f".git present (grade={grade})")

        c.step("verify clone has at least one tracked file")
        ls = dexec_root("git", "-C", TARGET_DIR, "ls-tree", "-r", "--name-only", "HEAD")
        files = [f for f in ls.stdout.split() if f]
        if not files:
            c.fail("tracked files", f"no files in HEAD: {ls.stdout!r}")
        c.ok("tracked files", f"{len(files)} files, e.g. {files[:3]}")

        c.step("verify HEAD has a commit")
        log = dexec_root("git", "-C", TARGET_DIR, "log", "--format=%H %s", "-1")
        head = log.stdout.strip()
        if not head:
            c.fail("HEAD", f"no commits visible: {log.stderr!r}")
        c.ok("HEAD", head[:80])

        c.step("verify agent invoked shell with git clone")
        sh_calls = find_skill_calls(c.run_id, "shell") or []
        if not any("clone" in a and "git" in a for a in sh_calls):
            print(f"       [WARN] no shell call combined 'git' and 'clone'", flush=True)
        c.ok("shell clone", f"{len(sh_calls)} shell calls")

        c.done()
