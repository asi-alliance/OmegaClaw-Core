# Reference — `lib_deontic.metta`

Defeasible, deontic, and temporal reasoning. Where `lib_nal`/`lib_pln` grade **how much** a fact is believed, `lib_deontic` answers what **defeasibly holds** under conflicting rules and what is **obligated, permitted, or forbidden** — non-monotonic and normative reasoning. It is the engine to reach for when conclusions must be *retractable* (a later fact can overturn an earlier one) or when an action must be checked against norms.

Theory: Nute/Antoniou **Defeasible Logic**, Governatori **defeasible deontic logic**, the **Event Calculus** + the 13 **Allen** interval relations for time. It also fills the gap [reference-lib-nal.md](./reference-lib-nal.md) notes — "real-time / temporal reasoning is not served by a stock engine."

---

## Conclusion tags

Reasoning over a theory yields a set of `(tag literal)` conclusions. Tags are the four standard Defeasible-Logic provability degrees:

| tag | DL notation | meaning |
|---|---|---|
| `pD` | +Δ | **definitely** provable (facts + strict rules alone) |
| `nD` | −Δ | definitely refuted |
| `pd` | +∂ | **defeasibly** provable (a rule fires and every attacker is defeated or out-ranked) |
| `nd` | −∂ | defeasibly refuted |

A literal is `(lit <sign> <mode> <temporal> <functor> <args>)`: `sign` ∈ `pos|neg`, `mode` ∈ `none|O|P|F` (obligation / permission / prohibition), `temporal` ∈ `none|(iv <start> <end>)`.

---

## Theory surface syntax (MeTTa / DFL)

A theory is a `.metta` (or arrow-format `.dfl`) file:

| form | meaning |
|---|---|
| `(given p)` | a **fact** |
| `(claims src p)` | a fact asserted **by a source** (carries provenance for trust) |
| `(always L a b)` | **strict** rule `a -> b` (classical: if `a` then `b`) |
| `(normally L a b)` | **defeasible** rule `a => b` (`b` unless defeated) |
| `(except L a b)` | **defeater** `a ~> b` (blocks the opposite of `b` without proving `b`) |
| `(prefer L1 L2)` | **superiority**: rule `L1` out-ranks `L2` |
| `(not p)` | classical negation |
| `(must p)` / `(forbidden p)` / `(permitted p)` | deontic mode O / F / P on `p` (`F p ≡ O ¬p`) |
| `(deadline …)` | a temporal-deontic deadline obligation (achievement / maintenance) |
| `(happens e t)` / `(initiates e f t)` / `(terminates e f t)` | Event-Calculus events/effects |
| `(during LIT ?T)` | bind an interval handle for Allen-relation constraints |
| `(trusts src v)` / `(threshold name v)` | per-source trust weight / a trust gate |

---

## API

Reach the engine through the `(metta …)` skill. A theory is loaded from a path via `(dl-path <repo-relative-file>)`.

### Defeasible reasoning
| call | returns |
|---|---|
| `(dl-run <path>)` | the full sorted `(tag lit)` conclusion set |
| `(dl-run-at <path> <ref>)` | conclusions **as of** a reference time (drops temporally-inactive atoms) |
| `(dl-run-deontic <path>)` | conclusions under the Standard Deontic Logic closure (`F p ≡ O ¬p`, `O p → P p`) |
| `(dl-print <path>)` | pretty-prints each conclusion (`  +D penguin`) |

### Deontic analysis
| call | returns |
|---|---|
| `(deontic-compliance <path>)` | per-obligation verdict report: fulfilled / violated / pending |
| `(deontic-dilemmas <path>)` | obligations in conflict (`O p` and `O ¬p` both applicable, neither resolved) |
| `(deadline-status <path> <now> <functor>)` | deadline verdict (achievement vs maintenance) at time `now` |

### Non-monotonic queries
| call | returns |
|---|---|
| `(dl-what-if <path> <hyps> <goal>)` | the goal's status and newly-provable literals after assuming `<hyps>` |
| `(dl-why-not <goal>)` | the rules/defeats that block a goal |
| `(dl-abduce <goal>)` | minimal fact-sets that would make the goal provable |
| `(dl-requires <path> <goal>)` | support the goal cannot do without |

### Trust & explanation
| call | returns |
|---|---|
| `(trust-of <lit>)` | weakest-link trust over the proof tree, `[0,1]` |
| `(justify <lit>)` | bundled DL status + proof tree + trust + sources + confidence |
| `(dl-trust-run <path>)` | conclusions annotated with trust + sources |

### Temporal (Event Calculus)
`(ec-intervals …)`, `(ec-holds-at …)`, `(ec-violated-at …)`, `(ec-timeline …)`.

### Engine backends
The reasoner ships two interchangeable backends with **identical conclusions**:
`prolog` (default — the fast indexed kernel) and `native` (the atomspace-native MeTTa
engine). Switch with `(dl-engine! native)` or `$OMEGACLAW_DL_ENGINE=native`. Use
`prolog` for grounding-heavy theories and `native` for propositional plans /
inspection — see [deontic/README.md](./deontic/README.md#two-reasoning-backends--the-engine-toggle).

---

## Worked examples

### Defeasible: the penguin overrides the bird rule
`examples/deontic/penguin.metta`:
```
(given bird) (given penguin)
(normally r1 bird flies)
(normally r2 penguin (not flies))
(prefer r2 r1)            ; penguins are more specific
```
```metta
!(import! &self (library OmegaClaw-Core lib_deontic))
!(dl-run (dl-path examples/deontic/penguin.metta))
```
Conclusion set includes `(pd (lit neg none none flies ()))` (defeasibly **not** flies) and `(nd (lit pos none none flies ()))` — the specific rule `r2` defeats `r1`.

### Deontic: an unresolved dilemma
`examples/deontic/deontic_dilemma.metta`:
```
(given a)
(normally r1 a (must p))
(normally r2 a (forbidden p))
```
```metta
!(deontic-dilemmas (dl-path examples/deontic/deontic_dilemma.metta))
```
Returns one dilemma: `O p` and `O ¬p` are both applicable and neither is ranked above the other, so neither obligation is discharged.

---

## When to use `lib_deontic` vs. NAL / PLN

| Situation | Engine |
|---|---|
| Conclusions that a later fact can **retract** (non-monotonic) | `lib_deontic` |
| Rule **priority** / specificity conflicts (superiority) | `lib_deontic` |
| **Norms**: obligations / permissions / prohibitions, compliance, dilemmas, deadlines | `lib_deontic` |
| **Temporal** reasoning (Event Calculus, Allen intervals) | `lib_deontic` |
| Graded **belief** from noisy multi-source evidence | NAL / PLN |
| Inheritance / implication chains with confidence decay | NAL `\|-` |
| Property-based categorical inference | PLN `\|~` |

The two are complements: NAL/PLN decide *how much you believe* a fact; `lib_deontic` decides *what defeasibly holds and what you ought to do* given those facts.

---

## See also
- [reference-lib-nal.md](./reference-lib-nal.md) — evidential (NARS) reasoning.
- [reference-lib-pln.md](./reference-lib-pln.md) — probabilistic reasoning.
- [reference-orchestration.md](./reference-orchestration.md) — picking an engine.
