!(import! &self (library OmegaClaw-Core lib_deontic))
; Incremental (append-only) grounding: a session that loads a base plan then
; APPENDS delta plans, grounding only the new closure each time (semi-naive,
; add-only), must yield IDENTICAL conclusions to a from-scratch load of the
; concatenated plan. This is the correctness contract for the optimization.


; incremental session: base, then two appended deltas (the second adds a new rule)
(= (incr-result)
   (let* (($_1 (dl-load-incr   (dl-path tests/deontic/fixtures/incr_base.metta)))
          ($_2 (dl-append-incr! (dl-path tests/deontic/fixtures/incr_delta1.metta)))
          ($_3 (dl-append-incr! (dl-path tests/deontic/fixtures/incr_delta2.metta))))
     (dl-reason-incr)))

; the same plan loaded from scratch (base ++ delta1 ++ delta2)
!(test (incr-result) (dl-run (dl-path tests/deontic/fixtures/incr_combined.metta)))

; incremental delta after only the FIRST append also matches its concatenation
(= (incr-result-1)
   (let* (($_1 (dl-load-incr   (dl-path tests/deontic/fixtures/incr_base.metta)))
          ($_2 (dl-append-incr! (dl-path tests/deontic/fixtures/incr_delta1.metta))))
     (dl-reason-incr)))

!(test (incr-result-1) (dl-run (dl-path tests/deontic/fixtures/incr_base1.metta)))

!(println! test-incremental-done)
