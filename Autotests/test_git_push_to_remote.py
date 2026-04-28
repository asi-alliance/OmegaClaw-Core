"""Agent clones a remote, adds a unique file, commits and pushes.

Needs OMEGACLAW_GIT_TOKEN (skipped otherwise).
Optionally OMEGACLAW_GIT_REMOTE — defaults to OmegaSing/Test-Repopo.
"""
import json
import time
import urllib.error
import urllib.request

import pytest

from helpers import (
    Checker, dexec, dexec_root, find_skill_calls, get_git_remote,
    get_git_token, make_prompt, send_prompt, setup_git_in_container,
    teardown_git_in_container, try_with_clarification, wait_for_file,
)

TARGET_DIR = "/tmp/git_push"


def _gh(method, url, token, body=None):
    req = urllib.request.Request(url, method=method)
    req.add_header("Authorization", f"Bearer {token}")
    req.add_header("Accept", "application/vnd.github+json")
    req.add_header("X-GitHub-Api-Version", "2022-11-28")
    data = json.dumps(body).encode() if body is not None else None
    if data:
        req.add_header("Content-Type", "application/json")
    try:
        with urllib.request.urlopen(req, data=data, timeout=20) as r:
            text = r.read().decode()
            try:
                return r.status, json.loads(text) if text else None
            except json.JSONDecodeError:
                return r.status, text
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode(errors="ignore")


def _api_base(remote_url):
    path = remote_url.rstrip("/").removesuffix(".git")
    parts = path.split("github.com/", 1)
    if len(parts) != 2:
        raise ValueError(f"unsupported remote url: {remote_url!r}")
    return f"https://api.github.com/repos/{parts[1]}"


def test_git_push_to_remote():
    token = get_git_token()
    if not token:
        pytest.skip("OMEGACLAW_GIT_TOKEN not set")
    remote = get_git_remote()
    api = _api_base(remote)
    branch = f"qa/run-{int(time.time())}"

    with Checker("git push to remote", cleanup_dirs=[TARGET_DIR]) as c:
        print(f"\n=== git push (run-id {c.run_id}, branch {branch}) ===", flush=True)

        c.verify_clean()

        c.step("provision git credentials in container")
        ok, detail = setup_git_in_container(token)
        if not ok:
            c.fail("git setup", detail)
        c.ok("git setup")

        c.step("pre-create target dir")
        dexec_root("mkdir", "-p", TARGET_DIR)
        dexec_root("chmod", "777", TARGET_DIR)
        c.ok("pre-create dir", TARGET_DIR)

        unique_file = f"qa-run-{c.run_id}.txt"
        marker = f"omegaclaw push run {c.run_id}"
        c.add_cleanup_marker(marker)
        start_ts = int(time.time()) - 1

        c.step("send prompt via IRC")
        prompt = make_prompt(
            c.run_id,
            f"Clone {remote} into {TARGET_DIR}/ and check out a NEW branch "
            f"named '{branch}'. Create file {TARGET_DIR}/{unique_file} with "
            f"content '{marker}'. Run `git add`, `git commit -m 'qa run "
            f"{c.run_id}'`, then `git push -u origin {branch}`.",
        )
        if not send_prompt(prompt):
            c.fail("irc", "could not deliver prompt within 60s")
        c.ok("irc", f"run-id={c.run_id}")

        c.step(f"wait for {unique_file} on disk")
        mtime = wait_for_file(f"{TARGET_DIR}/{unique_file}", start_ts, timeout=240)
        if mtime is None:
            c.fail(unique_file, f"{unique_file} not created within timeout")
        c.ok(unique_file, f"after {mtime - start_ts}s")

        c.step("wait for branch on remote (graded)")
        clarification = (
            f"Run `git -C {TARGET_DIR} push -u origin {branch}`. "
            f"Credential helper is already configured, no token in URL."
        )
        grade, _ = try_with_clarification(
            c,
            lambda: True if _gh("GET", f"{api}/branches/{branch}", token)[0] == 200 else None,
            clarification,
            timeout_first=180, timeout_second=240,
        )
        c.set_grade(grade)
        if grade == Checker.GRADE_FAIL:
            c.fail("remote branch", f"{branch} not visible on remote within timeout")
        c.ok("remote branch", f"{branch} pushed (grade={grade})")

        c.step("verify file is present on remote branch")
        status, body = _gh("GET", f"{api}/contents/{unique_file}?ref={branch}", token)
        if status != 200 or not isinstance(body, dict):
            c.fail("remote file", f"GET contents failed: status={status} body={body!r}")
        c.ok("remote file", f"sha={body.get('sha', '')[:8]}")

        c.step("verify agent invoked git push")
        sh_calls = find_skill_calls(c.run_id, "shell") or []
        if not any("push" in a and "git" in a for a in sh_calls):
            print(f"       [WARN] no shell call combined 'git' and 'push'", flush=True)
        c.ok("shell push", f"{len(sh_calls)} shell calls")

        c.step(f"teardown: delete remote branch {branch}")
        status, body = _gh("DELETE", f"{api}/git/refs/heads/{branch}", token)
        if status not in (204, 422):
            c.fail("delete branch", f"status={status} body={body!r}")
        c.ok("delete branch", f"removed {branch}")

        c.step("teardown: wipe container git credentials")
        teardown_git_in_container()
        if dexec("test", "-f", "/etc/git-credentials").returncode == 0:
            c.fail("creds wiped", "/etc/git-credentials still present")
        c.ok("creds wiped")

        c.done()
