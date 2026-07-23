"""Unit tests for the cron/webhook scheduler (Issue #17).

Pure-Python; imports src/scheduler.py directly against a temp jobs DB with an INJECTED clock
(deterministic — no real waiting). Runs under pytest and standalone.
"""
import hashlib
import hmac
import json
import os
import sys
import tempfile

_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_SRC = os.path.join(_REPO_ROOT, "src")
for _p in (_SRC, _REPO_ROOT):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import scheduler as sch  # noqa: E402

T0 = 1_000_000.0


def _db():
    d = tempfile.mkdtemp(prefix="sch_")
    os.environ["OMEGACLAW_JOBS_DB"] = os.path.join(d, "jobs.db")
    os.environ["OMEGACLAW_SESSION_DB"] = os.path.join(d, "s.db")
    sch.reset(os.environ["OMEGACLAW_JOBS_DB"])


def _clean():
    for k in ("OMEGACLAW_JOBS_DB", "OMEGACLAW_SESSION_DB"):
        os.environ.pop(k, None)


def test_once_fires_once_then_done():
    _db()
    try:
        ran = []
        sch.create_job("o1", "once", str(T0 + 10), prompt="hi", now=T0)
        assert sch.run_due(now=T0 + 5, runner=lambda j, c: ran.append(j["id"]))["count"] == 0
        assert sch.run_due(now=T0 + 11, runner=lambda j, c: ran.append(j["id"]) or "out")["count"] == 1
        assert sch.get_job("o1")["next_run"] is None                # done
        assert sch.run_due(now=T0 + 999, runner=lambda j, c: "x")["count"] == 0
        assert ran == ["o1"]
    finally:
        _clean()


def test_interval_reschedules_and_cron_creates():
    _db()
    try:
        sch.create_job("iv", "interval", "60", now=T0)
        before = sch.get_job("iv")["next_run"]
        sch.run_due(now=before + 0.1, runner=lambda j, c: "tick")
        assert sch.get_job("iv")["next_run"] > before
        assert sch.create_job("cr", "cron", "*/5 * * * *", now=T0)["ok"]
        assert sch.create_job("bad", "cron", "not a cron", now=T0)["ok"] is False
    finally:
        _clean()


def test_unsafe_id_and_runaway_interval_rejected():
    _db()
    try:
        assert sch.create_job("../x", "once", str(T0))["ok"] is False
        assert sch.create_job("a/b", "once", str(T0))["ok"] is False
        assert sch.create_job("toofast", "interval", "0.1", now=T0)["ok"] is False
    finally:
        _clean()


def test_restart_recovery_no_lost_or_duplicate():
    _db()
    try:
        sch.create_job("survive", "once", str(T0), prompt="x", now=T0)
        # "restart" = a fresh run_due call on the same persisted DB, long overdue
        f1 = sch.run_due(now=T0 + 5000, runner=lambda j, c: "out")
        f2 = sch.run_due(now=T0 + 9000, runner=lambda j, c: "out")
        assert [f["id"] for f in f1["fired"]] == ["survive"]        # not lost
        assert f2["count"] == 0                                     # not duplicated
    finally:
        _clean()


def test_failure_alerts_and_empty_policy():
    _db()
    try:
        alerts = []

        def alert(job, msg):
            alerts.append(job["id"])

        sch.create_job("boom", "once", str(T0), prompt="boom", now=T0)
        sch.run_due(now=T0 + 1, runner=lambda j, c: (_ for _ in ()).throw(RuntimeError("x")),
                    alert_fn=alert)
        assert "boom" in alerts

        sch.create_job("silent", "once", str(T0), now=T0, on_empty="silent")
        sch.create_job("noisy", "once", str(T0), now=T0, on_empty="alert")
        a2 = []
        sch.run_due(now=T0 + 1, runner=lambda j, c: "", alert_fn=lambda j, m: a2.append(j["id"]))
        assert "noisy" in a2 and "silent" not in a2
    finally:
        _clean()


def test_delivery_only_on_nonempty_success():
    _db()
    try:
        delivered = []
        sch.create_job("d", "once", str(T0), prompt="p", delivery="chan", now=T0)
        sch.run_due(now=T0 + 1, runner=lambda j, c: "hello",
                    delivery_fn=lambda job, out: delivered.append((job["id"], out)))
        assert delivered == [("d", "hello")]
    finally:
        _clean()


def test_context_chaining():
    _db()
    try:
        sch.create_job("first", "once", str(T0), now=T0)
        sch.run_due(now=T0 + 1, runner=lambda j, c: "FIRST-OUTPUT")
        seen = {}
        sch.create_job("second", "once", str(T0 + 5), chain_from="first", now=T0)
        sch.run_due(now=T0 + 6, runner=lambda j, c: seen.setdefault("chain", c["chain_output"]) or "ok")
        assert seen["chain"] == "FIRST-OUTPUT"
    finally:
        _clean()


def test_recursion_guard():
    _db()
    try:
        sch.create_job("r", "once", str(T0), now=T0)

        def _runner(job, ctx):
            return "nested=" + str(sch.create_job("child", "once", str(T0), now=T0)["ok"])

        sch.run_due(now=T0 + 1, runner=_runner)
        assert "nested=False" in sch.get_job("r")["last_output"]
        assert sch.get_job("child") is None
    finally:
        _clean()


def test_cron_respects_all_five_fields():
    """Regression (PR #42 review): a `*` DOW must not short-circuit the minute/hour/dom/mon
    checks (daily/monthly specs were firing every minute)."""
    import calendar
    import time as _t

    def gm(s):
        return _t.gmtime(calendar.timegm(_t.strptime(s, "%Y-%m-%d %H:%M")))

    # 0 0 * * * must NOT match midday, and its next fire is the next midnight
    assert sch._cron_matches("0 0 * * *", gm("2026-07-08 12:34")) is False
    nxt = sch._cron_next("0 0 * * *", calendar.timegm(_t.strptime("2026-07-08 12:34", "%Y-%m-%d %H:%M")))
    assert _t.strftime("%Y-%m-%d %H:%M", _t.gmtime(nxt)) == "2026-07-09 00:00"
    # */5 from an off-minute → next 5-minute boundary
    off = calendar.timegm(_t.strptime("2026-07-08 12:34", "%Y-%m-%d %H:%M"))
    assert _t.strftime("%H:%M", _t.gmtime(sch._cron_next("*/5 * * * *", off))) == "12:35"
    # DOW-specific spec: matches only when minute/hour also match (2026-07-06 is a Monday)
    assert sch._cron_matches("0 9 * * 1", gm("2026-07-06 09:00")) is True
    assert sch._cron_matches("30 9 * * 1", gm("2026-07-06 09:00")) is False   # minute mismatch
    assert sch._cron_matches("0 9 * * 1", gm("2026-07-07 09:00")) is False    # Tuesday


def test_webhook_transient_id_never_deletes_durable_job():
    """Regression (PR #42 review): a webhook's transient job must not delete a pre-existing
    durable job even if the generated id collides."""
    import uuid
    _db()
    try:
        sch.webhook_subscribe("gh", "", {"prompt": "x"})
        fixed = "abcdef0123456789"

        class _U:
            hex = fixed
        orig = uuid.uuid4
        uuid.uuid4 = lambda: _U()
        try:
            sch.create_job("wh-gh-" + fixed, "once", "9999999999", prompt="DURABLE", now=0)
            r = sch.webhook_event("gh", {"e": "push"}, runner=lambda j, c: "ok")
        finally:
            uuid.uuid4 = orig
        assert r["ok"] is False and "already exists" in (r.get("error") or "")
        assert sch.get_job("wh-gh-" + fixed) is not None          # durable job survived
        assert sch.get_job("wh-gh-" + fixed)["prompt"] == "DURABLE"
    finally:
        _clean()


def test_concurrent_heartbeats_run_due_occurrence_once():
    """Regression (PR #42 re-review): two heartbeats that both SELECT the same due row (stale
    select) must not both execute it — the atomic claim (CAS on next_run) lets exactly one win."""
    _db()
    try:
        sch.create_job("race", "once", str(T0), prompt="hi", now=T0)
        # both heartbeats selected the same due row at the same next_run
        stale = sch.due_jobs(T0 + 1)[0]
        ran = []
        c1, c2 = sch.connect(), sch.connect()
        try:
            r1 = sch._execute_one(dict(stale), T0 + 1, lambda j, c: ran.append(j["id"]) or "o",
                                  c1, advance=True)
            r2 = sch._execute_one(dict(stale), T0 + 1, lambda j, c: ran.append(j["id"]) or "o",
                                  c2, advance=True)
        finally:
            c1.close()
            c2.close()
        assert ran == ["race"], ran                    # ran exactly once
        assert r1 is not None and r2 is None            # second lost the atomic claim
        assert sch.get_job("race")["fires"] == 1        # persisted fire count reflects one run
    finally:
        _clean()


def test_concurrent_run_due_threads_fire_once():
    """Two concurrent run_due() threads racing the same due row fire it exactly once."""
    import threading
    _db()
    try:
        sch.create_job("r", "interval", "60", now=T0)
        ran = []
        barrier = threading.Barrier(2)
        orig = sch.due_jobs

        def patched(now, conn=None):
            d = orig(now, conn=conn)
            try:
                barrier.wait(timeout=5)                 # both hold the due row before advancing
            except threading.BrokenBarrierError:
                pass
            return d

        sch.due_jobs = patched
        try:
            threads = [threading.Thread(target=lambda: sch.run_due(now=T0 + 5000,
                                                                   runner=lambda j, c: ran.append(1)))
                       for _ in range(2)]
            for t in threads:
                t.start()
            for t in threads:
                t.join()
        finally:
            sch.due_jobs = orig
        assert len(ran) == 1, ran
        assert sch.get_job("r")["fires"] == 1
    finally:
        _clean()


def test_webhook_signature_validation():
    _db()
    try:
        secret = "shh"
        sch.webhook_subscribe("gh", secret, {"prompt": "handle"})
        payload = {"event": "push", "n": 1}
        raw = json.dumps(payload, sort_keys=True).encode("utf-8")
        good = hmac.new(secret.encode(), raw, hashlib.sha256).hexdigest()
        assert sch.webhook_event("gh", payload, good, runner=lambda j, c: "ok")["ok"]
        assert sch.webhook_event("gh", payload, "bad").get("rejected") is True
        assert sch.webhook_event("gh", payload, None).get("rejected") is True
        # unknown subscription
        assert sch.webhook_event("nope", payload, good)["ok"] is False
    finally:
        _clean()


def test_webhook_runner_receives_event_payload():
    """Regression (PR #42 re-review): the runner must get the validated (nested) event in ctx."""
    _db()
    try:
        sch.webhook_subscribe("gh", "", {"prompt": "handle"})
        seen = {}
        sch.webhook_event("gh", {"issue": {"title": "bug", "number": 7}, "repo": "acme"},
                          runner=lambda job, ctx: seen.update({"event": ctx.get("event")}) or "ok")
        assert seen["event"] == {"issue": {"title": "bug", "number": 7}, "repo": "acme"}
    finally:
        _clean()


def test_invalid_cron_fails_closed():
    """Regression (PR #42 re-review): a malformed cron (*/0, out-of-range, non-int) returns a
    structured error instead of crashing (ZeroDivisionError) or silently never firing."""
    _db()
    try:
        assert sch.create_job("z", "cron", "*/0 * * * *", now=T0)["ok"] is False
        assert sch.create_job("r", "cron", "99 * * * *", now=T0)["ok"] is False
        assert sch.create_job("n", "cron", "x * * * *", now=T0)["ok"] is False
        assert sch.create_job("f", "cron", "* * *", now=T0)["ok"] is False       # wrong field count
        assert sch.create_job("ok", "cron", "*/5 0 * * 1", now=T0)["ok"] is True  # valid still works
    finally:
        _clean()


def test_run_now_does_not_resume_paused_or_reschedule():
    """Regression (PR #42 re-review): a one-off `run` must not resume a paused job or change its
    next_run, and must not fire other due jobs."""
    _db()
    try:
        sch.create_job("p", "interval", "60", prompt="hi", now=T0)
        sch.pause("p")
        # an unrelated job is also due — run_now must NOT fire it
        other = []
        sch.create_job("other", "once", str(T0), now=T0)
        before = sch.get_job("p")
        r = sch.run_now("p", runner=lambda j, c: "done")
        after = sch.get_job("p")
        assert r["ok"] and r["fired"]["status"] == "ok"
        assert after["enabled"] == 0                       # still paused
        assert after["next_run"] == before["next_run"]     # not rescheduled
        assert sch.get_job("other")["last_status"] is None  # unrelated due job untouched
    finally:
        _clean()


if __name__ == "__main__":
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_") and callable(v)]
    failed = 0
    for fn in fns:
        try:
            fn()
            print("ok:", fn.__name__)
        except AssertionError as e:
            failed += 1
            print("FAIL:", fn.__name__, e)
    if failed:
        sys.exit(1)
    print(f"\nAll {len(fns)} scheduler tests passed")
