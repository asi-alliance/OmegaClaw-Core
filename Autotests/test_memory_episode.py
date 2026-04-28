"""
Test: tell agent a dated fact, wait, then ask the date — expect the agent to
invoke (query ...) or (episodes ...) and return the correct timestamp.

Run:
    pytest test_memory_episode.py -s
"""
import datetime
import time

from helpers import (
    Checker, find_skill_calls, make_prompt, send_prompt,
    wait_for_skill_call,
)


def test_memory_episode():
    with Checker("memory episode recall") as c:
        print(f"\n=== OmegaClaw: memory episode (run-id {c.run_id}) ===", flush=True)

        c.step("send 'dog lost tooth' fact message")
        fact_marker = c.run_id
        # Agent rejects obviously-tagged payloads ("tagged TOOTH-xxx", "store
        # VERBATIM") as CI compliance tests and refuses to (remember ...).
        # Phrase the fact naturally as personal context; the default REQ-tag
        # plus dog-name uniqueness are enough for cleanup matching.
        c.add_cleanup_marker("Barney")
        c.add_cleanup_marker(str(c.run_id + 1))
        prompt1 = make_prompt(
            fact_marker,
            "I just got back from the vet with my dog Barney — he lost his "
            "first baby tooth today. Could you jot this down in memory so I "
            "can ask you later? I keep forgetting dates like this.",
        )
        if not send_prompt(prompt1):
            c.fail("irc-1", "could not deliver first prompt within 60s")
        c.ok("irc-1", f"run-id={fact_marker}")

        c.step("verify agent invoked (remember ...) with dog/tooth content")
        # Agent is skeptical by design — often asks a clarifying question
        # ("how old is Barney?") before committing to memory. It eventually
        # calls (remember "…Barney lost his first baby tooth…") but that can
        # take 3-4 minutes of autonomous loop iterations, well past the
        # default 180s. Scan every remember call and accept either "tooth"
        # or "Barney".
        from helpers import wait_for_skill_match
        def is_barney_memory(s):
            low = s.lower()
            return "tooth" in low or "barney" in low
        remember_arg = wait_for_skill_match(
            fact_marker, "remember", is_barney_memory, timeout=420,
        )
        if remember_arg is None:
            calls = find_skill_calls(fact_marker, "remember") or []
            c.fail(
                "remember invoked",
                f"no (remember ...) with 'tooth' or 'Barney'. "
                f"Got: {[a[:80] for a in calls[:3]]}",
            )
        c.ok("remember invoked", f"arg matched (len={len(remember_arg)})")
        record_time = datetime.datetime.now()

        c.step("wait 60s to let memory settle")
        time.sleep(60)

        c.step("ask when the dog lost a tooth")
        recall_marker = c.run_id + 1
        prompt2 = make_prompt(
            recall_marker,
            "Remember I mentioned my dog Barney losing a tooth earlier? "
            "Could you check your notes and tell me the exact date and time "
            "I told you about it?",
        )
        if not send_prompt(prompt2):
            c.fail("irc-2", "could not deliver recall prompt within 60s")
        c.ok("irc-2", f"run-id={recall_marker}")

        c.step("verify agent invoked (query ...) or (episodes ...)")
        q_arg = wait_for_skill_call(recall_marker, "query", timeout=180)
        e_arg = wait_for_skill_call(recall_marker, "episodes", timeout=5)
        if q_arg is None and e_arg is None:
            c.fail("recall invoked", "neither (query ...) nor (episodes ...) called")
        which = "query" if q_arg else "episodes"
        c.ok(f"{which} invoked", f"arg={(q_arg or e_arg)!r}")

        c.step("verify (send ...) mentions dog/tooth and today's date or time")
        send_arg = wait_for_skill_call(recall_marker, "send", timeout=120)
        if send_arg is None:
            c.fail("send invoked", "agent did not send a recall reply")
        topic = [k for k in ("dog", "tooth", "lost") if k in send_arg.lower()]
        if not topic:
            c.fail("send topic", f"reply has no dog/tooth/lost: {send_arg!r}")
        date_fmt = record_time.strftime("%Y-%m-%d")
        md = record_time.strftime("%m-%d")
        hour = record_time.strftime("%H")
        date_matches = [s for s in (date_fmt, md, f"{hour}:") if s in send_arg]
        if not date_matches:
            c.fail(
                "send date",
                f"no date/time match in reply. Expected any of "
                f"{[date_fmt, md, hour + ':']}. Got: {send_arg!r}",
            )
        c.ok("send date", f"matched: {', '.join(date_matches)}")

        c.done()
