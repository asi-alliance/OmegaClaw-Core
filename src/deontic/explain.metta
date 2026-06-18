; Proof-tree extraction: reconstruct WHY a literal is (un)provable as a tree of
; rule applications over sub-goals — the justification that deontic verdicts and
; weakest-link trust both fold over.
;
; (explain <lit>) over the current reasoned state:
;   (proof <lit> (fact <label>))                      fact leaf
;   (proof <lit> (rule <label> (<sub-proofs...>)))    rule application
;   (no-proof <lit>)                                  not positively provable
; Attribution is deterministic: the lexicographically smallest applicable
; supporting rule (a stable tie-break when several rules support a literal).

(= (explain $lit) (explain-v $lit ()))

(= (explain-v $lit $seen)
   (if (== (is-member $lit $seen) True)
       (cycle $lit)
       (if (== (pos? $lit) True)
           (let $sup (best-supporter $lit)
             (if (== $sup ())
                 (no-proof $lit)
                 (let ($l $k $b) $sup
                   (if (== $k fact)
                       (proof $lit (fact $l))
                       (proof $lit (rule $l (explain-body $b (cons-atom $lit $seen))))))))
           (no-proof $lit))))

(= (explain-body $b $seen)
   (map-atom $b $x (explain-v $x $seen)))

; Smallest-label applicable supporter at the strongest level available:
; definite supporters (fact/strict with +D bodies) win over defeasible ones.
(= (best-supporter $lit)
   (let $def (applicable-supporters $lit def)
     (if (not (== $def ()))
         (car-atom (sort-atom $def))
         (let $sd (applicable-supporters $lit dft)
           (if (== $sd ()) () (car-atom (sort-atom $sd)))))))

(= (applicable-supporters $lit def)
   (collapse (match &ground (grule $l $k $b $lit)
     (if (and (== (def-kind? $k) True) (== (body-all-defp $b) True))
         ($l $k $b)
         (empty)))))

(= (applicable-supporters $lit dft)
   (collapse (match &ground (grule $l $k $b $lit)
     (if (and (== (sd-kind? $k) True) (== (body-all-pd $b) True))
         ($l $k $b)
         (empty)))))
