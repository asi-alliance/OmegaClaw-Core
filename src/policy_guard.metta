; Deontic policy guardrail (Feature B2, opt-in, default OFF).
;
; A norm-governor for the autonomous agent. The agent's behavioral policy is
; expressed as a defeasible DEONTIC theory — obligations (O), permissions (P) and
; prohibitions (F) over actions, with superiority for rule priority and
; contrary-to-duty for "if you did the forbidden thing, you must now compensate".
; Before the loop executes a chosen skill, the guard can evaluate the action
; against the policy and block forbidden ones. This is normative reasoning, and is
; complementary to the OS-level sandbox in profile/policy (which restricts what
; the process *can* do; this restricts what the agent *ought* to do).
!(import! &self (library OmegaClaw-Core lib_deontic))

; --- verdict for an action under a deontic policy theory --------------------
(= (forbidden-action? $action $policy)
   (is-member (pd (lit pos F none $action ())) (dl-run-deontic $policy)))
(= (obligatory-action? $action $policy)
   (is-member (pd (lit pos O none $action ())) (dl-run-deontic $policy)))
(= (action-verdict $action $policy)
   (if (== (forbidden-action? $action $policy) True) forbidden
       (if (== (obligatory-action? $action $policy) True) obligatory permitted)))

; the action a skill s-expr performs is its head functor: (shell "rm") -> shell
(= (skill->action $s) (car-atom $s))

; --- loop hook: a SAFE, flag-gated wrapper around (eval $s) -----------------
; deonticGuardEnabled defaults to False, so guarded-eval is EXACTLY (eval $s)
; until a deployment opts in (and points policyPath at its norms). With the flag
; off there is no behavioral change to the loop whatsoever.
(= (deonticGuardEnabled) False)
(= (policyPath) "examples/deontic/policy.metta")
(= (guarded-eval $s)
   (if (== (deonticGuardEnabled) True)
       (if (== (action-verdict (skill->action $s) (dl-path (policyPath))) forbidden)
           (BLOCKED_BY_DEONTIC_POLICY $s)
           (eval $s))
       (eval $s)))
