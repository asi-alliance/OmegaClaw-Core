; Defeasible Logic inference — the DL(d) proof theory (Nute; Antoniou et al.).
; Computed here as naive fixpoint sweeps over the ground theory; the same monotone
; conditions are realised by the fast worklist engine in platform/reason.pl.
;
; Phase 1  (+Δ): definite provability — facts + strict forward chaining.
; Phase 2  (+∂/-∂): defeasible provability — seeded, then swept with the standard
;          try-prove / try-disprove conditions, including:
;            - strict attackers can never be defeated by superiority;
;            - a defeasible attacker with an undecided body IS countered
;              if an applicable supporter is superior to it.
; Phase 3  closed-world emission: -Δ = not(+Δ), -∂ = not(+∂) at fixpoint.

; =====================================================================
; Phase 1: definite provability (+Δ)
; =====================================================================

(= (try-pD $q)
   (if (== (defp? $q) True)
       0
       (if (== () (collapse
             (match &ground (grule $l $k $b $q)
               (if (and (== (def-kind? $k) True) (== (body-all-defp $b) True))
                   yes
                   (empty)))))
           0
           (set-defp $q))))

(= (pass-pD)
   (foldall + (let $q (ulit-gen) (try-pD $q)) 0))

(= (phase1!) (if (> (pass-pD) 0) (phase1!) ()))

; =====================================================================
; Phase 2: defeasible provability (+∂/-∂)
; =====================================================================

; --- seeds (initialise +∂/-∂ before the sweep) ---
(= (seed-dft $q)
   (if (not (== (dft-of $q) unknown))
       0
       (if (== (defp? $q) True)
           (if (== (defp? (lit-neg $q)) True)
               (set-dft $q false)     ; +D q and +D ~q: condition (2) fails
               (set-dft $q true))     ; +D q and -D ~q: subsumption
           (if (== (has-sd-rule $q) True)
               0
               (set-dft $q false)))))  ; no Rsd support at all

(= (has-sd-rule $q)
   (case (once (match &ground (grule $l $k $b $q)
           (if (== (sd-kind? $k) True) yes (empty))))
     ((yes True) (Empty False))))

(= (seeds!)
   (let $_ (collapse (let $q (ulit-gen) (seed-dft $q))) ()))

; --- condition (1): ∃ applicable supporter in Rsd[q] ---
(= (has-applicable-sd $q)
   (case (once (match &ground (grule $l $k $b $q)
           (if (and (== (sd-kind? $k) True) (== (body-all-pd $b) True))
               yes
               (empty))))
     ((yes True) (Empty False))))

; --- ∃ applicable supporter t ∈ Rsd[q] with t > s (template labels) ---
(= (beaten? $q $ls)
   (case (once (match &ground (grule $lt $kt $bt $q)
           (if (and (== (sd-kind? $kt) True)
                    (and (== (body-all-pd $bt) True) (== (sup? $lt $ls) True)))
               yes
               (empty))))
     ((yes True) (Empty False))))

; --- try-prove a literal defeasibly (+∂): a supporter fires and all attackers clear ---
(= (try-pd $q)
   (if (not (== (dft-of $q) unknown))
       0
       (if (== (has-applicable-sd $q) False)
           0
           (if (== (defp? (lit-neg $q)) True)
               0
               (if (== (attack-clear $q) True)
                   (set-dft $q true)
                   0)))))

; condition (3): walk every attacker s ∈ R[~q] (all rule kinds).
(= (attack-clear $q)
   (let $nq (lit-neg $q)
     (att-walk $q (collapse
       (match &ground (grule $ls $ks $bs $nq) ($ls $ks $bs))))))

(= (att-walk $q $as)
   (if (== $as ())
       True
       (let ($ls $ks $bs) (car-atom $as)
         (if (== (body-some-nd $bs) True)
             (att-walk $q (cdr-atom $as))                 ; discarded attacker
             (if (== $ks strict)
                 False                                     ; strict always blocks
                 (if (== (beaten? $q $ls) True)
                     (att-walk $q (cdr-atom $as))          ; countered by superior
                     False))))))                           ; undefeated/undecided

; --- try-disprove a literal defeasibly (-∂): no supporter survives its attackers ---
(= (try-nd $q)
   (if (not (== (dft-of $q) unknown))
       0
       (if (== (defp? $q) True)
           0
           (if (== (defp? (lit-neg $q)) True)
               (set-dft $q false)                          ; disjunct (2)
               (if (== (all-sd-discarded $q) True)
                   (set-dft $q false)                      ; disjunct (1)
                   (if (== (unbeatable-attacker? $q) True)
                       (set-dft $q false)                  ; disjunct (3)
                       0))))))

(= (all-sd-discarded $q)
   (case (once (match &ground (grule $l $k $b $q)
           (if (and (== (sd-kind? $k) True) (== (body-some-nd $b) False))
               alive
               (empty))))
     ((alive False) (Empty True))))

(= (unbeatable-attacker? $q)
   (let $nq (lit-neg $q)
     (datt-walk $q (collapse
       (match &ground (grule $ls $ks $bs $nq) ($ls $ks $bs))))))

(= (datt-walk $q $as)
   (if (== $as ())
       False
       (let ($ls $ks $bs) (car-atom $as)
         (if (not (== (body-all-pd $bs) True))
             (datt-walk $q (cdr-atom $as))                 ; attacker not applicable
             (if (== $ks strict)
                 True                                      ; strict attacker: -d now
                 (if (== (any-defender-undecided $q $ls) True)
                     (datt-walk $q (cdr-atom $as))         ; wait for that defender
                     (if (== (all-defenders-fail $q $ls) True)
                         True
                         (datt-walk $q (cdr-atom $as)))))))))

; ∃t ∈ Rsd[q]: not discarded, body undecided, and t > s
(= (any-defender-undecided $q $ls)
   (case (once (match &ground (grule $lt $kt $bt $q)
           (if (and (== (sd-kind? $kt) True)
                    (and (== (body-some-nd $bt) False)
                         (and (not (== (body-all-pd $bt) True))
                              (== (sup? $lt $ls) True))))
               yes
               (empty))))
     ((yes True) (Empty False))))

; ∀t ∈ Rsd[q]: discarded OR not(t > s)
(= (all-defenders-fail $q $ls)
   (case (once (match &ground (grule $lt $kt $bt $q)
           (if (and (== (sd-kind? $kt) True)
                    (and (== (body-some-nd $bt) False) (== (sup? $lt $ls) True)))
               survivor
               (empty))))
     ((survivor False) (Empty True))))

; --- fixpoint sweep ---
(= (pass-dft)
   (foldall + (let $q (ulit-gen) (+ (try-pd $q) (try-nd $q))) 0))

(= (phase2!)
   (let $_ (seeds!)
     (phase2-loop!)))
(= (phase2-loop!) (if (> (pass-dft) 0) (phase2-loop!) ()))

; =====================================================================
; Phase 3: closed-world negatives (-Δ/-∂ at fixpoint)
; =====================================================================

(= (finalize-lit $q)
   (if (== (dft-of $q) unknown) (set-dft $q false) 0))

(= (phase3!)
   (let $_ (collapse (let $q (ulit-gen) (finalize-lit $q))) ()))

; =====================================================================
; Driver + conclusions
; =====================================================================

(= (reason!)
   (let* (($_1 (phase1!))
          ($_2 (phase2!))
          ($_3 (phase3!)))
     ()))

; Per-literal conclusion pair: (+D|-D) and (+d|-d), as tag tuples.
(= (concl-of $q)
   (superpose ((if (== (defp? $q) True) (pD $q) (nD $q))
               (if (== (dft-of $q) true) (pd $q) (nd $q)))))

(= (conclusions)
   (collapse (let $q (ulit-gen) (concl-of $q))))
