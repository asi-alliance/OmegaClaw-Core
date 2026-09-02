# Reference — `lib_telos_goals.metta`

An optional goal-graph module. Omega is goal-autonomous (it creates goals, pursues them, tracks progress) but the core ships no inspectable model of *what the goals are*. This module adds one in Omega's own idiom: AtomSpace atoms plus derivation rules, so an agent can represent individual and collective goals, surface conflicts and blockers, and reason about alignment symbolically instead of guessing.

It is **opt-in** and **side-effect-free on load**. `lib_omega.metta` does not import it, and nothing in the file runs at import time: it only defines the schema contract, the query rules, and two functions that install or remove a prompt extension when you call them.

---

## Loading

```metta
!(import! &self (library Omega lib_telos_goals))
```

---

## Schema

Two atom shapes. Every relation reads **source → destination**, and the direction matters for the rules below.

| Atom | Meaning |
|---|---|
| `(goal <id> <scope> <owner> <status>)` | A goal. `scope` is `individual` or `collective`. `status` is `active`, `proposed`, `achieved`, or `abandoned`. |
| `(rel supports <src> <dst>)` | Achieving `src` advances `dst`. |
| `(rel conflicts <src> <dst>)` | `src` and `dst` cannot both be achieved. Assert once per pair; the conflict lens does not symmetrise. |
| `(rel subsumes <parent> <child>)` | `parent` is the broader goal and `child` is a sub-goal of it. |
| `(rel depends-on <src> <dst>)` | `src` cannot progress until `dst` is achieved. |

---

## Who asserts the atoms

**Omega does not infer or assert `goal` / `rel` atoms on its own.** The module is a representation and a set of queries. The LLM layer populates it through the existing `metta` skill while it reads a conversation, and reads it back the same way:

```
metta (add-atom &self (goal alice-train individual alice active))
metta (add-atom &self (rel conflicts alice-train dao-fair-access))
metta (telos-reading)
```

`(telos-enable)` teaches the LLM to do exactly that. It calls the core `add-prompt-extension` hook from `src/skills.metta` to insert a `GOAL GRAPH` section into the prompt, after the SKILL section and before OUTPUT_FORMAT, describing the schema, the `add-atom` calls, the read lenses, and the rule that every `conflict-between` and `blocked` result is reported to the user before the agent acts on a goal. `(telos-disable)` removes the section again. Neither runs until called.

---

## Lenses

### Zero-arity lenses

Each of these queries the whole graph and is folded into `(telos-reading)`.

| Rule | Yields | Meaning |
|---|---|---|
| `(telos-conflicts)` | `(conflict-between $a $b)` | Every asserted conflict pair. |
| `(telos-collective-goals)` | `(collective-goal $g $owner)` | Every collective goal, any status. |
| `(telos-achieved-goals)` | `(achieved-goal $g $owner)` | Every achieved goal, any scope. |
| `(telos-abandoned-goals)` | `(abandoned-goal $g $owner)` | Every abandoned goal. Surfacing these stops the agent chasing a goal its owner dropped. |
| `(telos-subgoals)` | `(subgoal $child of $parent)` | The sub-goal structure declared by `subsumes`. |
| `(telos-blocked)` | `(blocked $g on $dep)` | A goal whose `depends-on` target is not yet achieved. An abandoned dependency still blocks. |
| `(telos-aligned)` | `(aligns $i with $c)` | An individual goal that `supports` a collective goal of some owner. |

### The full reading

```metta
!(telos-reading)
```

The superposition of every zero-arity lens above. Call it after the goal and relation atoms are in place.

### Parameterised probes

These take an owner or a goal id, so they are queried on their own and are **not** part of `(telos-reading)`.

| Rule | Yields | Meaning |
|---|---|---|
| `(telos-goals-of $owner)` | `(goal-of $owner $g)` | The individual goals of one stakeholder. |
| `(telos-achieved $g)` | `True` or empty | Whether one goal's status atom says `achieved`. |

---

## Worked example

```metta
!(import! &self (library Omega lib_telos_goals))

(goal alice-train      individual alice active)
(goal bob-share        individual bob   active)
(goal grant            individual alice achieved)
(goal dao-fair-access  collective dao   active)
(goal gpu-quota        collective dao   proposed)
(rel  conflicts  alice-train bob-share)
(rel  supports   bob-share   dao-fair-access)
(rel  depends-on dao-fair-access gpu-quota)
(rel  subsumes   dao-fair-access gpu-quota)

!(telos-conflicts)        ; (conflict-between alice-train bob-share)
!(telos-achieved-goals)   ; (achieved-goal grant alice)
!(telos-subgoals)         ; (subgoal gpu-quota of dao-fair-access)
!(telos-blocked)          ; (blocked dao-fair-access on gpu-quota)
!(telos-aligned)          ; (aligns bob-share with dao-fair-access)
!(telos-goals-of alice)   ; (goal-of alice alice-train) (goal-of alice grant)
!(telos-reading)          ; all of the zero-arity results at once
```

---

## Tests

`tests/tests_lib_telos_goals.metta` covers every lens, both probes, the direction of `subsumes`, the membership of each lens in `(telos-reading)`, and the `telos-enable` / `telos-disable` round trip through `getPromptExtensions`. It runs with the rest of the MeTTa unit tests:

```sh
PETTA_PATH=/PeTTa sh tests/mettatest.sh
```

---

## Origin

Contributed from the BGI Sprint I project Telos (https://github.com/arielagor/telos, MIT), which also ships a 14-scenario goal-understanding benchmark that can score Omega or any other agent on goal *misunderstanding*: pursuing the literal request and missing the real goal, serving one person while externalising cost onto the group, or chasing an abandoned goal.
