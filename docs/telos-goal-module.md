# Telos goal module (`lib_telos_goals.metta`) — optional

OmegaClaw is goal-autonomous but the public core ships no dedicated, inspectable model of
*what the goals are* (no `goal` token in `run.metta` / `lib_omegaclaw.metta`). This optional
module adds one in OmegaClaw's own idiom: AtomSpace atoms + parameterized derivation rules.

It is **opt-in** and **side-effect-free on load** (nothing runs at import).

## Schema

```
(goal <id> <scope> <owner> <status>)   ; scope: individual | collective
                                       ; status: active | proposed | achieved | abandoned
(rel  <type> <src> <dst>)              ; type: supports | conflicts | subsumes | depends-on
```

## Use

Load it, then have the agent assert goal/rel atoms it inferred from what it is reading and
call the rules via the `metta` skill:

```metta
!(import! &self (library OmegaClaw-Core lib_telos_goals))

(goal alice-train      individual alice active)
(goal dao-fair-access  collective dao   active)
(rel  conflicts alice-train dao-fair-access)

!(telos-conflicts)        ; -> (conflict-between alice-train dao-fair-access)
!(telos-collective-goals) ; -> (collective-goal dao-fair-access dao)
!(telos-reading)          ; all lenses at once
```

Rules available: `telos-conflicts`, `telos-collective-goals`, `telos-goals-of`,
`telos-achieved`, `telos-blocked`, `telos-aligned`, `telos-reading`.

## Verified

Loads on the standalone Hyperon interpreter and in a **live OmegaClaw (PeTTa) runtime** — the
conflict rule derives `(conflict-between alice-train dao-fair-access)` inside the running
agent's AtomSpace.

## Why / measuring it

Goal *misunderstanding* (pursuing the literal request and missing the real goal, serving one
person while externalising cost onto the group, chasing an abandoned goal) is where an
autonomous agent is most dangerous and is rarely measured. This module is paired with a
14-scenario / 7-category goal-understanding **benchmark** that can score OmegaClaw or any
agent: https://github.com/arielagor/telos (MIT, same licence as OmegaClaw). Contributed from
the BGI Sprint I project "Telos".
