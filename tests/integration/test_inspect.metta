; Plan-inspection commands (trace / validate / assign). These assertions pin the
; structured results (sorted assignment sets, validity verdicts) so regressions
; in extraction or rendering surface as concrete value mismatches.

!(import! &self (library OmegaClaw-Core lib_directive))

; assign: active (non-completed) assignment literals, sorted, all agents.
!(test (let* (($_ (dl-run (dl-path tests/deontic/fixtures/basic-tasks.metta)))
              ($names (directive-pos-names)))
         (assign-names $names ""))
       (assign-to-auth-coder assign-to-auth-reviewer assign-to-models-coder))

; assign filtered by a specific agent (reviewer only gets the auth-reviewer slot).
!(test (let* (($_ (dl-run (dl-path tests/deontic/fixtures/basic-tasks.metta)))
              ($names (directive-pos-names)))
         (assign-names $names reviewer))
       (assign-to-auth-reviewer))

; validate: a well-formed plan is valid (the dangling tests-failing literal only
; yields warnings, not errors, in non-strict mode).
!(test (directive-validate (dl-path tests/deontic/fixtures/basic-tasks.metta) False) True)

; penguin.metta is clean -> valid with no warnings.
!(test (directive-validate (dl-path tests/deontic/fixtures/penguin.metta) False) True)

!(println! test-inspect-done)
