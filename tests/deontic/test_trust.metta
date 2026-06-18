!(import! &self (library OmegaClaw-Core lib_deontic))
; Trust-weighted reasoning tests.
; Golden trust-annotated conclusions:
;   +D rain (trust: 0.90) [alice]   +D cold (trust: 0.50) [bob]
;   +d miserable (trust: 0.00) [alice, bob]   -D miserable (trust: 0.00)
; Trust = weakest link over the proof tree; rule nodes default to 0.0 so any
; rule-derived literal is 0.00 unless every step is a trusted fact.


!(dl-run (dl-path tests/deontic/fixtures/trust.metta))

; fact trust = claiming source's trust value, with source attribution
!(test (trust-of (lit pos none none rain ())) 0.9)
!(test (sources-of (lit pos none none rain ())) (alice))
!(test (trust-of (lit pos none none cold ())) 0.5)
!(test (sources-of (lit pos none none cold ())) (bob))

; derived trust = weakest link (rule default 0.0); sources are the union
!(test (trust-of (lit pos none none miserable ())) 0.0)
!(test (sources-of (lit pos none none miserable ())) (alice bob))

; full trust-annotated conclusion set
!(test (dl-trust-run (dl-path tests/deontic/fixtures/trust.metta))
       (sort-atom ((tconcl pD (lit pos none none rain ()) 0.9 (alice))
                   (tconcl pd (lit pos none none rain ()) 0.9 (alice))
                   (tconcl pD (lit pos none none cold ()) 0.5 (bob))
                   (tconcl pd (lit pos none none cold ()) 0.5 (bob))
                   (tconcl pd (lit pos none none miserable ()) 0.0 (alice bob))
                   (tconcl nD (lit pos none none miserable ()) 0.0 ()))))

; rendering matches the canonical trust line format
!(test (mm_trust_str (tconcl pD (lit pos none none rain ()) 0.9 (alice)))
       "+D rain (trust: 0.90) [alice]")
!(test (mm_trust_str (tconcl nD (lit pos none none miserable ()) 0.0 ()))
       "-D miserable (trust: 0.00)")

; threshold filtering (a literal passes iff its trust degree >= threshold)
!(test (meets-threshold (lit pos none none rain ()) credible) True)
!(test (meets-threshold (lit pos none none miserable ()) credible) False)

; unified justification: status + trust + confidence + sources + proof in one
!(test (justify (lit pos none none rain ()))
       (justification (literal (lit pos none none rain ()))
                      (status definitely-provable)
                      (trust 0.9)
                      (confidence high)
                      (sources (alice))
                      (proof (proof (lit pos none none rain ()) (fact f1)))))
; a rule-derived literal: low confidence (weakest link through a rule node = 0.0)
!(test (status-of (lit pos none none miserable ())) defeasibly-provable)
!(test (confidence-label (trust-of (lit pos none none miserable ()))) none)

!(println! test-trust-done)
