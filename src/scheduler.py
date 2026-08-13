"""Cron, webhook & event-triggered autonomous runs (Issue #17).

OmegaClaw was interactive/benchmark-loop oriented; automation (monitors, daily summaries,
recurring benchmarks, CI watchers, external event handlers) needed ad hoc shell wrappers. This
adds first-class **durable job definitions** + a **scheduler** + a **webhook adapter**:

- Jobs live in a durable SQLite store, so due jobs **survive a process restart** (the persisted
  ``next_run`` means an overdue job still fires exactly once — never lost, never duplicated).
- Schedules: ``once`` (at an epoch), ``interval`` (every N seconds), and a minimal 5-field
  ``cron`` (``*`` / int / ``*/n`` / comma-lists).
- ``run_due(now, runner)`` fires everything due at ``now`` — the clock is **injected**, so tests
  drive a simulated timeline deterministically. Each run executes in its **own session**
  (Issue #16), delivers non-empty output via a delivery hook, and on failure (or an empty result
  when ``on_empty="alert"``) raises an **alert**; ``on_empty="silent"`` watchdogs stay quiet. A
  bad job (incl. a workdir the io policy forbids) fails **only itself** — it can't abort the tick.
- ``run_forever(interval)`` is the **operator** that actually drives the store: the
  ``omegaclaw-cron daemon`` heartbeat loops ``run_due`` so due jobs fire on their own. Its
  ``delivery_fn``/``alert_fn`` default to a **durable outbox** (``memory/cron_outbox.jsonl``) so a
  scheduled result/alert is never silently dropped; a live deployment injects channel-backed hooks
  and a real agent ``runner`` here — that is the intended extension seam.
- Each run gets a **working dir** (an explicit ``--workdir``, validated against the io policy's
  read_write roots; else an auto-cleaned temp dir, removed after the run — no unbounded growth).
- **Context chaining**: a job may consume the previous job's output.
- Safeguards: **recursion is refused** while a job runs (no self-scheduling storms) and a
  per-job minimum interval guards against runaway loops.
- **Webhooks**: subscriptions carry an HMAC secret; an event with a bad/missing signature is
  **rejected** (no run); a valid one triggers a run carrying validated event metadata.

Stdlib only. DB path ``OMEGACLAW_JOBS_DB`` (default ``memory/jobs.db``).
"""

from __future__ import annotations

import hashlib
import hmac
import json
import os
import shutil
import sqlite3
import tempfile
import threading
import time
from typing import Any, Callable, Dict, List, Optional

try:
    import session_store
except ImportError:  # pragma: no cover
    from src import session_store


def is_safe_skill_name(name: Any) -> bool:
    """True iff ``name`` is safe as a lookup key AND a filesystem path segment — rejects empties,
    path separators, ``..`` traversal, absolute paths, and NULs. Inlined (from skill_loader) to keep
    the scheduler independent of the skills subsystem; used to validate job/subscription ids that
    become filesystem path segments."""
    return (
        isinstance(name, str) and bool(name)
        and name not in (".", "..")
        and ".." not in name
        and "/" not in name and "\\" not in name
        and not os.path.isabs(name)
        and "\x00" not in name
    )


_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_MIN_INTERVAL = float(os.environ.get("OMEGACLAW_JOB_MIN_INTERVAL", "1"))   # runaway guard


# --------------------------------------------------------------------------- io-policy guard

def _allowed_workdir_roots() -> Optional[List[str]]:
    """Read-write base paths a job workdir must sit under, or ``None`` when it can't be
    determined (then the caller does NOT block). Priority: the explicit
    ``OMEGACLAW_JOB_WORKDIR_ROOTS`` env (``os.pathsep``-separated — deterministic, stdlib-only) and
    otherwise a best-effort read of the repo security policy's ``read_write`` list (needs the
    optional yaml/py_landlock deps; absent on a bare host, so we fail open there)."""
    env = os.environ.get("OMEGACLAW_JOB_WORKDIR_ROOTS")
    if env is not None:
        roots = [os.path.abspath(p) for p in env.split(os.pathsep) if p.strip()]
        return roots or None
    try:  # optional: profile.policy pulls yaml + py_landlock, unavailable on a bare test host
        from profile import policy as _pol
        fsp = _pol.FileSystemPolicy()
        fsp.load_file(os.path.join(_REPO_ROOT, "profile", "policy.yaml"))
        return [os.path.abspath(str(p)) for p in fsp._read_write] or None
    except Exception:  # noqa: BLE001 - can't determine -> caller allows
        return None


def _workdir_allowed(workdir: str) -> bool:
    """True iff ``workdir`` resolves inside an allowed read-write root (per the io policy). Returns
    True when the policy is undeterminable so host-only runs aren't blocked; a configured policy
    fails closed on a path outside its read_write roots (e.g. a job trying to write ``/etc``)."""
    roots = _allowed_workdir_roots()
    if not roots:
        return True
    real = os.path.realpath(os.path.abspath(workdir))
    for root in roots:
        r = os.path.realpath(root)
        # rstrip so a root of "/" (realpath keeps its trailing sep) contains every subpath instead
        # of comparing against "//"; normal roots have no trailing sep so this is a no-op.
        if real == r or real.startswith(r.rstrip(os.sep) + os.sep):
            return True
    return False


# --------------------------------------------------------------------------- durable output sink

def _outbox_path() -> str:
    env = os.environ.get("OMEGACLAW_CRON_OUTBOX")
    if env:
        return env if os.path.isabs(env) else os.path.join(_REPO_ROOT, env)
    return os.path.join(_REPO_ROOT, "memory", "cron_outbox.jsonl")


def _append_outbox(kind: str, job: Dict[str, Any], text: str) -> None:
    """Append one run result/alert to the durable JSONL outbox (a policy read_write path), so a
    scheduled run's output is captured rather than silently dropped. Best-effort: never raises."""
    path = _outbox_path()
    try:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        rec = {"ts": time.time(), "kind": kind, "job": job.get("id"),
               "delivery": job.get("delivery") or "", "text": text}
        with open(path, "a", encoding="utf-8") as fh:
            fh.write(json.dumps(rec) + "\n")
    except Exception:  # noqa: BLE001
        pass


def _default_delivery(job: Dict[str, Any], output: str) -> None:
    """Default delivery sink: append the run output to the durable outbox. This is the seam a live
    deployment overrides with a channel/provider push (see ``run_forever``)."""
    _append_outbox("delivery", job, output)


def _default_alert(job: Dict[str, Any], message: str) -> None:
    """Default alert sink: record durably AND echo to stdout (so a bare `tick`/`daemon` surfaces
    failures even without a wired alert channel)."""
    _append_outbox("alert", job, message)
    print("[scheduler] ALERT job={} {}".format(job.get("id"), message), flush=True)


_SCHEMA = """
CREATE TABLE IF NOT EXISTS jobs (
    id TEXT PRIMARY KEY, kind TEXT, spec TEXT, prompt TEXT, skills TEXT, workdir TEXT,
    delivery TEXT, on_empty TEXT, enabled INTEGER DEFAULT 1, created REAL,
    next_run REAL, last_run REAL, last_status TEXT, last_output TEXT, fires INTEGER DEFAULT 0,
    chain_from TEXT, meta TEXT
);
CREATE TABLE IF NOT EXISTS webhooks (
    id TEXT PRIMARY KEY, secret TEXT, job_template TEXT, created REAL
);
CREATE INDEX IF NOT EXISTS idx_jobs_next ON jobs(enabled, next_run);
"""

_in_run = threading.local()   # recursion guard: create_job refused while a job runs


class SchedulerError(Exception):
    pass


def db_path() -> str:
    env = os.environ.get("OMEGACLAW_JOBS_DB")
    if env:
        return env if os.path.isabs(env) else os.path.join(_REPO_ROOT, env)
    return os.path.join(_REPO_ROOT, "memory", "jobs.db")


def connect(path: Optional[str] = None) -> sqlite3.Connection:
    p = path or db_path()
    if p != ":memory:":
        os.makedirs(os.path.dirname(p), exist_ok=True)
    conn = sqlite3.connect(p, timeout=30)
    conn.row_factory = sqlite3.Row
    # wait (don't error) when another heartbeat holds the write lock; the atomic claim below
    # serializes concurrent heartbeats so a due occurrence runs exactly once.
    conn.execute("PRAGMA busy_timeout=30000")
    conn.executescript(_SCHEMA)
    conn.commit()
    return conn


def reset(path: Optional[str] = None) -> None:
    p = path or db_path()
    if p != ":memory:" and os.path.exists(p):
        os.remove(p)


# --------------------------------------------------------------------------- cron

def _cron_field_match(field: str, value: int, lo: int, hi: int) -> bool:
    if field == "*":
        return True
    for part in field.split(","):
        if part.startswith("*/"):
            try:
                step = int(part[2:])
                if step > 0 and value % step == 0:      # step<=0 is invalid, never matches
                    return True
            except ValueError:
                pass
        elif "-" in part:
            try:
                a, b = part.split("-", 1)
                if int(a) <= value <= int(b):
                    return True
            except ValueError:
                pass
        else:
            try:
                if int(part) == value:
                    return True
            except ValueError:
                pass
    return False


def _cron_matches(spec: str, t: time.struct_time) -> bool:
    fields = spec.split()
    if len(fields) != 5:
        raise SchedulerError("cron spec must have 5 fields (m h dom mon dow): {!r}".format(spec))
    m, h, dom, mon, dow = fields
    # cron day-of-week: 0 or 7 = Sunday, 1=Mon..6=Sat. Python tm_wday: 0=Mon..6=Sun.
    cron_dow = (t.tm_wday + 1) % 7                       # -> 0=Sun,1=Mon,..,6=Sat
    dow_ok = (_cron_field_match(dow, cron_dow, 0, 6)
              or (cron_dow == 0 and _cron_field_match(dow, 7, 0, 7)))   # accept "7" for Sunday
    # ALL five fields must match (the dow term stays INSIDE the conjunction — a `*` dow must not
    # short-circuit the minute/hour/day/month checks, which previously let daily specs fire every
    # minute).
    return (_cron_field_match(m, t.tm_min, 0, 59)
            and _cron_field_match(h, t.tm_hour, 0, 23)
            and _cron_field_match(dom, t.tm_mday, 1, 31)
            and _cron_field_match(mon, t.tm_mon, 1, 12)
            and dow_ok)


def _validate_cron(spec: str) -> None:
    """Raise SchedulerError for a malformed 5-field cron spec (bad step / range / token), so
    create_job fails closed instead of storing a job that silently never fires (or crashes)."""
    fields = spec.split()
    if len(fields) != 5:
        raise SchedulerError("cron spec must have 5 fields (m h dom mon dow): {!r}".format(spec))
    ranges = [(0, 59), (0, 23), (1, 31), (1, 12), (0, 7)]
    for field, (lo, hi) in zip(fields, ranges):
        for part in field.split(","):
            if part == "*":
                continue
            if part.startswith("*/"):
                try:
                    if int(part[2:]) <= 0:
                        raise SchedulerError("cron step must be > 0: {!r}".format(part))
                except ValueError:
                    raise SchedulerError("cron step not an integer: {!r}".format(part))
                continue
            toks = part.split("-") if "-" in part else [part]
            for tok in toks:
                try:
                    v = int(tok)
                except ValueError:
                    raise SchedulerError("cron field token not an integer: {!r}".format(tok))
                if not (lo <= v <= hi):
                    raise SchedulerError("cron token {} out of range [{}, {}]".format(v, lo, hi))


def _cron_next(spec: str, after_epoch: float) -> Optional[float]:
    """Next epoch (UTC, minute-aligned) strictly after ``after_epoch`` matching ``spec``."""
    start = int(after_epoch // 60 + 1) * 60
    for i in range(0, 366 * 24 * 60):        # cap: one year
        cand = start + i * 60
        if _cron_matches(spec, time.gmtime(cand)):
            return float(cand)
    return None


def _compute_next(kind: str, spec: str, after: float) -> Optional[float]:
    if kind == "once":
        return float(spec)
    if kind == "interval":
        n = max(_MIN_INTERVAL, float(spec))
        return after + n
    if kind == "cron":
        return _cron_next(spec, after)
    raise SchedulerError("unknown job kind: {!r}".format(kind))


# --------------------------------------------------------------------------- job store

def create_job(job_id: str, kind: str, spec: str, *, prompt: str = "", skills: Optional[List[str]] = None,
               workdir: str = "", delivery: str = "", on_empty: str = "silent",
               chain_from: str = "", meta: Optional[Dict[str, Any]] = None, now: Optional[float] = None,
               conn: Optional[sqlite3.Connection] = None) -> Dict[str, Any]:
    """Create a durable job. ``now`` (injectable clock) seeds the first ``next_run``."""
    if getattr(_in_run, "active", False):
        return {"ok": False, "error": "recursive job creation refused while a job is running"}
    if not is_safe_skill_name(job_id):
        return {"ok": False, "error": "unsafe job id: {!r}".format(job_id)}
    if workdir and not _workdir_allowed(workdir):
        return {"ok": False, "error": "workdir not permitted by io policy: {}".format(workdir)}
    now = time.time() if now is None else now
    own = conn is None
    conn = conn or connect()
    try:
        if conn.execute("SELECT 1 FROM jobs WHERE id=?", (job_id,)).fetchone():
            return {"ok": False, "error": "job already exists: {}".format(job_id)}
        try:
            if kind == "interval" and float(spec) < _MIN_INTERVAL:
                return {"ok": False, "error": "interval below min {}s (runaway guard)".format(_MIN_INTERVAL)}
            if kind == "cron":
                _validate_cron(spec)                 # fail closed on a malformed cron spec
            nxt = _compute_next(kind, spec, now)
        except (SchedulerError, ValueError, ZeroDivisionError) as e:
            return {"ok": False, "error": str(e)}
        conn.execute(
            "INSERT INTO jobs(id,kind,spec,prompt,skills,workdir,delivery,on_empty,enabled,created,"
            "next_run,last_run,last_status,last_output,fires,chain_from,meta) "
            "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (job_id, kind, str(spec), prompt or "", json.dumps(skills or []),
             workdir or "", delivery or "", on_empty, 1, now, nxt, None, None, None, 0,
             chain_from or "", json.dumps(meta or {})))
        conn.commit()
        return {"ok": True, "id": job_id, "kind": kind, "next_run": nxt}
    finally:
        if own:
            conn.close()


def _set(conn, job_id, **fields):
    cols = ", ".join("{}=?".format(k) for k in fields)
    conn.execute("UPDATE jobs SET {} WHERE id=?".format(cols), (*fields.values(), job_id))
    conn.commit()


def list_jobs(conn: Optional[sqlite3.Connection] = None) -> List[Dict[str, Any]]:
    own = conn is None
    conn = conn or connect()
    try:
        return [dict(r) for r in conn.execute("SELECT * FROM jobs ORDER BY next_run").fetchall()]
    finally:
        if own:
            conn.close()


def get_job(job_id: str, conn: Optional[sqlite3.Connection] = None) -> Optional[Dict[str, Any]]:
    own = conn is None
    conn = conn or connect()
    try:
        r = conn.execute("SELECT * FROM jobs WHERE id=?", (job_id,)).fetchone()
        return dict(r) if r else None
    finally:
        if own:
            conn.close()


def pause(job_id, conn=None):
    return _toggle(job_id, 0, conn)


def resume(job_id, conn=None):
    return _toggle(job_id, 1, conn)


def _toggle(job_id, enabled, conn):
    own = conn is None
    conn = conn or connect()
    try:
        if not conn.execute("SELECT 1 FROM jobs WHERE id=?", (job_id,)).fetchone():
            return {"ok": False, "error": "no such job: {}".format(job_id)}
        _set(conn, job_id, enabled=enabled)
        return {"ok": True, "id": job_id, "enabled": bool(enabled)}
    finally:
        if own:
            conn.close()


def remove(job_id, conn=None):
    own = conn is None
    conn = conn or connect()
    try:
        cur = conn.execute("DELETE FROM jobs WHERE id=?", (job_id,))
        conn.commit()
        return {"ok": cur.rowcount > 0, "id": job_id}
    finally:
        if own:
            conn.close()


def due_jobs(now: float, conn: Optional[sqlite3.Connection] = None) -> List[Dict[str, Any]]:
    own = conn is None
    conn = conn or connect()
    try:
        rows = conn.execute("SELECT * FROM jobs WHERE enabled=1 AND next_run IS NOT NULL "
                            "AND next_run <= ? ORDER BY next_run", (now,)).fetchall()
        return [dict(r) for r in rows]
    finally:
        if own:
            conn.close()


# --------------------------------------------------------------------------- execution

def _default_runner(job: Dict[str, Any], ctx: Dict[str, Any]) -> str:
    """Fallback runner: echoes the prompt. A live deployment passes a runner that
    drives an actual agent run with the job's prompt/skills/workdir."""
    return "ran job {} (prompt chars={})".format(job["id"], len(job.get("prompt") or ""))


def _execute_one(job: Dict[str, Any], now: float, runner: Callable, conn: sqlite3.Connection, *,
                 delivery_fn: Optional[Callable] = None, alert_fn: Optional[Callable] = None,
                 advance: bool = True, extra_ctx: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Run ONE job in its own session + apply delivery/alert. ``advance`` reschedules next_run
    (scheduled fire); a manual/one-off run passes ``advance=False`` so it does not mutate the
    durable schedule/enabled state. ``extra_ctx`` merges into the runner ctx (webhooks inject the
    validated event here)."""
    jid = job["id"]
    if advance:
        # ATOMICALLY CLAIM this occurrence before running (durability + concurrency safety): the
        # UPDATE's WHERE checks the exact next_run we selected, so if another heartbeat already
        # advanced it, our rowcount is 0 and we skip — a due occurrence runs exactly once even
        # with multiple concurrent schedulers against the same DB. Advancing first also means a
        # crash mid-run cannot refire it.
        try:
            nxt = None if job["kind"] == "once" else _compute_next(job["kind"], job["spec"], now)
        except (SchedulerError, ValueError, ZeroDivisionError):
            nxt = None
        cur = conn.execute(
            "UPDATE jobs SET next_run=?, last_run=?, fires=fires+1 "
            "WHERE id=? AND enabled=1 AND next_run=?",
            (nxt, now, jid, job.get("next_run")))
        conn.commit()
        if cur.rowcount != 1:
            return None                      # lost the claim -> another heartbeat is running it
    else:
        nxt = job.get("next_run")
        conn.execute("UPDATE jobs SET last_run=?, fires=fires+1 WHERE id=?", (now, jid))
        conn.commit()
    # derive the session id from the PERSISTED (atomically-incremented) fire count, so concurrent
    # attempts can never share a session id like cron-<job>-1.
    row = conn.execute("SELECT fires FROM jobs WHERE id=?", (jid,)).fetchone()
    fire_no = row[0] if row else (int(job.get("fires") or 0) + 1)
    sid = "cron-{}-{}".format(jid, fire_no)

    # EVERYTHING that can raise for job-specific reasons (workdir resolution, dir creation, the
    # runner itself) lives inside this try, so a bad job fails ONLY itself: an unhandled exception
    # here can never propagate out of _execute_one and abort the surrounding run_due() heartbeat
    # (which would skip every other job due this tick). The occurrence was already claimed above.
    status, output, err = "ok", "", None
    wd = None
    created_tmp = False
    try:
        configured = job.get("workdir") or ""
        if configured:
            if not _workdir_allowed(configured):
                raise SchedulerError("workdir not permitted by io policy: {}".format(configured))
            wd = configured
        else:
            wd = tempfile.mkdtemp(prefix="omegaclaw-cron-{}-".format(jid))
            created_tmp = True                 # ephemeral: we own it, so we remove it after the run
        os.makedirs(wd, exist_ok=True)

        chain_out = None
        if job.get("chain_from"):
            prev = get_job(job["chain_from"], conn=conn)
            chain_out = prev.get("last_output") if prev else None
        ctx = {"job": job, "workdir": wd, "chain_output": chain_out, "now": now}
        if extra_ctx:
            ctx.update(extra_ctx)
        try:
            session_store.begin_session(sid, channel="cron", task=job.get("prompt") or jid)
        except Exception:  # noqa: BLE001
            pass

        _in_run.active = True
        try:
            output = str(runner(job, ctx) or "")
        finally:
            _in_run.active = False
    except Exception as e:  # noqa: BLE001 - setup OR job failure is isolated + alerted below
        status, err = "error", str(e)
    finally:
        # an ephemeral temp workdir is OURS: always remove it, so a job firing on a schedule can't
        # leak a new /tmp dir on every run (unbounded disk growth). A job with an explicit workdir
        # keeps it — the operator manages that directory's lifecycle.
        if created_tmp and wd:
            shutil.rmtree(wd, ignore_errors=True)

    _set(conn, jid, last_status=status, last_output=output)
    try:
        session_store.record_snapshot(sid, 1, {"status": status, "output_chars": len(output)})
        session_store.end_session(sid, status)
    except Exception:  # noqa: BLE001
        pass

    delivered = alerted = False
    if status == "error":
        _alert(alert_fn, job, "job failed: {}".format(err))
        alerted = True
    elif not output.strip():
        if job.get("on_empty") == "alert":
            _alert(alert_fn, job, "job produced empty output")
            alerted = True
        # on_empty == "silent": watchdog stays quiet
    elif job.get("delivery"):
        # deliver only when a destination is configured; fall back to the durable outbox sink so a
        # scheduled result is captured even when no delivery_fn was wired (bare `tick`/`daemon`).
        try:
            (delivery_fn or _default_delivery)(job, output)
            delivered = True
        except Exception:  # noqa: BLE001
            _alert(alert_fn, job, "delivery failed")
            alerted = True
    return {"id": jid, "status": status, "session_id": sid, "next_run": nxt,
            "delivered": delivered, "alerted": alerted, "error": err}


def run_due(now: Optional[float] = None, runner: Optional[Callable] = None, *,
            delivery_fn: Optional[Callable] = None, alert_fn: Optional[Callable] = None,
            conn: Optional[sqlite3.Connection] = None) -> Dict[str, Any]:
    """Fire every job due at ``now`` (injected clock). Each runs in its own session; the persisted
    ``next_run`` is advanced BEFORE running so a crash mid-run can't double-fire it."""
    now = time.time() if now is None else now
    runner = runner or _default_runner
    own = conn is None
    conn = conn or connect()
    try:
        fired = [r for r in (_execute_one(job, now, runner, conn, delivery_fn=delivery_fn,
                                          alert_fn=alert_fn, advance=True)
                             for job in due_jobs(now, conn=conn))
                 if r is not None]   # r is None when this heartbeat lost the atomic claim
        return {"ok": all(f["status"] != "error" for f in fired), "now": now,
                "fired": fired, "count": len(fired)}
    finally:
        if own:
            conn.close()


def run_forever(interval: float = 60.0, *, runner: Optional[Callable] = None,
                delivery_fn: Optional[Callable] = None, alert_fn: Optional[Callable] = None,
                iterations: Optional[int] = None, sleep_fn: Callable = time.sleep) -> Dict[str, Any]:
    """Scheduler heartbeat — the operator that actually drives the store. A deployment runs
    ``omegaclaw-cron daemon``; this loops ``run_due`` every ``interval`` seconds so due jobs fire
    on their own (without this, jobs are only ever created, never run).

    ``delivery_fn``/``alert_fn`` default to the durable file sinks so results/failures are never
    silently dropped; a live deployment injects channel-backed hooks (and a real agent ``runner``)
    here — that wiring is the intended extension seam. ``iterations`` bounds the loop (``None`` =
    until interrupted); ``sleep_fn`` is injectable so tests drive it without real waiting. One
    tick that raises never kills the heartbeat — it is caught and alerted."""
    delivery_fn = delivery_fn or _default_delivery
    alert_fn = alert_fn or _default_alert
    ticks = fired_total = 0
    try:
        while iterations is None or ticks < iterations:
            try:
                r = run_due(runner=runner, delivery_fn=delivery_fn, alert_fn=alert_fn)
                fired_total += r.get("count", 0)
            except Exception as e:  # noqa: BLE001 - a bad tick must not stop the heartbeat
                _alert(alert_fn, {"id": "<daemon>"}, "run_due crashed: {}".format(e))
            ticks += 1
            if iterations is not None and ticks >= iterations:
                break
            sleep_fn(interval)
    except KeyboardInterrupt:  # pragma: no cover - graceful Ctrl-C on the CLI daemon
        pass
    return {"ok": True, "ticks": ticks, "fired_total": fired_total}


def _alert(alert_fn, job, message):
    fn = alert_fn or _default_alert
    try:
        fn(job, message)
    except Exception:  # noqa: BLE001
        pass


def run_now(job_id: str, runner: Optional[Callable] = None, **kw) -> Dict[str, Any]:
    """Force-run a single job immediately (CLI ``cron run``), regardless of its schedule.

    A one-off manual run: it executes ONLY this job (never other due jobs) and does NOT mutate
    durable pause/resume (``enabled``) or ``next_run`` — running a paused job leaves it paused."""
    delivery_fn = kw.pop("delivery_fn", None)
    alert_fn = kw.pop("alert_fn", None)
    conn = kw.pop("conn", None) or connect()
    try:
        job = get_job(job_id, conn=conn)
        if not job:
            return {"ok": False, "error": "no such job: {}".format(job_id)}
        entry = _execute_one(job, time.time(), runner or _default_runner, conn,
                             delivery_fn=delivery_fn, alert_fn=alert_fn, advance=False)
        return {"ok": entry["status"] != "error", "fired": entry}
    finally:
        conn.close()


# --------------------------------------------------------------------------- webhooks

def webhook_subscribe(sub_id: str, secret: str, job_template: Dict[str, Any],
                      conn: Optional[sqlite3.Connection] = None) -> Dict[str, Any]:
    if not is_safe_skill_name(sub_id):
        return {"ok": False, "error": "unsafe subscription id"}
    own = conn is None
    conn = conn or connect()
    try:
        conn.execute("INSERT OR REPLACE INTO webhooks(id, secret, job_template, created) VALUES (?,?,?,?)",
                     (sub_id, secret or "", json.dumps(job_template or {}), time.time()))
        conn.commit()
        return {"ok": True, "id": sub_id}
    finally:
        if own:
            conn.close()


def webhook_list(conn=None):
    own = conn is None
    conn = conn or connect()
    try:
        return [{"id": r["id"], "created": r["created"], "has_secret": bool(r["secret"])}
                for r in conn.execute("SELECT * FROM webhooks ORDER BY created").fetchall()]
    finally:
        if own:
            conn.close()


def webhook_remove(sub_id, conn=None):
    own = conn is None
    conn = conn or connect()
    try:
        cur = conn.execute("DELETE FROM webhooks WHERE id=?", (sub_id,))
        conn.commit()
        return {"ok": cur.rowcount > 0, "id": sub_id}
    finally:
        if own:
            conn.close()


def _sign(secret: str, payload: bytes) -> str:
    return hmac.new(secret.encode("utf-8"), payload, hashlib.sha256).hexdigest()


def webhook_event(sub_id: str, payload, signature: Optional[str] = None,
                  runner: Optional[Callable] = None, conn: Optional[sqlite3.Connection] = None) -> Dict[str, Any]:
    """Validate an incoming event and, if valid, run a one-shot job from the subscription
    template carrying the event metadata. A bad/missing signature (when a secret is configured)
    is REJECTED without running anything."""
    own = conn is None
    conn = conn or connect()
    try:
        row = conn.execute("SELECT * FROM webhooks WHERE id=?", (sub_id,)).fetchone()
        if not row:
            return {"ok": False, "error": "no such subscription: {}".format(sub_id)}
        raw = payload if isinstance(payload, (bytes, bytearray)) else json.dumps(payload, sort_keys=True).encode("utf-8")
        if row["secret"]:
            if not signature or not hmac.compare_digest(_sign(row["secret"], raw), signature):
                return {"ok": False, "error": "invalid signature", "rejected": True}
        template = json.loads(row["job_template"] or "{}")
        try:
            event = payload if isinstance(payload, dict) else json.loads(raw.decode("utf-8"))
        except (ValueError, UnicodeDecodeError):
            event = {"raw": True}

        def _webhook_runner(job, ctx):
            # the validated, parsed event is injected into ctx by _execute_one(extra_ctx=...)
            if runner is not None:
                return runner(job, ctx)
            keys = ",".join(sorted(event.keys())) if isinstance(event, dict) else "?"
            return "webhook {} event handled (keys={})".format(sub_id, keys)
        # Collision-resistant transient id (random suffix), and — critically — only remove the
        # job if WE created it, so a webhook can never delete a pre-existing durable job whose id
        # happens to collide (the old predictable modulo id + unconditional remove could).
        import uuid
        jid = "wh-{}-{}".format(sub_id, uuid.uuid4().hex[:16])
        created = create_job(jid, "once", str(time.time()), prompt=template.get("prompt", ""),
                             skills=template.get("skills"), on_empty=template.get("on_empty", "silent"),
                             meta={"webhook": sub_id,
                                   "event_keys": sorted(event.keys()) if isinstance(event, dict) else []},
                             now=0, conn=conn)
        if not created.get("ok"):
            return {"ok": False, "error": "could not create transient webhook job: {}".format(
                created.get("error")), "sub_id": sub_id, "event_valid": True}
        try:
            job = get_job(jid, conn=conn)
            # run ONLY this transient job, passing the validated event into the runner ctx
            entry = _execute_one(job, time.time(), _webhook_runner, conn, advance=False,
                                 extra_ctx={"event": event})
        finally:
            remove(jid, conn=conn)   # transient — safe: this id is unique and we created it
        return {"ok": bool(entry) and entry["status"] != "error", "sub_id": sub_id,
                "fired": entry, "event_valid": True}
    finally:
        if own:
            conn.close()


# --------------------------------------------------------------------------- selftest

def _selftest() -> None:
    dbp = os.path.join(tempfile.mkdtemp(prefix="scheduler_selftest_"), "jobs.db")
    os.environ["OMEGACLAW_JOBS_DB"] = dbp
    os.environ["OMEGACLAW_SESSION_DB"] = os.path.join(os.path.dirname(dbp), "s.db")
    reset(dbp)

    t0 = 1_000_000.0
    ran = []

    def runner(job, ctx):
        ran.append(job["id"])
        if job.get("meta") and "boom" in (job.get("prompt") or ""):
            raise RuntimeError("kaboom")
        return "output for " + job["id"]

    # once + interval + cron creation
    assert create_job("once1", "once", str(t0 + 10), prompt="hi", now=t0)["ok"]
    assert create_job("iv1", "interval", "60", prompt="tick", now=t0)["ok"]
    assert create_job("cr1", "cron", "*/5 * * * *", prompt="cronjob", now=t0)["ok"]
    # unsafe id + too-fast interval refused
    assert create_job("../x", "once", str(t0))["ok"] is False
    assert create_job("fast", "interval", "0.1", now=t0)["ok"] is False

    # nothing due before t0+10; once1 due at t0+10
    assert run_due(now=t0 + 5, runner=runner)["count"] == 0
    r = run_due(now=t0 + 11, runner=runner)
    assert "once1" in [f["id"] for f in r["fired"]]
    # once job is now done (next_run None) -> not due again
    assert get_job("once1")["next_run"] is None
    assert "once1" not in [f["id"] for f in run_due(now=t0 + 100, runner=runner)["fired"]]

    # interval reschedules
    before = get_job("iv1")["next_run"]
    run_due(now=before + 0.1, runner=runner)
    assert get_job("iv1")["next_run"] > before

    # restart safety: a due job persisted; a fresh connection still sees + fires it once
    reset(dbp)
    create_job("survive", "once", str(t0), prompt="x", now=t0)
    # simulate restart: new process reads same DB (overdue) -> fires exactly once, not lost/dup
    f1 = run_due(now=t0 + 1000, runner=runner)
    f2 = run_due(now=t0 + 2000, runner=runner)
    assert [f["id"] for f in f1["fired"]] == ["survive"] and f2["count"] == 0

    # failure -> alert
    alerts = []
    create_job("boomjob", "once", str(t0), prompt="boom", now=t0, meta={"x": 1})
    rb = run_due(now=t0 + 1, runner=runner, alert_fn=lambda job, msg: alerts.append((job["id"], msg)))
    assert rb["fired"][0]["status"] == "error" and alerts and alerts[0][0] == "boomjob"

    # on_empty: silent stays quiet, alert alerts
    create_job("emptysilent", "once", str(t0), now=t0, on_empty="silent")
    create_job("emptyalert", "once", str(t0), now=t0, on_empty="alert")
    a2 = []
    run_due(now=t0 + 1, runner=lambda j, c: "", alert_fn=lambda j, m: a2.append(j["id"]))
    assert "emptyalert" in a2 and "emptysilent" not in a2

    # recursion guard: a runner can't create jobs
    create_job("recur", "once", str(t0), now=t0)
    def _recur_runner(job, ctx):
        return "nested={}".format(create_job("child", "once", str(t0), now=t0)["ok"])
    rr = run_due(now=t0 + 1, runner=_recur_runner)
    assert "nested=False" in get_job("recur")["last_output"]

    # webhook: valid signature runs, invalid rejected
    secret = "shh-secret"
    webhook_subscribe("gh", secret, {"prompt": "handle push"})
    import json as _json
    payload = {"event": "push", "repo": "x"}
    raw = _json.dumps(payload, sort_keys=True).encode("utf-8")
    good = _sign(secret, raw)
    assert webhook_event("gh", payload, good, runner=lambda j, c: "handled")["ok"]
    assert webhook_event("gh", payload, "deadbeef").get("rejected") is True
    assert webhook_event("gh", payload, None).get("rejected") is True

    del os.environ["OMEGACLAW_JOBS_DB"], os.environ["OMEGACLAW_SESSION_DB"]
    print("scheduler self-tests passed")


if __name__ == "__main__":
    _selftest()
