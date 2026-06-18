!(import! &self (library OmegaClaw-Core lib_deontic))
; Temporal + modal tests using the (during LIT ?T) interval-handle syntax, which
; binds an interval handle ?T, and the 13 Allen interval relations relate two
; handles. The cases here cover all 13 Allen relations; allen_intervals.metta is a
; single fixture that exercises each of the 13 relations plus negative controls.


; ---------------------------------------------------------------
; temporal fact + rule matching it via an interval variable
;   +D/+d meeting[10,20], +d busy, -D busy
; ---------------------------------------------------------------
!(test (dl-run (dl-path tests/deontic/fixtures/temporal_fact.metta))
       (sort-atom ((pD (lit pos none (iv 10 20) meeting ()))
                   (pd (lit pos none (iv 10 20) meeting ()))
                   (pd (lit pos none none busy ()))
                   (nD (lit pos none none busy ())))))

; ---------------------------------------------------------------
; Allen `before` over interval handles: a=[10,20] before b=[25,35] -> seq-ab
; ---------------------------------------------------------------
!(test (dl-run (dl-path tests/deontic/fixtures/allen_seq.metta))
       (sort-atom ((pD (lit pos none (iv 10 20) ev (a)))
                   (pD (lit pos none (iv 25 35) ev (b)))
                   (pd (lit pos none (iv 10 20) ev (a)))
                   (pd (lit pos none (iv 25 35) ev (b)))
                   (pd (lit pos none none seq-ab ()))
                   (nD (lit pos none none seq-ab ())))))

; ---------------------------------------------------------------
; modal operators as distinct atoms (O/P/F differ in the mode slot)
; ---------------------------------------------------------------
!(test (dl-run (dl-path tests/deontic/fixtures/modal.metta))
       (sort-atom ((pD (lit pos O none pay ()))
                   (pd (lit pos O none pay ()))
                   (pD (lit pos P none relax ()))
                   (pd (lit pos P none relax ()))
                   (pD (lit pos F none steal ()))
                   (pd (lit pos F none steal ())))))
!(test (lit-neg (lit pos O none pay ())) (lit neg O none pay ()))

; ---------------------------------------------------------------
; all 13 Allen relations (one fixture covering every relation): each result-* fires +d,
; each negative-test literal never fires (its rule's constraint fails so it
; isn't even in the universe — not present at any tag).
; ---------------------------------------------------------------
(= (concl-has $cs $tag $f)
   (is-member ($tag (lit pos none none $f ())) $cs))

!(test (let $cs (dl-run (dl-path tests/deontic/fixtures/allen_intervals.metta))
         (map-atom (result-before result-after result-meets result-met-by
                    result-overlaps result-overlapped-by result-starts result-started-by
                    result-within result-contains result-finishes result-finished-by
                    result-equals)
                   $r (concl-has $cs pd $r)))
       (True True True True True True True True True True True True True))

; the five negative-test literals are absent entirely (not +d and not -d)
!(test (let $cs (dl-run (dl-path tests/deontic/fixtures/allen_intervals.metta))
         (map-atom (neg-before neg-meets neg-overlaps neg-within neg-equals)
                   $n (or (concl-has $cs pd $n) (concl-has $cs nd $n))))
       (False False False False False))

; ---------------------------------------------------------------
; --at filtering: p[100,200] active at 150, filtered out at 300
; ---------------------------------------------------------------
!(test (dl-run-at (dl-path tests/deontic/fixtures/temporal_at.metta) 150)
       (sort-atom ((pD (lit pos none none q ()))
                   (pd (lit pos none none q ()))
                   (pD (lit pos none (iv 100 200) p ()))
                   (pd (lit pos none (iv 100 200) p ())))))

!(test (dl-run-at (dl-path tests/deontic/fixtures/temporal_at.metta) 300)
       (sort-atom ((pD (lit pos none none q ()))
                   (pd (lit pos none none q ())))))

!(println! test-temporal-done)
