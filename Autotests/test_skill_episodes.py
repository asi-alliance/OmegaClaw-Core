"""
Test: agent invokes (episodes ...) to recall history around a timestamp.

Two-turn flow:
  1. Send a uniquely-marked message (seed) and wait for the agent to
     respond — this puts a dated record into history.metta.
  2. After a settle pause, ask the agent to use `episodes` (timestamp
     lookup, NOT query — query is embedding-based) to recall what was
     discussed at that earlier time, and to mention the unique marker.

Pass criteria: an (episodes ...) call in the recall turn AND a (send ...)
that references our seed marker.

Run:
    pytest test_skill_episodes.py -s
"""
import datetime
import time

from helpers import (
    Checker, find_skill_calls, make_prompt, send_prompt,
    wait_for_skill_call, wait_for_skill_match,
)


def test_skill_episodes():
    with Checker("episodes skill recall") as c:
        print(f"\n=== Omega: episodes skill (run-id {c.run_id}) ===", flush=True)

        marker = f"BEACON-{c.run_id}"
        c.add_cleanup_marker(marker)

        # ---------- seed turn ----------
        seed_id = c.run_id
        c.step("seed: send a uniquely-marked message and capture timestamp")
        seed_time = datetime.datetime.now()
        seed_prompt = make_prompt(
            seed_id,
            f"Please acknowledge with one short send that you just heard "
            f"the keyword {marker} from me. No need to remember it — just "
            f"reply once.",
        )
        if not send_prompt(seed_prompt):
            c.fail("irc-seed", "could not deliver seed prompt within 60s")
        c.ok("irc-seed", f"run-id={seed_id}, time={seed_time:%H:%M:%S}")

        c.step("seed: wait for agent to reply (history will record it)")
        seed_send = wait_for_skill_call(seed_id, "send", timeout=60)
        if seed_send is None:
            c.fail("seed reply", "agent did not reply to seed within 240s")
        c.ok("seed reply", f"reply={seed_send[:80]!r}")

        c.step("wait 90s so the seed turn is clearly in 'past' history")
        time.sleep(90)
        c.ok("waited", "90s")

        # ---------- recall turn ----------
        recall_id = c.run_id + 1
        c.add_cleanup_marker(str(recall_id))
        c.step("recall: ask agent to use episodes skill at the seed timestamp")
        time_str = seed_time.strftime("%Y-%m-%d %H:%M")
        recall_prompt = make_prompt(
            recall_id,
            f"Use your `episodes` skill (timestamp lookup, not query) to "
            f"look up what we were discussing around {time_str}, then tell "
            f"me the unique keyword I mentioned then. Reply with one short "
            f"send.",
        )
        if not send_prompt(recall_prompt):
            c.fail("irc-recall", "could not deliver recall prompt within 60s")
        c.ok("irc-recall", f"run-id={recall_id}")

        c.step("verify agent invoked (episodes ...)")
        ep_arg = wait_for_skill_call(recall_id, "episodes", timeout=60)
        if ep_arg is None:
            c.fail("episodes invoked", "no (episodes ...) call within 240s")
        c.ok("episodes invoked", f"arg={ep_arg[:80]!r}")

        c.step("verify agent's send actually surfaces the seed marker")
        # If the agent only invokes (episodes ...) but its send reply doesn't
        # mention our unique BEACON marker, the recall failed: the test would
        # otherwise pass on a stub like "I looked but found nothing relevant",
        # masking an actually-broken episodes lookup.
        def has_marker(s):
            low = s.lower()
            return marker.lower() in low or "beacon" in low
        send_arg = wait_for_skill_match(
            recall_id, "send", has_marker, timeout=120,
        )
        if send_arg is None:
            sends = find_skill_calls(recall_id, "send") or []
            last = sends[-1] if sends else "<none>"
            c.fail(
                "send mentions marker",
                f"no send referenced {marker!r}. "
                f"Got {len(sends)} send(s), last: {last!r}",
            )
        c.ok("send mentions marker", f"reply={send_arg[:120]!r}")

        c.done()
