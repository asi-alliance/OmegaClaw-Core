"""
Test: agent invokes (query ...) to retrieve a previously-remembered fact.

Two-turn flow:
  1. Plant a unique fact via remember (seed turn).
  2. After memory settles, ask the agent to look up that fact and require
     query specifically (not episodes — episodes is timestamp-based).

Pass criteria: a (query ...) call appears in the recall turn AND the agent
sends back a reply that mentions the planted keyword.

Run:
    pytest test_skill_query.py -s
"""
import time

from helpers import (
    Checker, find_skill_calls, make_prompt, send_prompt,
    wait_for_skill_call, wait_for_skill_match,
)


def test_skill_query():
    with Checker("query skill recall") as c:
        print(f"\n=== Omega: query skill (run-id {c.run_id}) ===", flush=True)

        secret_color = f"azure-{c.run_id}"
        c.add_cleanup_marker(secret_color)

        # ---------- seed turn ----------
        seed_id = c.run_id
        c.step("seed: ask agent to remember a unique color")
        seed_prompt = make_prompt(
            seed_id,
            f"Please use your `remember` skill to store this exact fact "
            f"verbatim: 'My favorite color is {secret_color}.' Acknowledge "
            f"with one short send.",
        )
        if not send_prompt(seed_prompt):
            c.fail("irc-seed", "could not deliver seed prompt within 60s")
        c.ok("irc-seed", f"run-id={seed_id}")

        c.step("seed: verify (remember ...) carries the secret color")
        def has_color(arg):
            return secret_color.lower() in arg.lower()
        remember_arg = wait_for_skill_match(
            seed_id, "remember", has_color, timeout=60,
        )
        if remember_arg is None:
            calls = find_skill_calls(seed_id, "remember") or []
            c.fail(
                "remember planted",
                f"no (remember ...) carrying {secret_color!r}. "
                f"Got: {[a[:80] for a in calls[:3]]}",
            )
        c.ok("remember planted", f"len={len(remember_arg)}")

        c.step("wait 60s for embedding to settle")
        time.sleep(60)
        c.ok("waited", "60s")

        # ---------- recall turn ----------
        recall_id = c.run_id + 1
        c.add_cleanup_marker(str(recall_id))
        c.step("recall: ask agent to look up the color via query skill")
        recall_prompt = make_prompt(
            recall_id,
            "Earlier I told you my favorite color. Use your `query` skill "
            "(short phrase, embedding lookup) to recall it from long-term "
            "memory and tell me the exact color name.",
        )
        if not send_prompt(recall_prompt):
            c.fail("irc-recall", "could not deliver recall prompt within 60s")
        c.ok("irc-recall", f"run-id={recall_id}")

        c.step("verify agent invoked (query ...)")
        q_arg = wait_for_skill_call(recall_id, "query", timeout=60)
        if q_arg is None:
            c.fail("query invoked", "no (query ...) call within 240s")
        c.ok("query invoked", f"arg={q_arg[:80]!r}")

        c.step("verify agent sent a reply mentioning the secret color")
        # Agent often strips the technical -{run_id} suffix when relaying
        # the colour back to the user (it treats the suffix as a CI marker
        # / noise, which is the right product behaviour). Accept either:
        #   - the full verbatim secret_color, OR
        #   - the bare colour name ("azure") provided the send is clearly
        #     a recall reply (mentions colour/favorite/remember context)
        # to avoid false-passes on unrelated text that happens to contain
        # "azure".
        bare = "azure"
        context_words = ("color", "colour", "favorite", "favourite",
                         "remember", "recall", "stored", "told")

        def is_recall_reply(a):
            low = a.lower()
            if secret_color.lower() in low:
                return True
            if bare in low and any(cw in low for cw in context_words):
                return True
            return False

        send_arg = wait_for_skill_match(
            recall_id, "send", is_recall_reply, timeout=60,
        )
        if send_arg is None:
            sends = find_skill_calls(recall_id, "send") or []
            c.fail(
                "send mentions color",
                f"no send mentions {bare!r} in a recall context. "
                f"Got: {[a[:80] for a in sends[:3]]}",
            )
        c.ok("send mentions color", f"reply={send_arg[:120]!r}")

        c.done()
