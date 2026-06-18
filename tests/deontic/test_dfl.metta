!(import! &self (library OmegaClaw-Core lib_deontic))
; DFL (arrow format) parser tests. The DFL surface notation is validated by
; comparing each .dfl theory to its hand-built .metta equivalent: both must produce
; the same defeasible conclusions, confirming the two front ends compile to the
; same underlying theory.

; penguin.dfl  ==  penguin.metta  (facts, defeasible rules, superiority, negation)
!(test (dl-run (dl-path tests/deontic/fixtures/penguin.dfl))
       (dl-run (dl-path tests/deontic/fixtures/penguin.metta)))

; strict + defeater + negation:  dfl_mixed.dfl == its MeTTa equivalent
!(test (dl-run (dl-path tests/deontic/fixtures/dfl_mixed.dfl))
       (dl-run (dl-path tests/deontic/fixtures/dfl_mixed_sexpr.metta)))

; multi-literal bodies, front-matter blocks (skipped), assignments via DFL
; (annotated.dfl is a representative annotated DFL example)
!(dl-run (dl-path tests/deontic/fixtures/annotated.dfl))
(= (is-pd $f) (is-member (pd (lit pos none none $f ())) (dl-conclusions)))
!(test (map-atom (ready_auth assignTo_auth_coder assignTo_auth_security) $f (is-pd $f))
       (True True True))

!(println! test-dfl-done)
