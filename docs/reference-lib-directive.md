# Reference — `lib_directive.metta`

**Dependency-ordered task orchestration**, built on the defeasible deontic engine
([`lib_deontic`](./reference-lib-deontic.md)). A *plan* lists tasks and the rules by
which a task becomes ready; the engine derives what is actionable right now, and a
claim/complete lifecycle is enforced so work happens in dependency order. Because the
rules are *defeasible*, the plan can express priorities, blocking, and reversible
claims — and recover when a task fails.

The orchestration is just deontic reasoning: **readiness and assignment are defeasible
rules**, so `directive-next` is `dl-run` over the plan, filtered to the assignments
whose dependencies hold. Lifecycle actions (claim, complete, …) are **appended to the
plan `.metta` file** as superiority-ranked blocks, so the file *is* the durable,
auditable state — no external store.

---

## Plan format

A plan is a `.metta` theory ([loaded natively](./reference-lib-deontic.md), no parser)
using the deontic forms plus a literal-naming convention:

```metta
(meta plan (id "PROJ-1") (title "Ship v1") (status "active") (author "agent:me"))

(given agent-coder-available)              ; available agents
(given task-design) (given task-backend)   ; the tasks
(given no-deps-design)                     ; roots (no dependencies)

; readiness: a task is ready once its dependencies are completed
(normally r-design  (and task-design no-deps-design)  ready-design)
(normally r-backend completed-design                  ready-backend)

; assignment: a ready task + an available agent is an actionable assignment
(normally assign-design (and ready-design agent-coder-available) assign-to-design-coder)
(prefer assign-design-reviewer assign-design)   ; optional priority between assignments

; blocking defeater (optional)
(except block-deploy tests-failing (not ready-deploy))
```

Conventions the layer reads: `task-X`, `ready-X`, `completed-X`, `claimed-X`,
`blocked-X`, `upstream-blocked-X`, and `assign-to-X-AGENT`. A task `X` is *ready* when
`ready-X` is concluded and `completed-X` is not.

---

## Lifecycle

Lifecycle calls append a **`(claims supervisor:AGENT …)`** block to the plan file. Each
block carries a version and a `(prefer …)` that out-ranks the previous block, so the
newest action wins by superiority (defeasible, hence reversible):

```
claim   v1   →  claimed-X
unclaim v2   →  (not claimed-X)     prefer v2 > v1
reclaim v3   →  claimed-X           prefer v3 > v2
```

`completed-X` is a fact; completing a task's dependencies makes dependents *ready* on
the next read. `directive-block` propagates through the dependency DAG — a blocked task
marks downstream tasks `upstream-blocked-…`, so a failure visibly cascades and the team
can be rerouted. Completing the final task reports `plan-complete`.

---

## API

A plan is a path (use `(dl-path <repo-relative-file>)` for bundled fixtures, or an
absolute path for runtime plans).

### Read the actionable state
| call | returns |
|---|---|
| `(directive-next <plan>)` | `(next-actions ((assign <task> <agent> <label>) …))` — assignments whose deps hold |
| `(directive-status <plan>)` | `(status (tasks …) (ready …) (claimed …) (blocked …) (upstream-blocked …) (completed …))` |
| `(directive-board <plan>)` | tasks grouped: `(board (backlog …) (ready …) (in-progress …) (blocked …) (done …))` |
| `(directive-summary <plan>)` | counts: `(summary (total N) (backlog N) (ready N) (in-progress N) (blocked N) (done N) (progress-pct N))` |
| `(directive-info <plan>)` | the `(meta plan …)` key/values |
| `(directive-assignments <plan>)` | the current assignment suggestions |

### Mutate (append a lifecycle block)
| call | returns |
|---|---|
| `(directive-claim <plan> <task> <agent> <force>)` | `(claimed <task> <ver>)` · `(already-claimed …)` · `(err not-ready <task>)` |
| `(directive-complete <plan> <task> <agent>)` | `(completed <task>)` · `(completed <task> plan-complete)` |
| `(directive-unclaim <plan> <task> <agent>)` | `(unclaimed <task> <ver>)` |
| `(directive-block <plan> <task> <agent>)` | `(blocked <task> <ver>)` (+ downstream `upstream-blocked`) |
| `(directive-unblock <plan> <task> <agent>)` | `(unblocked <task> <ver>)` |

`<force> = True` bypasses the readiness check when claiming.

### Inspect / validate
| call | returns |
|---|---|
| `(directive-validate <plan>)` | structural problems (cycles, dangling deps, missing metadata) |
| `(directive-analyze <plan>)` | a combined structure + readiness report |
| `(directive-trace <plan> <task>)` | why a task is / isn't actionable (the deriving + defeating rules) |
| `(directive-upstream <plan> <task>)` | the tasks `<task>` depends on |
| `(directive-task-state <plan> <task>)` | one of `backlog` / `ready` / `in-progress` / `blocked` / `done` |

---

## Worked example

`tests/deontic/fixtures/basic-tasks.metta` defines tasks `auth`, `models`, `crud`,
`tests` with `crud ⇐ models` and `tests ⇐ crud ∧ auth`.

```metta
!(import! &self (library OmegaClaw-Core lib_directive))

!(directive-next "/tmp/plan.metta")                 ; offers auth, models — NOT crud
!(directive-complete "/tmp/plan.metta" models me)   ; (completed models)
!(directive-next "/tmp/plan.metta")                 ; NOW offers crud (its dep is done)
!(directive-claim "/tmp/plan.metta" crud me False)  ; (claimed crud 1)
```

`crud` is gated until `models` completes — the dependency DAG is enforced by the
defeasible engine, not by the caller.

---

## See also
- [reference-lib-deontic.md](./reference-lib-deontic.md) — the reasoner underneath.
- [deontic/README.md](./deontic/README.md) — the overall engine + layer overview.
