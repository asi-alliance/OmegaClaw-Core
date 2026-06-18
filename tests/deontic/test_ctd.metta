!(import! &self (library OmegaClaw-Core lib_deontic))
; Contrary-to-duty (CTD) reparation chains — Governatori's ⊗ operator, via the
; (otherwise D1 D2 ... Dn) rule-head syntax (one of the deontic extensions).
; O(¬litter ⊗ pay_fine ⊗ apologize): primary "don't litter", reparation
; "pay the fine" if that's violated, "apologize" if that's also violated.


(= (concl? $lit) (is-member $lit (dl-conclusions)))

; --- violation activates the reparation ---
!(dl-run (dl-path tests/deontic/fixtures/ctd_violated.metta))
!(test (concl? (pd (lit pos F none litter ()))) True)       ; primary prohibition holds
!(test (concl? (pd (lit pos O none pay_fine ()))) True)     ; reparation O pay_fine active
!(test (concl? (pd (lit pos O none apologize ()))) False)   ; 2nd reparation NOT yet (fine pending)
; compliance: primary violated, reparation pending
!(test (compliance-of (lit pos F none litter ())) violated)
!(test (compliance-of (lit pos O none pay_fine ())) pending)

; --- no violation -> no reparation ---
!(dl-run (dl-path tests/deontic/fixtures/ctd_clean.metta))
!(test (concl? (pd (lit pos F none litter ()))) True)
!(test (concl? (pd (lit pos O none pay_fine ()))) False)    ; reparation dormant
!(test (compliance-of (lit pos F none litter ())) pending)  ; not littered -> not violated

; --- cascade: primary AND first reparation violated -> 2nd reparation fires ---
!(dl-run (dl-path tests/deontic/fixtures/ctd_cascade.metta))
!(test (concl? (pd (lit pos O none pay_fine ()))) True)
!(test (concl? (pd (lit pos O none apologize ()))) True)    ; cascaded
!(test (compliance-of (lit pos O none pay_fine ())) violated) ; fine unpaid

!(println! test-ctd-done)
