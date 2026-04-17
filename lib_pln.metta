;Shortcut for and with 5 args
(= (and5 $0 $1 $2 $3 $4)
   (and $0 (and $1 (and $2 (and $3 $4)))))

;Exclude division by 0
(= (/safe $A $B)
   (if (> $B 0.0)
       (/ $A $B)
       (empty)))

;Make sure $v is within the range ($min $max)
(= (clamp $v $min $max) (min $max (max $v $min)))
;Negate (1 minus)
(= (negate $arg) (- 1.0 $arg))

;Invert (1 over)
(= (invert $arg) (/safe 1.0 $arg))

;; Consistency Conditions: 
;; PLN book "5.2.2.2 PLN Deduction and Second-Order Probability", page 74:
;; borrowed from https://github.com/trueagi-io/hyperon-pln/blob/main/metta/pln/dependent-types/DeductionDTL.metta

(: smallest-intersection-probability (-> Number Number Number))
(= (smallest-intersection-probability $As $Bs)
   (clamp (/ (- (+ $As $Bs) 1) $As) 0 1))

(: largest-intersection-probability (-> Number Number Number))
(= (largest-intersection-probability $As $Bs)
   (clamp (/ $Bs $As) 0 1))

(: conditional-probability-consistency (-> Number Number Number Bool))
(= (conditional-probability-consistency $As $Bs $ABs)
   (and (< 0 $As)
        (and (<= (smallest-intersection-probability $As $Bs) $ABs)
             (<= $ABs (largest-intersection-probability $As $Bs)))))

(= (Consistency_ImplicationImplicantConjunction $As $Bs $Cs $ACs $BCs)
   ; Conditional probability consistency checks:
   ; P(C|A) <= P(C)/P(A)  =>  $sAC <= $sC / $sA
   ; P(C|B) <= P(C)/P(B)  =>  $sBC <= $sC / $sB
   ; Also ensure denominators are not zero for the checks.
   (and5 (> $As 0) (> $Bs 0) (> $Cs 0) ; Avoid division by zero and ensure meaningful probabilities
         (<= $ACs (/ $Cs $As))
         (<= $BCs (/ $Cs $Bs))))

;; Truth functions

;Forward declaration
(= (STV $X) (stv (/ 1.0 10.0) 0.9))

(: Truth__c2w (-> Number Number))
(= (Truth__c2w $c)
   (/safe $c (- 1 $c)))

(: Truth__w2c (-> Number Number))
(= (Truth__w2c $w)
   (/safe $w (+ $w 1)))

(: Truth__or (-> Number Number Number))
(= (Truth__or $a $b) 
   (- 1 (* (- 1 $a) (- 1 $b))))

; Deduction formula: PLN book "1.4 Truth-value Formulas", page 15:
; borrowed from https://github.com/trueagi-io/hyperon-pln/blob/main/metta/pln/dependent-types/DeductionDTL.metta
(= (Truth__Deduction (stv $Ps $Pc)
                    (stv $Qs $Qc)
                    (stv $Rs $Rc)
                    (stv $PQs $PQc)
                    (stv $QRs $QRc))
   (if (and (conditional-probability-consistency $Ps $Qs $PQs)
            (conditional-probability-consistency $Qs $Rs $QRs))
       ; Preconditions are met
       (stv (if (< 0.9999 $Qs)                  ; avoid division by 0
                ; Qs tends to 1
                $Rs
                ; Otherwise
                (+ (* $PQs $QRs) (/safe (* (- 1 $PQs) (- $Rs (* $Qs $QRs))) (- 1 $Qs))))
            (* (* $PQs $QRs) (* $PQc $QRc)))
       ; Preconditions are not met
       (stv 1 0)))

; Induction formula: PLN book "Appendix A: Comparison of PLN Rules with NARS Rules", page 307
(= (Truth__Induction (stv $sA $cA)
                    (stv $sB $cB)
                    (stv $sC $cC)
                    (stv $sBA $cBA)
                    (stv $sBC $cBC))
   (stv (+ (/safe (* (* $sBA $sBC) $sB) $sA)
           (* (- 1 (/safe (* $sBA $sB) $sA))
              (/safe (- $sC (* $sB $sBC)) (- 1 $sB))))
        (Truth__w2c (* (* $sBC $cBC) $cBA))))

(= (Truth__Abduction (stv $sA $cA)
                    (stv $sB $cB)
                    (stv $sC $cC)
                    (stv $sAB $cAB)
                    (stv $sCB $cCB))
   (stv (+ (/safe (* (* $sAB $sCB) $sC)
                  $sB)
           (/safe (* $sC (* (- 1 $sAB) (- 1 $sCB)))
                  (- 1 $sB)))
        (Truth__w2c (* (* $sAB $cAB) $cCB))))

;Modus Ponens: PLN book "5.7.1 Modus Ponens", page 111:
(= (Truth__ModusPonens (stv $Ps $Pc) (stv $PQs $PQc)) 
   (stv (+ (* $Ps $PQs) (* 0.02 (- 1 $Ps)))
        (* (* $Ps $PQs) (* $Pc $PQc))))

; SymmetricModusPonens rule   see https://github.com/opencog/pln/blob/master/opencog/pln/rules/wip/symmetric-modus-ponens.scm
(= (Truth__SymmetricModusPonens (stv $sA $cA) (stv $sAB $cAB))
   (let* (($snotAB 0.2)
          ($cnotAB 1.0))
         (stv (+ (* $sA $sAB) (* (* $snotAB (negate $sA)) (+ 1.0 $sAB)))
              (* (* $cA $cAB) (Truth__or $sA $sAB)))))

;Revision: PLN Book "5.10.2 A Heuristic Revision Rule for Simple Truth-values", page 116:
(= (Truth__Revision (stv $f1 $c1) (stv $f2 $c2))
   (let* (($w1 (Truth__c2w $c1))
          ($w2 (Truth__c2w $c2))
          ($w (+ $w1 $w2))
          ($f (/safe (+ (* $w1 $f1) (* $w2 $f2)) $w))
          ($c (Truth__w2c $w)))
         (stv (min 1.0 $f)
              (min 1.0 (max (max $c $c1) $c2)))))

; negation, see https://github.com/opencog/pln/blob/master/opencog/pln/rules/wip/negation-introduction.scm#L41
; negation elimination, see https://github.com/opencog/pln/blob/master/opencog/pln/rules/wip/not-elimination.scm#L34
(= (Truth__Negation (stv $s $c))
   (stv (- 1.0 $s) $c))

(= (Truth__inversion (stv $Bs $Bc) (stv $ABs $ABc))
   ; confidence depends on Truth of (target) B node, which is not according to OpenCOG classic.
   ; confidence penality not according to OpenCOG classic PLN. Is weaker in this implementation.
   (stv $ABs (* $Bc (* $ABc 0.6))))

; see https://github.com/opencog/pln/blob/master/opencog/pln/rules/wip/equivalence-to-implication.scm
(= (Truth__equivalenceToImplication (stv $As $Ac) (stv $Bs $Bc) (stv $ABs $ABc))
    (let* (($ConclS (if (< 0.99 (* $ABs $ABc)) ; Hack to work around the lack of distributional
                                               ; TV. If ABs is high enough, we just set $ConclS as $ABs
                        $ABs
                        ;; Formula based on PLN book formula for sim2inh
                        (/safe (* (+ 1.0 (/safe $Bs $As)) $ABs) (+ 1.0 $ABs)))))
          (stv $ConclS $ABc)))

; see https://github.com/opencog/pln/blob/master/opencog/pln/rules/wip/formulas.scm#L160-L173
(= (TransitiveSimilarityStrength $sA $sB $sC $sAB $sBC)
   (let* (($T1 (/ (* (+ 1.0 (/ $sB $sA)) $sAB) (+ 1.0 $sAB)))
          ($T2 (/ (* (+ 1.0 (/ $sC $sB)) $sBC) (+ 1.0 $sBC)))
          ($T3 (/ (* (+ 1.0 (/ $sB $sC)) $sBC) (+ 1.0 $sBC)))
          ($T4 (/ (* (+ 1.0 (/ $sA $sB)) $sAB) (+ 1.0 $sAB))))
         (invert (- (+ (invert (+ (* $T1 $T2) (* (negate $T1) (/safe (- $sC (* $sB $T2)) (negate $sB)))))
                       (invert (+ (* $T3 $T4) (* (negate $T3) (/safe (- $sC (* $sB $T4)) (negate $sB)))))) 1.0))))

; see https://github.com/opencog/pln/blob/master/opencog/pln/rules/wip/transitive-similarity.scm
(= (Truth__transitiveSimilarity (stv $As $Ac)
                               (stv $Bs $Bc)
                               (stv $Cs $Cc)
                               (stv $ABs $ABc)
                               (stv $BCs $BCc))
   (let* (($ConclS (TransitiveSimilarityStrength $As $Bs $Cs $ABs $BCs))
          ($ConclC (* (* $ABc $BCc) (Truth__or $ABs $BCs))))
         (stv $ConclS $ConclC)))

; see https://github.com/opencog/pln/blob/master/opencog/pln/rules/wip/formulas.scm
(= (simpleDeductionStrength $sA $sB $sC $sAB $sBC)
   (if (and (conditional-probability-consistency $sA $sB $sAB)
            (conditional-probability-consistency $sB $sC $sBC))
       ;; Preconditions are met
       (if (< 0.99 $sB)
           ;; sB tends to 1
           $sC
           ;; otherwise
           (+ (* $sAB $sBC) (/safe (* (- 1.0 $sAB) (- $sC (* $sB $sBC))) (- 1.0 $sB))))
       ;; Preconditions are not met
       (empty)))

; see https://github.com/opencog/pln/blob/master/opencog/pln/rules/wip/evaluation-implication.scm
(= (Truth__evaluationImplication (stv $As $Ac)
                                (stv $Bs $Bc)
                                (stv $Cs $Cc)
                                (stv $ABs $ABc)
                                (stv $ACs $ACc))
   (let* (($ConclS (simpleDeductionStrength $Bs $As $Cs $ABs $ACs))
          ($ConclC (* (* $ABs $ACs) (* $ABc $ACc))))
         (stv $ConclS $ConclC)))



;; INFERENCE RULES

;Revision
(= (|~pln ($T $T1) 
       ($T $T2))
   ($T (Truth__Revision $T1 $T2)))

;Modus Ponens
(= (|~pln ($A $T1) 
       ((Implication $A $B) $T2))
   ($B (Truth__ModusPonens $T1 $T2)))

; guard to only allow inference for certain link types
(= (SymmetricModusPonensRuleGuard Similarity) True)
(= (SymmetricModusPonensRuleGuard IntentionalSimilarity) True)
(= (SymmetricModusPonensRuleGuard ExtensionalSimilarity) True)

; SymmetricModusPonens rule, see https://github.com/opencog/pln/blob/master/opencog/pln/rules/wip/symmetric-modus-ponens.scm
(= (|~pln ($A $TruthA)
       (($LinkType $A $B) $TruthAB))
   (if (SymmetricModusPonensRuleGuard $LinkType)
       ($B (Truth__SymmetricModusPonens $TruthA $TruthAB)) (empty)))

; guard to only allow inference for certain link types
(= (SyllogisticRuleGuard Inheritance) True)
(= (SyllogisticRuleGuard Implication) True)

; Deduction rule, see https://github.com/opencog/pln/blob/master/opencog/pln/rules/term/deduction.scm
(= (|~pln (($LinkType $A $B) $T1)
          (($LinkType $B $C) $T2))
   (if (SyllogisticRuleGuard $LinkType)
       (($LinkType $A $C)
        (Truth__Deduction (STV $A)
                         (STV $B)
                         (STV $C) $T1 $T2)) (empty)))
      

; Induction rule, see https://github.com/opencog/pln/blob/master/opencog/pln/rules/wip/induction.scm
(= (|~pln (($LinkType $C $A) $T1)
       (($LinkType $C $B) $T2))
   (if (SyllogisticRuleGuard $LinkType)
       (($LinkType $A $B) (Truth__Induction (STV $A)
                                           (STV $B)
                                           (STV $C) $T1 $T2)) (empty)))

; Abduction rule, see https://github.com/opencog/pln/blob/master/opencog/pln/rules/wip/abduction.scm
(= (|~pln (($LinkType $A $C) $T1)
       (($LinkType $B $C) $T2))
   (if (SyllogisticRuleGuard $LinkType)
       (($LinkType $A $B) (Truth__Abduction (STV $A)
                                           (STV $B)
                                           (STV $C) $T1 $T2)) (empty)))

;Usage of inheritance for predicates
;unary arg
(= (|~pln ((Evaluation (Predicate $x)
                    (List (Concept $C))) $T1)
       ((Inheritance (Concept $S) (Concept $C)) $T2))
   ((Evaluation (Predicate $x)
                (List (Concept $S))) (Truth__ModusPonens $T1 $T2)))

;binary arg1
(= (|~pln ((Evaluation (Predicate $x)
                    (List (Concept $C1) (Concept $C2))) $T1)
       ((Inheritance (Concept $S) (Concept $C1)) $T2))
   ((Evaluation (Predicate $x)
                (List (Concept $S) (Concept $C2))) (Truth__ModusPonens $T1 $T2)))

;binary arg2
(= (|~pln ((Evaluation (Predicate $x)
                    (List (Concept $C1) (Concept $C2))) $T1)
       ((Inheritance (Concept $S) (Concept $C2)) $T2))
   ((Evaluation (Predicate $x)
                (List (Concept $C1) (Concept $S))) (Truth__ModusPonens $T1 $T2)))

; negation elimination rule (introduction now handled by Translator), see https://github.com/opencog/pln/blob/master/opencog/pln/rules/wip/not-elimination.scm#L1-L8
(= (|~pln ((Not $A) $T)) ($A (Truth__Negation $T)))

; Inheritance Inversion Rule, see https://github.com/opencog/pln/blob/master/opencog/pln/rules/wip/inversion.scm
(= (|~pln ((Inheritance $A $B) $Truth))
   ((Inheritance $B $A) (Truth__inversion (STV $B) $Truth)))

; Implication Inversion Rule (same)
(= (|~pln ((Implication $A $B) $Truth))
   ((Implication $B $A) (Truth__inversion (STV $B) $Truth)))

; Equivalence to Implication Rule, see https://github.com/opencog/pln/blob/master/opencog/pln/rules/wip/equivalence-to-implication.scm
(= (|~pln ((Equivalence $A $B) $Truth))
   ((Implication $A $B) (Truth__equivalenceToImplication (STV $A)
                                                        (STV $B) $Truth)))

(= (|~pln ((Equivalence $A $B) $Truth))
   ((Implication $B $A) (Truth__equivalenceToImplication (STV $A)
                                                        (STV $B) $Truth)))

; transitive similarity Rule, see https://github.com/opencog/pln/blob/master/opencog/pln/rules/wip/transitive-similarity.scm
(= (|~pln ((Similarity $A $B) $T1)
       ((Similarity $B $C) $T2))
   ((Similarity $A $C) (Truth__transitiveSimilarity (STV $A)
                                                   (STV $B)
                                                   (STV $C) $T1 $T2)))

; Evaluation Implication Rule, see https://github.com/opencog/pln/blob/master/opencog/pln/rules/wip/evaluation-implication.scm
(= (|~pln ((Evaluation $A $B) $TruthAB)
       ((Implication $A $C) $TruthAC))
   ((Evaluation $C $B) (Truth__evaluationImplication (STV $A)
                                                    (STV $B)
                                                    (STV $C) $TruthAB $TruthAC)))

; extensional - Member deduction rule, see https://github.com/opencog/pln/blob/master/opencog/pln/rules/extensional/member-deduction.scm
; we are using the truth of deduction here
(= (|~pln ((Member $A $B) $T1)
       ((Inheritance $B $C) $T2))
   ((Member $A $C) (Truth__Deduction (STV $A)
                                     (STV $B)
                                     (STV $C) $T1 $T2)))

(= (|~ $a $b)
   (unique-atom (collapse (superpose ((|~pln $a $b) (|~pln $b $a))))))


