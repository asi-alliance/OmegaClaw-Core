; Feature B2: deontic policy guardrail verdict logic.
!(import! &self (library OmegaClaw-Core src/policy_guard))

; the policy forbids `delete` and obliges `reply` while unconfirmed
!(test (forbidden-action? delete (dl-path examples/deontic/policy.metta)) True)
!(test (obligatory-action? reply (dl-path examples/deontic/policy.metta)) True)
; an action the policy says nothing about is permitted
!(test (forbidden-action? send (dl-path examples/deontic/policy.metta)) False)
!(test (action-verdict delete (dl-path examples/deontic/policy.metta)) forbidden)
!(test (action-verdict send  (dl-path examples/deontic/policy.metta)) permitted)

; a skill s-expr maps to its head action
!(test (skill->action (shell "rm -rf /")) shell)

; the guardrail is OFF by default (no change to loop behavior unless opted in)
!(test (deonticGuardEnabled) False)

!(println! test-policy-guard-done)
