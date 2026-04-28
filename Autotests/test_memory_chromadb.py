"""
Test: after an explicit remember prompt, agent invokes (remember ...) and
ChromaDB vector count grows by at least 1.

Run:
    pytest test_memory_chromadb.py -s
"""
import time

from helpers import (
    CHROMA_SQLITE, CONTAINER, Checker, find_skill_calls,
    make_prompt, send_prompt, wait_for_skill_call,
)
import subprocess


def chromadb_vector_count():
    """Query chroma.sqlite3 via python3 sqlite3 module inside the container."""
    py = (
        "import sqlite3;"
        f"c=sqlite3.connect('{CHROMA_SQLITE}');"
        "print(c.execute('SELECT COUNT(*) FROM embeddings').fetchone()[0])"
    )
    res = subprocess.run(
        ["docker", "exec", CONTAINER, "python3", "-c", py],
        capture_output=True, text=True,
    )
    if res.returncode != 0:
        return None
    try:
        return int(res.stdout.strip())
    except ValueError:
        return None


def test_memory_chromadb():
    with Checker("chromadb vector write") as c:
        print(f"\n=== OmegaClaw: chromadb write (run-id {c.run_id}) ===", flush=True)

        c.step("count chromadb vectors before")
        count_before = chromadb_vector_count()
        if count_before is None:
            c.fail("chromadb", f"cannot query {CHROMA_SQLITE} (sqlite3 missing?)")
        c.ok("chromadb before", f"{count_before} vectors")

        c.step("send remember prompt via IRC")
        marker = f"CI-SMOKE-{c.run_id}"
        c.add_cleanup_marker(marker)
        prompt = make_prompt(
            c.run_id,
            f"Please remember this exact fact using the remember skill: "
            f"'Unique smoke marker {marker} was emitted by CI.'",
        )
        if not send_prompt(prompt):
            c.fail("irc", "could not deliver prompt within 60s")
        c.ok("irc", f"run-id={c.run_id}")

        c.step("verify agent invoked (remember ...) with our marker")
        arg = wait_for_skill_call(
            c.run_id, "remember", timeout=180, arg_substr=marker,
        )
        if arg is None:
            all_calls = find_skill_calls(c.run_id, "remember") or []
            c.fail(
                "remember invoked",
                f"no (remember ...) with marker {marker}. Got {len(all_calls)} calls, "
                f"first args: {[a[:80] for a in all_calls[:3]]}",
            )
        c.ok("remember invoked", f"arg contains marker (len={len(arg)})")

        c.step("wait for chromadb vector count to grow")
        deadline = time.time() + 60
        count_after = count_before
        while time.time() < deadline:
            count_after = chromadb_vector_count()
            if count_after is not None and count_after > count_before:
                break
            time.sleep(2)
        if count_after is None or count_after <= count_before:
            c.fail(
                "chromadb grew",
                f"count stayed {count_before} (is {count_after})",
            )
        c.ok(
            "chromadb grew",
            f"{count_before} -> {count_after} (+{count_after - count_before})",
        )

        c.done()
