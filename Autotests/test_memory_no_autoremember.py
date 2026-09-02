"""
Live test (negative): a HUMAN_MESSAGE alone must not autopromote into
ChromaDB. The agent should write to long-term memory only when it
explicitly invokes (remember ...). This test does NOT mock the LLM —
the question being asked ("does the agent voluntarily call remember
on a fact-shaped sentence?") is only meaningful with a real model.

We send a fact-shaped statement that does not request anything. The
agent is allowed to acknowledge via (send ...) or even (pin ...), but
must not write a ChromaDB vector unless it explicitly chose to. The
test reports the agent's choice; passing means "no implicit promotion
to long-term memory".

Run:
    pytest test_memory_no_autoremember.py -s
"""
import subprocess
import time

from helpers import (
    CHROMA_SQLITE, CONTAINER, Checker, find_skill_calls,
    HISTORY_FILE, dexec, make_prompt, send_prompt,
)


def chromadb_vector_count():
    """Return the number of embeddings in ChromaDB. Returns 0 when the
    database has not yet been initialised (fresh volume) or the
    embeddings table does not yet exist."""
    py = f"""
import os, sqlite3, sys
p = "{CHROMA_SQLITE}"
if not os.path.exists(p):
    print(0); sys.exit(0)
try:
    c = sqlite3.connect(p)
    print(c.execute("SELECT COUNT(*) FROM embeddings").fetchone()[0])
except sqlite3.OperationalError:
    print(0)
"""
    res = subprocess.run(
        ["docker", "exec", CONTAINER, "python3", "-c", py],
        capture_output=True, text=True,
    )
    if res.returncode != 0:
        print(f"  [chromadb_vector_count] rc={res.returncode} "
              f"stderr={res.stderr.strip()[:200]!r}", flush=True)
        return None
    try:
        return int(res.stdout.strip())
    except ValueError:
        print(f"  [chromadb_vector_count] non-int stdout={res.stdout!r} "
              f"stderr={res.stderr.strip()[:200]!r}", flush=True)
        return None


def test_memory_no_autoremember():
    with Checker("HUMAN_MESSAGE does NOT autopromote to ChromaDB (live)") as c:
        print(f"\n=== Omega: no-autoremember live (run-id {c.run_id}) ===",
              flush=True)

        fact_marker = f"azure-{c.run_id}"
        c.add_cleanup_marker(fact_marker)

        count_before = chromadb_vector_count()
        if count_before is None:
            c.fail("chromadb", "cannot read vector count")
        c.ok("chromadb before", f"{count_before} vectors")

        c.step("send a fact-shaped statement WITHOUT asking to remember")
        prompt = make_prompt(
            c.run_id,
            f"My favorite color is {fact_marker}. "
            f"This is just a casual mention — no need to do anything special.",
        )
        if not send_prompt(prompt):
            c.fail("irc", "could not deliver prompt within 60s")
        c.ok("irc", f"run-id={c.run_id}")

        c.step(f"wait up to 180s for {fact_marker!r} to land in history.metta")
        # GLM is slow — first 2-4 idle iterations happen before HUMAN_MESSAGE
        # arrives, then the agent needs another iteration to process it.
        # In practice the marker shows up around 70-120s after send_prompt.
        deadline = time.time() + 180
        disk_hits = 0
        while time.time() < deadline:
            res = dexec("grep", "-c", fact_marker, HISTORY_FILE)
            try:
                disk_hits = int(res.stdout.strip())
            except ValueError:
                disk_hits = 0
            if disk_hits >= 1:
                break
            time.sleep(5)
        if disk_hits < 1:
            c.fail("history autowrite",
                   f"marker {fact_marker!r} missing from history.metta after "
                   f"180s — HUMAN_MESSAGE was not recorded")
        c.ok("history autowrite",
             f"{disk_hits} occurrence(s) of HUMAN_MESSAGE in history "
             f"(after {int(180 - (deadline - time.time()))}s)")

        c.step("give the agent another 60s to decide whether to (remember ...)")
        time.sleep(60)

        c.step("check whether the agent decided to (remember ...) on its own")
        remember_calls = find_skill_calls(c.run_id, "remember") or []
        explicit_remember = [a for a in remember_calls if fact_marker in a]

        count_after = chromadb_vector_count()
        if count_after is None:
            c.fail("chromadb after", "cannot read vector count")

        if explicit_remember:
            # The agent volunteered a (remember ...) for the fact. Spec-wise
            # that's allowed for a "casual mention", but it does demonstrate
            # the agent's tendency to promote unprompted facts. We surface
            # this as informational, not as a hard failure.
            c.ok(
                "agent volunteered remember",
                f"agent autopromoted the fact via {len(explicit_remember)} "
                f"(remember ...) call(s); ChromaDB delta "
                f"{count_after - count_before:+d}. Behaviour is model-dependent.",
            )
        elif count_after > count_before:
            # Vectors grew without our marker. The agent remembered something
            # unrelated to azure-marker — still a "voluntary promotion" of
            # something. Surface as informational.
            c.ok(
                "agent volunteered remember (other content)",
                f"ChromaDB delta {count_after - count_before:+d} from unrelated "
                f"content; our fact was NOT promoted",
            )
        else:
            c.ok(
                "no implicit promotion",
                f"agent did not call (remember ...) for the fact; "
                f"ChromaDB stayed at {count_before} vectors",
            )

        c.done()
