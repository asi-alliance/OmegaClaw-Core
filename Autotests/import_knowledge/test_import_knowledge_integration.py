"""
Test: knowledge-base import on container startup (PR #168). Covers entrypoint
gating on IMPORT_KB_ON_START and a real local import landing in the chroma_db the
agent reads. Needs a built image (OMEGACLAW_KB_IMAGE) and Docker.

Run:
    cd Autotests && OMEGACLAW_KB_IMAGE=<image> \
        pytest -s import_knowledge/test_import_knowledge_integration.py
"""
import os
import subprocess
import time
from pathlib import Path

import pytest

IMAGE = os.environ.get("OMEGACLAW_KB_IMAGE", "")
REPO = Path(os.environ.get("OMEGACLAW_REPO", "/root/OmegaClaw-Core"))
NAME = "omegaclaw"


def _docker_ok():
    try:
        return subprocess.run(
            ["docker", "version"], capture_output=True
        ).returncode == 0
    except FileNotFoundError:
        return False


pytestmark = pytest.mark.skipif(
    not IMAGE or not _docker_ok() or not (REPO / "scripts" / "omegaclaw").exists(),
    reason="needs OMEGACLAW_KB_IMAGE, Docker, and scripts/omegaclaw",
)


def _logs():
    r = subprocess.run(["docker", "logs", NAME], capture_output=True, text=True)
    return r.stdout + r.stderr


def _running():
    out = subprocess.run(
        ["docker", "ps", "-q", "-f", f"name=^{NAME}$"],
        capture_output=True, text=True,
    ).stdout.strip()
    return bool(out)


def _start(import_kb_on_start):
    subprocess.run(["docker", "rm", "-f", NAME], capture_output=True)
    env = dict(os.environ)
    env["IMPORT_KB_ON_START"] = import_kb_on_start
    env.setdefault("TEST_SERVER_IP", "127.0.0.1")
    r = subprocess.run(
        ["bash", str(REPO / "scripts" / "omegaclaw"),
         "start", "-d", IMAGE, "-t", "test", "-p", "Test"],
        env=env, cwd=str(REPO), capture_output=True, text=True,
    )
    assert r.returncode == 0, r.stdout + r.stderr


def _wait_for(needle, timeout):
    deadline = time.time() + timeout
    while time.time() < deadline:
        logs = _logs()
        if needle in logs:
            return logs
        if not _running():
            return _logs()
        time.sleep(3)
    return _logs()


@pytest.fixture(autouse=True)
def _cleanup():
    yield
    subprocess.run(["docker", "rm", "-f", NAME], capture_output=True)


# With IMPORT_KB_ON_START=1 the entrypoint kicks off the import on boot.
def test_entrypoint_imports_when_enabled():
    _start("1")
    logs = _wait_for("[import-kb] Running", timeout=180)
    assert "[import-kb] Running" in logs, logs[-2000:]


# With IMPORT_KB_ON_START=0 the entrypoint never touches import-kb.
def test_entrypoint_skips_when_disabled():
    _start("0")
    time.sleep(25)
    logs = _logs()
    assert "[import-kb]" not in logs, logs[-2000:]


def _dexec(*cmd):
    return subprocess.run(
        ["docker", "exec", NAME, *cmd], capture_output=True, text=True
    ).stdout.strip()


# A real local import runs and lands in the same chroma_db the agent reads from.
def test_local_real_import_runs():
    _start("1")
    logs = _wait_for("Generating local", timeout=300)
    assert "[import-kb] Running import-knowledge with local embeddings" in logs, logs[-2000:]
    assert "Generating local" in logs, logs[-2000:]
    target = _dexec("readlink", "-f", "/PeTTa/chroma_db")
    app_path = _dexec("sh", "-c", "echo $MEMORY_DIR/chroma_db")
    assert target and target == app_path, f"import target {target!r} != app path {app_path!r}"
