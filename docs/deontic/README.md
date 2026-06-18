# OmegaClaw Deontic Engine

A **defeasible deontic logic reasoner** with a **task-orchestration layer** on top,
implemented natively in MeTTa on the PeTTa interpreter. It answers two questions
that graded-belief engines (NAL/PLN) do not:

- **What defeasibly holds** when rules conflict — conclusions that a later fact can
  *retract* (non-monotonic), resolved by rule specificity / priority.
- **What is obligated, permitted, or forbidden** — and whether an action complies,
  violates, or sits in an unresolved dilemma, including over time.

If you need *retractable* conclusions, *rule priority*, *norms* (O/P/F, compliance,
deadlines), or *temporal* reasoning (Event Calculus, Allen intervals), this is the
engine. The **directive** layer then uses it to coordinate tasks: a plan of work
plus dependency rules, from which the engine derives what is actionable and a
claim/complete lifecycle is enforced.

---

## What's in the box

| Piece | File | What it does |
|---|---|---|
| **Core reasoner** | `lib_deontic.metta` | Defeasible Logic DL(d) + Standard Deontic Logic + Event Calculus + trust |
| **Directive layer** | `lib_directive.metta` | Task orchestration on top of the reasoner (dependency-ordered work) |
| Reference | [`reference-lib-deontic.md`](../reference-lib-deontic.md) | Full reasoner API |
| Reference | [`reference-lib-directive.md`](../reference-lib-directive.md) | Full directive API |

Optional feature layers live on their own branches (see *Layered architecture*).

---

## The theory it implements

- **Defeasible Logic** (Nute; Antoniou et al.) — strict (`->`), defeasible (`=>`),
  and defeater (`~>`) rules, a **superiority** relation, ambiguity blocking, and the
  four DL(d) provability tags **±Δ** (definite) / **±∂** (defeasible).
- **Standard Deontic Logic** (Governatori) — obligation/permission/prohibition with
  `F p ≡ O ¬p`, **contrary-to-duty** ⊗-reparation chains, and **deontic dilemmas**.
- **Event Calculus** + the 13 **Allen** interval relations + temporal-deontic
  **deadlines** (achievement / maintenance).
- **Weakest-link trust** over multi-source claims, with per-source weights and gates.

Conclusions are a set of `(tag literal)` pairs; tags are `pD`/`nD` (±Δ) and `pd`/`nd`
(±∂). A literal is `(lit <sign> <mode> <temporal> <functor> <args>)`. See the
[reasoner reference](../reference-lib-deontic.md) for the full tag/literal model.

---

## Theories and plans are ordinary `.metta` files

There is **no bespoke parser**: a theory/plan is read by PeTTa's own loader, so it is
just MeTTa atoms. The surface forms:

| form | meaning |
|---|---|
| `(given p)` | a fact |
| `(always L a b)` / `(normally L a b)` / `(except L a b)` | strict / defeasible / defeater rule |
| `(prefer L1 L2)` | superiority: rule `L1` out-ranks `L2` |
| `(not p)` · `(must p)` · `(forbidden p)` · `(permitted p)` | negation · deontic O/F/P |
| `(deadline …)` | temporal-deontic deadline obligation |
| `(happens e t)` · `(initiates e f t)` · `(terminates e f t)` · `(during LIT ?T)` | Event Calculus / Allen |
| `(claims src … )` · `(trusts src v)` · `(threshold n v)` | sourced facts / trust weights / gates |

The arrow-syntax `.dfl` format is also accepted (same theory, textbook notation).

---

## Quickstart

`examples/deontic/penguin.metta` — the specific rule defeats the general one:

```metta
(given bird) (given penguin)
(normally r1 bird flies)
(normally r2 penguin (not flies))
(prefer r2 r1)                 ; penguins are more specific
```

```metta
!(import! &self (library OmegaClaw-Core lib_deontic))
!(dl-run (dl-path examples/deontic/penguin.metta))
; => includes (pd (lit neg none none flies ()))  — defeasibly NOT flies
;            and (nd (lit pos none none flies ())) — r2 defeats r1
```

Key entry points: `(dl-run <path>)` for the conclusion set, `(dl-run-deontic <path>)`
for the SDL closure, `(dl-run-at <path> <time>)` for as-of reasoning,
`(deontic-compliance <path>)` / `(deontic-dilemmas <path>)` for norm analysis, and the
non-monotonic queries `(dl-what-if …)` / `(dl-why-not …)` / `(dl-abduce …)` /
`(dl-requires …)`. Full tables in the [reference](../reference-lib-deontic.md).

---

## Two reasoning backends — the engine toggle

The same theory runs through either of two interchangeable backends, with
**identical conclusions**:

| backend | what it is | when |
|---|---|---|
| `prolog` *(default)* | the fast indexed Prolog kernel (`grounding.pl` / `reason.pl`) | grounding-heavy theories (variable rules over lots of data) |
| `native` | the atomspace-native MeTTa engine (`ground.metta` / `reason.metta`) | propositional / coordination plans, and inspection / debugging |

Switch per run with `(dl-engine! native)` or `$OMEGACLAW_DL_ENGINE=native`.

**Why two?** Native reasoning is at parity, but native *grounding* (instantiating
variable rules) runs ~4–5× slower than the Prolog kernel on grounding-heavy theories
— the cost is per-operation MeTTa-eval overhead, not the algorithm (semi-naive and
functor-indexed variants were measured; neither closes it). So `prolog` is the
default for variable-rule-heavy work, while `native` is free where it matters
(propositional plans, where grounding is trivial) and keeps every rule/atom
inspectable in the atomspace. See the perf note in `src/deontic/ground.metta`.

---

## The directive layer — dependency-ordered task coordination

`lib_directive.metta` turns the reasoner into a **task orchestrator**. A plan lists
tasks and **readiness rules** (a task becomes ready once its dependencies complete);
the defeasible engine derives what is actionable, and a claim/complete lifecycle is
enforced so nothing happens out of order.

```metta
!(import! &self (library OmegaClaw-Core lib_directive))
!(directive-next   <plan>)     ; the assignments whose dependencies are satisfied
!(directive-status <plan>)     ; tasks / ready / claimed / blocked / completed
!(directive-claim    <plan> <task> <agent> False)
!(directive-complete <plan> <task> <agent>)   ; completing deps unlocks dependents
```

Claims/completions are **appended** to the plan `.metta` file with version-superiority
blocks, so the plan is its own durable, auditable state. Blocking propagates through
the dependency DAG (`directive-block` → downstream `upstream-blocked`). Full API in the
[directive reference](../reference-lib-directive.md).

---

## Layered architecture

The engine is the base; each capability is an **independently selectable layer**
(each on its own branch, all building on the core):

| layer | branch | adds |
|---|---|---|
| **core reasoner** | `deontic-core` | the DL(d) / SDL / EC / trust engine |
| **directive** | `deontic-directive` | task orchestration (this branch) |
| NAL/PLN bridge | `deontic-nal-bridge` | feed graded-belief conclusions into deontic rules |
| agent skill | `deontic-skill` | expose the reasoner as an agent skill |
| policy guardrail | `deontic-policy-guardrail` | gate agent actions against a deontic policy |
| semantic | `deontic-semantic` | semantic retrieval into the reasoning loop |

The reasoner itself is a thin MeTTa facade (`src/deontic/*.metta` — `engine`, `query`,
`deontic`, `eventcalc`, `trust`, `ground`, `reason`) over a deterministic kernel
(`src/deontic/platform/*.pl`). `platform.metta` is the only module that knows the
engine runs on PeTTa.

---

## Running the tests

```sh
SWIPL=…/swipl    # the PeTTa build
$SWIPL --stack_limit=8g -q -s PeTTa/src/main.pl -- tests/deontic/test_core.metta --silent
```

The suite is **139 tests** across `tests/deontic/` (core, CTD, deadline, deontic, dfl,
eventcalc, incremental, query, temporal, trust) and `tests/integration/` (directive,
analyze, inspect, mining). It passes identically under **both** engine backends
(`OMEGACLAW_DL_ENGINE=prolog` and `=native`).

---

## When to use this vs NAL / PLN

| You need… | Use |
|---|---|
| Retractable (non-monotonic) conclusions, rule priority | this engine |
| Norms: O/P/F, compliance, dilemmas, deadlines | this engine |
| Temporal reasoning (Event Calculus, Allen intervals) | this engine |
| Dependency-ordered task coordination | the directive layer |
| Graded belief from noisy multi-source evidence | NAL / PLN |

NAL/PLN decide *how much you believe* a fact; this engine decides *what defeasibly
holds and what you ought to do* given those facts.
