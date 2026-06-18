!(import! &self (library OmegaClaw-Core lib_deontic))
; Core defeasible-logic engine tests.
; Expected values are golden conclusion sets for each fixture.
; Conclusions are compared as sorted sets of (tag lit) tuples;
; tags: pD = +D, nD = -D, pd = +d, nd = -d (the DL(d) definite/defeasible
; proof tags +Δ/−Δ and +∂/−∂).


; ---------------------------------------------------------------
; penguin.metta: superiority resolves the conflict in favour of r2
; ---------------------------------------------------------------
!(test (dl-run (dl-path tests/deontic/fixtures/penguin.metta))
       (sort-atom ((pD (lit pos none none bird ()))
                   (pD (lit pos none none penguin ()))
                   (pd (lit pos none none bird ()))
                   (pd (lit pos none none penguin ()))
                   (pd (lit neg none none flies ()))
                   (nD (lit neg none none flies ()))
                   (nD (lit pos none none flies ()))
                   (nd (lit pos none none flies ())))))

; ---------------------------------------------------------------
; conflict_facts.metta: +D both, -d both (condition 2)
; ---------------------------------------------------------------
!(test (dl-run (dl-path tests/deontic/fixtures/conflict_facts.metta))
       (sort-atom ((pD (lit neg none none p ()))
                   (pD (lit pos none none p ()))
                   (nd (lit pos none none p ()))
                   (nd (lit neg none none p ())))))

; ---------------------------------------------------------------
; ambiguity.metta: unresolved conflict blocks both sides
; ---------------------------------------------------------------
!(test (dl-run (dl-path tests/deontic/fixtures/ambiguity.metta))
       (sort-atom ((pD (lit pos none none a ()))
                   (pd (lit pos none none a ()))
                   (nD (lit pos none none q ()))
                   (nd (lit pos none none q ()))
                   (nD (lit neg none none q ()))
                   (nd (lit neg none none q ())))))

; ---------------------------------------------------------------
; defeater.metta: d1 vetoes flies without proving ~flies
; ---------------------------------------------------------------
!(test (dl-run (dl-path tests/deontic/fixtures/defeater.metta))
       (sort-atom ((pD (lit pos none none bird ()))
                   (pD (lit pos none none injured ()))
                   (pd (lit pos none none bird ()))
                   (pd (lit pos none none injured ()))
                   (nD (lit neg none none flies ()))
                   (nd (lit neg none none flies ()))
                   (nD (lit pos none none flies ()))
                   (nd (lit pos none none flies ())))))

; ---------------------------------------------------------------
; strict_chain.metta: a -> b -> c, then c => d; e => f never fires
; ---------------------------------------------------------------
!(test (dl-run (dl-path tests/deontic/fixtures/strict_chain.metta))
       (sort-atom ((pD (lit pos none none a ()))
                   (pD (lit pos none none b ()))
                   (pD (lit pos none none c ()))
                   (pd (lit pos none none a ()))
                   (pd (lit pos none none b ()))
                   (pd (lit pos none none c ()))
                   (pd (lit pos none none d ()))
                   (nD (lit pos none none d ()))
                   (nD (lit pos none none e ()))
                   (nd (lit pos none none e ()))
                   (nD (lit pos none none f ()))
                   (nd (lit pos none none f ())))))

; ---------------------------------------------------------------
; superiority.metta: r3 > r2 lets p through; ~p stays blocked
; ---------------------------------------------------------------
!(test (dl-run (dl-path tests/deontic/fixtures/superiority.metta))
       (sort-atom ((pD (lit pos none none a ()))
                   (pd (lit pos none none a ()))
                   (pd (lit pos none none p ()))
                   (nD (lit pos none none p ()))
                   (nD (lit neg none none p ()))
                   (nd (lit neg none none p ())))))

; ---------------------------------------------------------------
; strict_beats_def.metta: strict attacker ignores superiority
; ---------------------------------------------------------------
!(test (dl-run (dl-path tests/deontic/fixtures/strict_beats_def.metta))
       (sort-atom ((pD (lit pos none none a ()))
                   (pD (lit pos none none b ()))
                   (pD (lit neg none none p ()))
                   (pd (lit pos none none a ()))
                   (pd (lit pos none none b ()))
                   (pd (lit neg none none p ()))
                   (nD (lit pos none none p ()))
                   (nd (lit pos none none p ())))))

; ---------------------------------------------------------------
; variables.metta: Datalog grounding with transitive ancestor
; ---------------------------------------------------------------
!(test (dl-run (dl-path tests/deontic/fixtures/variables.metta))
       (sort-atom ((pD (lit pos none none parent (alice bob)))
                   (pD (lit pos none none parent (bob carol)))
                   (pD (lit pos none none ancestor (alice bob)))
                   (pD (lit pos none none ancestor (bob carol)))
                   (pd (lit pos none none parent (alice bob)))
                   (pd (lit pos none none parent (bob carol)))
                   (pd (lit pos none none ancestor (alice bob)))
                   (pd (lit pos none none ancestor (bob carol)))
                   (pd (lit pos none none ancestor (alice carol)))
                   (nD (lit pos none none ancestor (alice carol))))))

; ---------------------------------------------------------------
; arith.metta: guards filter substitutions; bind extends them
; ---------------------------------------------------------------
!(test (dl-run (dl-path tests/deontic/fixtures/arith.metta))
       (sort-atom ((pD (lit pos none none salary (alice 120000)))
                   (pD (lit pos none none salary (bob 85000)))
                   (pd (lit pos none none salary (alice 120000)))
                   (pd (lit pos none none salary (bob 85000)))
                   (pd (lit pos none none double-pay (alice 240000)))
                   (pd (lit pos none none double-pay (bob 170000)))
                   (pd (lit pos none none high-earner (alice)))
                   (nD (lit pos none none double-pay (alice 240000)))
                   (nD (lit pos none none double-pay (bob 170000)))
                   (nD (lit pos none none high-earner (alice))))))

!(println! test-core-done)
