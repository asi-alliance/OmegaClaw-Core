!(import! &self (library OmegaClaw-Core lib_deontic))
; Standard Deontic Logic layer (opt-in; the base defeasible logic carries modes
; O/P/F without inferring, and this layer adds the SDL bridges). Canonical
; relationships:
;   F p ≡ O ¬p   (forbidden = obligatory-not)
;   O p → P p    (ought implies may, under deontic consistency)
; Verified sound on modal.metta; the default reason path leaves plain defeasible
; reasoning untouched.


(= (concl? $lit) (is-member $lit (dl-conclusions)))

; --- deontic closure of (must pay)(may relax)(forbidden steal) ---
!(dl-run-deontic (dl-path tests/deontic/fixtures/modal.metta))

; O pay  →  P pay     (ought implies may)
!(test (concl? (pd (lit pos P none pay ()))) True)
; O pay  →  F ¬pay    (obligatory ≡ forbidden-not)
!(test (concl? (pd (lit neg F none pay ()))) True)
; F steal →  O ¬steal (forbidden ≡ obligatory-not)
!(test (concl? (pd (lit neg O none steal ()))) True)
; O ¬steal → P ¬steal (chained: ought-not implies may-not)
!(test (concl? (pd (lit neg P none steal ()))) True)
; the bare permission stays put (P is a sink — no spurious obligations)
!(test (concl? (pd (lit pos O none relax ()))) False)

; --- DEFEASIBLE INTERACTION: superiority resolves a deontic conflict ---
; r1: a => O p   r2: a => F p   (prefer r1 r2).  Since F p ≡ O ¬p and the
; equivalence carries r2's label, O p (r1) attacks O ¬p (r2) and r1 > r2 wins:
; obligation holds, permission follows, forbidden is defeated.
!(dl-run-deontic (dl-path tests/deontic/fixtures/deontic_conflict.metta))
!(test (concl? (pd (lit pos O none p ()))) True)    ; O p wins
!(test (concl? (pd (lit pos P none p ()))) True)    ; O p -> P p
!(test (concl? (pd (lit pos F none p ()))) False)   ; F p defeated
!(test (concl? (pd (lit neg O none p ()))) False)   ; O ¬p defeated

; --- STRONG PERMISSION defeats a contrary defeasible prohibition ---
; r1: a => F p   plus an explicit (may p). The permission emits a defeater that
; blocks the prohibition (in both its F and O¬ forms); only the permission holds.
!(dl-run-deontic (dl-path tests/deontic/fixtures/perm_defeats.metta))
!(test (concl? (pd (lit pos P none p ()))) True)    ; permission holds
!(test (concl? (pd (lit pos F none p ()))) False)   ; prohibition defeated
!(test (concl? (pd (lit neg O none p ()))) False)   ; ...in its O¬ form too

; --- DILEMMA: O p vs F p with no superiority is flagged as unresolved ---
!(test (size-atom (deontic-dilemmas (dl-path tests/deontic/fixtures/deontic_dilemma.metta))) 1)
; ...and a superiority resolves it (no dilemma)
!(test (size-atom (deontic-dilemmas (dl-path tests/deontic/fixtures/deontic_conflict.metta))) 0)

; --- opt-in: the DEFAULT path derives none of the deontic consequences ---
!(dl-run (dl-path tests/deontic/fixtures/modal.metta))
!(test (concl? (pd (lit pos P none pay ()))) False)
!(test (concl? (pd (lit neg O none steal ()))) False)
; ...but still has the three modal facts themselves
!(test (concl? (pd (lit pos O none pay ()))) True)

!(println! test-deontic-done)
