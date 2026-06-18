; lib_deontic <-> NAL belief-bridge tests (opt-in Feature A).
; Unlike the earlier design-stage seam, NAL is actually present, so these assert
; real cross-engine behavior: the trust<->(stv) numeric bridge, the literal<->NAL
; term mapping both ways, projecting defeasible conclusions out to beliefs,
; injecting credible beliefs back in, and a full belief->reason->belief round trip.
!(import! &self (library OmegaClaw-Core src/integration/nal))

; float-tolerant equality (NAL truth math is floating point)
(= (approx $a $b) (< (let $d (- $a $b) (if (< $d 0.0) (- 0.0 $d) $d)) 0.0001))

; --- trust <-> truth value (projected expectation E = c*(f-0.5)+0.5) ---
!(test (approx (stv->trust (stv 1.0 0.9)) 0.95) True)
!(test (approx (stv->trust (stv 0.0 0.9)) 0.05) True)
!(test (trust->stv 0.7) (stv 0.7 (Truth_w2c 2.0)))

; --- literal <-> NAL term ---
!(test (lit->term (lit pos none none bird ())) bird)
!(test (lit->term (lit pos none none flies (tweety))) (--> tweety flies))
!(test (lit->term (lit pos none none parent (alice bob))) (--> (× alice bob) parent))
!(test (term->plit bird) (lit pos none none bird ()))
!(test (term->plit (--> tweety flies)) (lit pos none none flies (tweety)))
!(test (term->plit (--> (× alice bob) parent)) (lit pos none none parent (alice bob)))

; --- conclusion -> belief (factual + defeasible only; sign sets frequency) ---
!(test (concl->belief (pd (lit pos none none bird ()))) (bird (stv 1.0 0.81)))
!(test (concl->belief (pd (lit neg none none flies ()))) (flies (stv 0.0 0.81)))
!(test (concl->belief (nd (lit pos none none flies ()))) ())
!(test (concl->belief (pd (lit pos O none pay ()))) ())

; --- belief -> deontic fact (signed by belief direction; expectation-gated) ---
!(test (belief->fact (bird (stv 1.0 0.9)) 0.5) (dfact (lit pos none none bird ()) 0.95))
!(test (belief->fact (flies (stv 0.0 0.9)) 0.5) (dfact (lit neg none none flies ()) 0.95))
!(test (belief->fact (bird (stv 0.5 0.9)) 0.5) ())

; --- project a real defeasible run OUT to beliefs (penguin: flies is false) ---
!(test (is-member (bird (stv 1.0 0.81))
                  (theory->beliefs (dl-path examples/deontic/penguin.metta))) True)
!(test (is-member (flies (stv 0.0 0.81))
                  (theory->beliefs (dl-path examples/deontic/penguin.metta))) True)

; --- full round trip: NAL belief -> injected fact -> defeasible reasoning ->
;     new belief. bird is supplied only by the injected belief; r1 then derives flies. ---
!(test (is-member (flies (stv 1.0 0.81))
                  (combined-step (dl-path tests/integration/bridge_demo.metta)
                                 ((bird (stv 1.0 0.9))) 0.5)) True)

; --- NAL revision fuses two evidence sources about the same term ---
!(test (is-member (bird (Truth_Revision (stv 1.0 0.5) (stv 1.0 0.5)))
                  (infer (bird (stv 1.0 0.5)) (bird (stv 1.0 0.5)))) True)

!(println! test-nal-done)
