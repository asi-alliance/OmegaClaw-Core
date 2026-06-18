!(import! &self (library OmegaClaw-Core lib_deontic))
; Query operator tests: why-not / requires / explain / abduce / what-if.
; Each expected value is the golden result of the query on the named fixture
; (see comments per test).


; ---------------------------------------------------------------
; why-not on missing_premise.metta
; would derive via r1; blocked because the premise tests-pass is missing
; ---------------------------------------------------------------
!(dl-run (dl-path tests/deontic/fixtures/missing_premise.metta))
!(test (dl-why-not (lit pos none none ready-review ()))
       (whynot (lit pos none none ready-review ())
               (would r1)
               (blockers ((missing r1 ((lit pos none none tests-pass ())))))))

; abduce on the same state
; the one missing premise needed is: {tests-pass}
!(test (dl-abduce (lit pos none none ready-review ()))
       (abduction (lit pos none none ready-review ())
                  (solutions (((lit pos none none tests-pass ()))))))

; requires verifies by injection + re-reasoning
!(test (dl-requires (dl-path tests/deontic/fixtures/missing_premise.metta)
                         (lit pos none none ready-review ()))
       (requires (lit pos none none ready-review ())
                 (verified ((lit pos none none tests-pass ())))))

; ---------------------------------------------------------------
; why-not flies on penguin.metta
; would derive via r1; blocked because r2 contradicts it
; ---------------------------------------------------------------
!(dl-run (dl-path tests/deontic/fixtures/penguin.metta))
!(test (dl-why-not (lit pos none none flies ()))
       (whynot (lit pos none none flies ())
               (would r1)
               (blockers ((contradicted r1 r2)))))

; why-not on a provable literal reports provable
!(test (dl-why-not (lit neg none none flies ()))
       (whynot (lit neg none none flies ()) provable))

; explain +d ~flies: rule r2 over fact penguin (proof: r2 <- f2)
!(test (explain (lit neg none none flies ()))
       (proof (lit neg none none flies ())
              (rule r2 ((proof (lit pos none none penguin ()) (fact f2))))))

; explain a fact
!(test (explain (lit pos none none bird ()))
       (proof (lit pos none none bird ()) (fact f1)))

; ---------------------------------------------------------------
; why-not flies on defeater.metta: defeated by d1
; ---------------------------------------------------------------
!(dl-run (dl-path tests/deontic/fixtures/defeater.metta))
!(test (dl-why-not (lit pos none none flies ()))
       (whynot (lit pos none none flies ())
               (would r1)
               (blockers ((defeated r1 d1)))))

; ---------------------------------------------------------------
; what-if on strict_chain.metta: assuming e makes f provable
; ---------------------------------------------------------------
!(test (dl-what-if (dl-path tests/deontic/fixtures/strict_chain.metta)
                        ((lit pos none none e ()))
                        (lit pos none none f ()))
       (whatif provable
               (new (sort-atom ((lit pos none none e ()) (lit pos none none f ()))))
               (assumed ((lit pos none none e ())))))

; what-if that refutes: assuming penguin-theory hypothetical against ~flies
!(test (dl-what-if (dl-path tests/deontic/fixtures/penguin.metta)
                        ()
                        (lit pos none none flies ()))
       (whatif refuted (new ()) (assumed ())))

!(println! test-query-done)
