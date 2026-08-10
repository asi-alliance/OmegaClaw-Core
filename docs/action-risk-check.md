# Action Risk Gate

## Purpose

`action-risk-check` deterministically evaluates the risk of an intended
OmegaClaw action. It uses local rules only: no LLM, network request, command
execution, or filesystem access occurs during classification. Results include
a decision, risk level, and stable reason code, and never echo the supplied
target.

## Skill signature

```metta
(action-risk-check "skill-name" "target-or-argument")
```

The result follows the existing Python bridge convention and is returned as a
plain string:

```text
decision=allow, risk=low, reason=read-only
```

## Examples

```metta
(action-risk-check "websearch" "public Hyperon documentation")
; decision=allow, risk=low, reason=read-only

(action-risk-check "write-file" "notes.txt")
; decision=review, risk=medium, reason=state-changing

(action-risk-check "read-file" "/project/.env")
; decision=review, risk=high, reason=sensitive-target

(action-risk-check "shell" "rm -rf /var/lib/app")
; decision=block, risk=critical, reason=destructive-action
```

Classification precedence is fixed: destructive, sensitive, state-changing,
read-only, then unknown. Unknown skills default to `review`/`medium`.

## Advisory limitation

This first version is advisory. It evaluates an action only when
`action-risk-check` is explicitly called. It does not intercept every skill or
prevent another skill from executing.

## Possible Phase 2 enforcement

A later pre-dispatch gate could classify each parsed skill expression in
`src/loop.metta` before `eval`. It could permit `allow`, require explicit user
confirmation for `review`, and refuse `block`, while keeping the classifier
side-effect-free. Such enforcement should include a trusted confirmation
state, protection against recursive gating, structured audit logging that
redacts arguments, and regression tests for multi-command dispatch.
