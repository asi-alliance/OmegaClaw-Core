"""
Test: tell agent a dated fact, wait, then ask the date — expect the agent to
invoke (query ...) or (episodes ...) and return the correct timestamp.

Run:
    pytest test_memory_episode.py -s
"""
import datetime
import re
import time

from helpers import (
    Checker, find_skill_calls, make_prompt, read_history, send_prompt,
    try_with_clarification, wait_for_skill_match,
)


_RECORD_TS_RE = re.compile(r'\("(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2})"')


def _record_timestamp(run_id):
    """Return the leading "YYYY-MM-DD HH:MM:SS" timestamp of the
    history.metta record block that mentions REQ-{run_id}, parsed as
    datetime. Falls back to None if not found.

    The agent stamps each iteration block with its own clock; that is
    what the recall reply will quote, not the test-side datetime.now()
    which can be off by tens of seconds.
    """
    content = read_history()
    if not content:
        return None
    tag = f"REQ-{run_id}"
    idx = content.find(tag)
    if idx == -1:
        return None
    last_open = content.rfind('("20', 0, idx)
    if last_open == -1:
        return None
    m = _RECORD_TS_RE.match(content[last_open:])
    if not m:
        return None
    try:
        return datetime.datetime.strptime(m.group(1), "%Y-%m-%d %H:%M:%S")
    except ValueError:
        return None


def _date_candidates(record_time):
    """Build the set of date/time substrings any of which we accept as
    proof that the reply pinpoints when the fact was stored."""
    iso_date = record_time.strftime("%Y-%m-%d")
    short_date = record_time.strftime("%m-%d")
    hour = record_time.strftime("%H")
    full_month = record_time.strftime("%B")
    abbr_month = record_time.strftime("%b")
    day_no_pad = str(record_time.day)
    day_padded = record_time.strftime("%d")

    english_long = [
        f"{full_month} {day_no_pad}",
        f"{full_month} {day_padded}",
        f"{day_no_pad} {full_month}",
        f"{day_padded} {full_month}",
    ]
    english_abbr = [
        f"{abbr_month} {day_no_pad}",
        f"{abbr_month} {day_padded}",
    ] if abbr_month != full_month else []

    return (
        iso_date,
        short_date,
        f"{hour}:",
        *english_long,
        *english_abbr,
    )


def test_memory_episode():
    with Checker("memory episode recall") as c:
        print(f"\n=== Omega: memory episode (run-id {c.run_id}) ===", flush=True)

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
        # take 3-4 minutes of autonomous loop iterations.
        def is_barney_memory(s):
            low = s.lower()
            return "tooth" in low or "barney" in low

        remember_arg = wait_for_skill_match(
            fact_marker, "remember", is_barney_memory, timeout=180,
        )
        if remember_arg is None:
            calls = find_skill_calls(fact_marker, "remember") or []
            c.fail(
                "remember invoked",
                f"no (remember ...) with 'tooth' or 'Barney'. "
                f"Got: {[a[:80] for a in calls[:3]]}",
            )
        c.ok("remember invoked", f"arg matched (len={len(remember_arg)})")

        # Source of truth for the recall: the timestamp the agent itself
        # stamped onto the history.metta record. Fall back to the test-
        # side wall clock only if parsing fails.
        record_time = _record_timestamp(fact_marker) or datetime.datetime.now()
        print(f"       record_time={record_time:%Y-%m-%d %H:%M:%S}", flush=True)

        c.step("wait 60s to let memory settle")
        time.sleep(60)

        c.step("ask when the dog lost a tooth (graded recall + reply)")
        recall_marker = c.run_id + 1
        # Directive prompt: the agent has freedom to choose query or
        # episodes, but must produce a single send carrying the date and
        # the topic words. Without this directive the agent often runs
        # the lookup, records it via pin, and goes idle without replying.
        prompt2 = make_prompt(
            recall_marker,
            "I told you earlier that my dog Barney lost his first baby "
            "tooth. Use your query or episodes skill to look that up in "
            "your notes, then reply with ONE short send that contains "
            "both the date and the words dog and tooth.",
        )
        if not send_prompt(prompt2):
            c.fail("irc-2", "could not deliver recall prompt within 60s")
        c.ok("irc-2", f"run-id={recall_marker}")

        date_candidates = _date_candidates(record_time)
        topic_words = ("dog", "tooth", "lost", "barney")

        def is_recall_reply(s):
            low = s.lower()
            if not any(w in low for w in topic_words):
                return False
            return any(
                cand in s or cand.lower() in low
                for cand in date_candidates
            )

        def ready_check():
            sends = find_skill_calls(recall_marker, "send") or []
            for s in sends:
                if is_recall_reply(s):
                    return s
            return None

        clarification = (
            "I still need the date in a reply. Use query or episodes on "
            "Barney's tooth, then send ONE short message that includes "
            "the date and the words dog and tooth."
        )
        grade, send_arg = try_with_clarification(
            c, ready_check, clarification,
            timeout_first=180, timeout_second=180,
        )
        c.set_grade(grade)
        if grade == Checker.GRADE_FAIL:
            sends = find_skill_calls(recall_marker, "send") or []
            last = sends[-1] if sends else "<none>"
            c.fail(
                "recall reply",
                f"no send with topic + date. "
                f"Date candidates: {list(date_candidates)}. "
                f"Got {len(sends)} send(s), last: {last!r}",
            )
        c.ok("recall reply", f"reply={send_arg[:120]!r} (grade={grade})")

        c.step("verify agent invoked (query ...) or (episodes ...)")
        q_calls = find_skill_calls(recall_marker, "query") or []
        e_calls = find_skill_calls(recall_marker, "episodes") or []
        if not q_calls and not e_calls:
            c.fail(
                "recall skill",
                "neither (query ...) nor (episodes ...) called in recall window",
            )
        which = "query" if q_calls else "episodes"
        c.ok(f"{which} invoked", f"q={len(q_calls)}, e={len(e_calls)}")

        c.done()
