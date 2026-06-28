; ============================================================================
; lib_telos_goals — an optional goal-representation module for OmegaClaw
; ----------------------------------------------------------------------------
; OmegaClaw is goal-autonomous (it creates goals, pursues them, tracks progress),
; but the public core ships no dedicated, inspectable model of *what the goals are*:
; a grep of this repo finds no `goal` token in run.metta / lib_omegaclaw.metta. This
; module adds one, in OmegaClaw's own idiom — AtomSpace atoms + derivation rules — so
; an agent can represent individual vs collective goals, surface conflicts, and reason
; about alignment.
;
; It is OPT-IN and SIDE-EFFECT-FREE on load (no queries run at import): it only defines
; the schema contract + parameterized rules. The agent (its LLM layer) materialises goal
; atoms from what it is reading, then calls these rules via the `metta` skill.
;
; Verified: loads on the standalone Hyperon interpreter AND in a live OmegaClaw runtime
; (PeTTa) — the conflict rule derives (conflict-between alice-train dao-fair-access) in the
; running agent's AtomSpace. Contributed from the BGI Sprint I project "Telos"
; (https://github.com/arielagor/telos), which also ships a 14-scenario goal-understanding
; benchmark you can run against OmegaClaw.
;
; Schema (atoms the agent asserts into &self while reading):
;   (goal <id> <scope> <owner> <status>)   scope: individual | collective
;                                          status: active | proposed | achieved | abandoned
;   (rel  <type> <src> <dst>)              type: supports | conflicts | subsumes | depends-on
;
; Load with:  !(import! &self (library OmegaClaw-Core lib_telos_goals))
; ============================================================================

; All conflict pairs the agent must surface (across ALL goals).
(= (telos-conflicts)
   (match &self (rel conflicts $a $b) (conflict-between $a $b)))

; Every collective goal (what the commons wants).
(= (telos-collective-goals)
   (match &self (goal $g collective $owner $status) (collective-goal $g $owner)))

; Goals owned by ANY given stakeholder (individual goal understanding).
(= (telos-goals-of $owner)
   (match &self (goal $g individual $owner $status) (goal-of $owner $g)))

; A goal is ACHIEVED when its status atom says so.
(= (telos-achieved $g)
   (match &self (goal $g $scope $owner achieved) True))

; BLOCKED: a goal that depends-on another goal that is not yet achieved.
(= (telos-blocked)
   (match &self (rel depends-on $g $dep)
      (match &self (goal $dep $s2 $o2 $st2)
         (if (== $st2 achieved) (empty) (blocked $g on $dep)))))

; Cross-level ALIGNMENT: an individual goal that SUPPORTS a collective goal.
(= (telos-aligned)
   (match &self (rel supports $i $c)
      (match &self (goal $i individual $o1 $s1)
         (match &self (goal $c collective $o2 $s2)
            (aligns $i with $c)))))

; A full goal reading: run every lens. Call after asserting the goal/rel atoms.
(= (telos-reading)
   (superpose ((telos-conflicts)
               (telos-collective-goals)
               (telos-blocked)
               (telos-aligned))))
