; Plan analysis: dependency-cycle (deadlock) detection over the support graph,
; and self-inconsistency (contradictory definite conclusions). Cyclic
; dependencies can never be grounded from facts, so a cycle is a deadlock; a
; well-formed plan has none and is consistent.

!(import! &self (library OmegaClaw-Core lib_directive))

; deadlock plan: ready-a ⇄ ready-b is one cyclic dependency group
!(test (size-atom (plan-cycles (dl-path tests/deontic/fixtures/plan_cycle.metta))) 1)
; a well-formed directive plan has no dependency cycles
!(test (size-atom (plan-cycles (dl-path tests/deontic/fixtures/basic-tasks.metta))) 0)
; penguin is acyclic too
!(test (size-atom (plan-cycles (dl-path tests/deontic/fixtures/penguin.metta))) 0)

; self-inconsistent plan (strict p and ¬p) is flagged; well-formed plans are not
!(test (plan-consistent? (dl-path tests/deontic/fixtures/plan_incon.metta)) False)
!(test (plan-consistent? (dl-path tests/deontic/fixtures/basic-tasks.metta)) True)
!(test (plan-consistent? (dl-path tests/deontic/fixtures/penguin.metta)) True)

; the analyze renderer runs end-to-end
!(test (directive-analyze (dl-path tests/deontic/fixtures/plan_cycle.metta)) true)

!(println! test-analyze-done)
