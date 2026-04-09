;; Truth functions
(= (Truth_c2w $c)
   (/ $c (- 1 $c)))

(= (Truth_w2c $w)
   (/ $w (+ $w 1)))

(= (Truth_Deduction (stv $f1 $c1)
                    (stv $f2 $c2))
   (stv (* $f1 $f2) (* (* $f1 $f2) (* $c1 $c2))))

(= (Truth_Abduction (stv $f1 $c1) 
                    (stv $f2 $c2))
   (stv $f2 (Truth_w2c (* (* $f1 $c1) $c2))))

(= (Truth_Induction $T1 $T2)
   (Truth_Abduction $T2 $T1))

(= (Truth_Exemplification (stv $f1 $c1)
                          (stv $f2 $c2))
   (stv 1.0 (Truth_w2c (* (* $f1 $f2) (* $c1 $c2)))))

(= (Truth_StructuralDeduction $T)
   (Truth_Deduction $T (stv 1.0 0.9)))
  
(= (Truth_Negation (stv $f $c))
   (stv (- 1 $f) $c))

(= (Truth_StructuralDeductionNegated $T)
   (Truth_Negation (Truth_StructuralDeduction $T)))

(= (Truth_Intersection (stv $f1 $c1) 
                       (stv $f2 $c2))
   (stv (* $f1 $f2) (* $c1 $c2)))

(= (Truth_StructuralIntersection $T)
   (Truth_Intersection $T (stv 1.0 0.9)))

(= (Truth_or $a $b)
   (- 1 (* (- 1 $a) (- 1 $b))))

(= (Truth_Comparison (stv $f1 $c1)
                     (stv $f2 $c2))
   (let $f0 (Truth_or $f1 $f2) 
        (stv (if (== $f0 0.0)
                 0.0 
                 (/ (* $f1 $f2) $f0))
             (Truth_w2c (* $f0 (* $c1 $c2))))))
  
(= (Truth_Analogy (stv $f1 $c1)
                  (stv $f2 $c2))
   (stv (* $f1 $f2) (* (* $c1 $c2) $f2)))

(= (Truth_Resemblance (stv $f1 $c1)
                      (stv $f2 $c2))
   (stv (* $f1 $f2) (* (* $c1 $c2) (Truth_or $f1 $f2))))

(= (Truth_Union (stv $f1 $c1)
                (stv $f2 $c2))
   (stv (Truth_or $f1 $f2) (* $c1 $c2)))

(= (Truth_Difference (stv $f1 $c1)
                     (stv $f2 $c2))
   (stv (* $f1 (- 1 $f2)) (* $c1 $c2)))

(= (Truth_DecomposePNN (stv $f1 $c1)
                       (stv $f2 $c2))
   (let $fn (* $f1 (- 1 $f2))
        (stv (- 1 $fn) (* $fn (* $c1 $c2)))))

(= (Truth_DecomposeNPP (stv $f1 $c1)
                       (stv $f2 $c2))
   (let $f (* (- 1 $f1) $f2)
        (stv $f (* $f (* $c1 $c2)))))

(= (Truth_DecomposePNP (stv $f1 $c1)
                       (stv $f2 $c2))
   (let $f (* $f1 (- 1 $f2))
        (stv $f (* $f (* $c1 $c2)))))

(= (Truth_DecomposePPP $v1 $v2)
   (Truth_DecomposeNPP (Truth_Negation $v1) $v2))

(= (Truth_DecomposeNNN (stv $f1 $c1)
                       (stv $f2 $c2))
   (let $fn (* (- 1 $f1) (- 1 $f2))
        (stv (- 1 $fn) (* $fn (* $c1 $c2)))))

(= (Truth_Eternalize (stv $f $c))
   (stv $f (Truth_w2c $c)))

(= (Truth_Revision (stv $f1 $c1)
                   (stv $f2 $c2))
   (let* (($w1 (Truth_c2w $c1))
          ($w2 (Truth_c2w $c2))
          ($w  (+ $w1 $w2))
          ($f (/ (+ (* $w1 $f1) (* $w2 $f2)) $w))
          ($c (Truth_w2c $w)))
          (stv (min 1.00 $f) (min 0.99 (max (max $c $c1) $c2)))))

(= (Truth_Expectation (stv $f $c))
   (+ (* $c (- $f 0.5)) 0.5))

;; INFERENCE RULES

;;NAL-1
;;!Revision
(= (|-nal ($T $T1) ($T $T2)) ($T (Truth_Revision $T1 $T2)))
;;!Syllogistic rules for -->:
(= (|-nal ((--> $a $b) $T1) ((--> $b $c) $T2)) ((--> $a $c) (Truth_Deduction $T1 $T2)))
(= (|-nal ((--> $a $b) $T1) ((--> $a $c) $T2)) ((--> $c $b) (Truth_Induction $T1 $T2)))
(= (|-nal ((--> $a $c) $T1) ((--> $b $c) $T2)) ((--> $b $a) (Truth_Abduction $T1 $T2)))
(= (|-nal ((--> $a $b) $T1) ((--> $b $c) $T2)) ((--> $c $a) (Truth_Exemplification $T1 $T2)))

;;NAL-3
;;!Set decomposition:
(= (|-nal ((--> ({} $A $B) $M) $T)) ((--> ({} $A) $M) (Truth_StructuralDeduction $T)))
(= (|-nal ((--> ({} $A $B) $M) $T)) ((--> ({} $B) $M) (Truth_StructuralDeduction $T)))
(= (|-nal ((--> $M ([] $A $B)) $T)) ((--> $M ([] $A)) (Truth_StructuralDeduction $T)))
(= (|-nal ((--> $M ([] $A $B)) $T)) ((--> $M ([] $B)) (Truth_StructuralDeduction $T)))
;;!Extensional and intensional intersection decomposition:
(= (|-nal ((--> (∪ $S $P) $M) $T)) ((--> $S $M) (Truth_StructuralDeduction $T)))
(= (|-nal ((--> $M (∩ $S $P)) $T)) ((--> $M $S) (Truth_StructuralDeduction $T)))
(= (|-nal ((--> (∪ $S $P) $M) $T)) ((--> $P $M) (Truth_StructuralDeduction $T)))
(= (|-nal ((--> $M (∩ $S $P)) $T)) ((--> $M $P) (Truth_StructuralDeduction $T)))
(= (|-nal ((--> (~ $A $S) $M) $T)) ((--> $A $M) (Truth_StructuralDeduction $T)))
(= (|-nal ((--> $M (− $B $S)) $T)) ((--> $M $B) (Truth_StructuralDeduction $T)))
(= (|-nal ((--> (~ $A $S) $M) $T)) ((--> $S $M) (Truth_StructuralDeductionNegated $T)))
(= (|-nal ((--> $M (− $B $S)) $T)) ((--> $M $S) (Truth_StructuralDeductionNegated $T)))
;;!Extensional and intensional intersection decomposition:
(= (|-nal ((--> $S $M) $T1) ((--> (∪ $S $P) $M) $T2)) ((--> $P $M) (Truth_DecomposePNN $T1 $T2)))
(= (|-nal ((--> $P $M) $T1) ((--> (∪ $S $P) $M) $T2)) ((--> $S $M) (Truth_DecomposePNN $T1 $T2)))
(= (|-nal ((--> $S $M) $T1) ((--> (∩ $S $P) $M) $T2)) ((--> $P $M) (Truth_DecomposeNPP $T1 $T2)))
(= (|-nal ((--> $P $M) $T1) ((--> (∩ $S $P) $M) $T2)) ((--> $S $M) (Truth_DecomposeNPP $T1 $T2)))
(= (|-nal ((--> $S $M) $T1) ((--> (~ $S $P) $M) $T2)) ((--> $P $M) (Truth_DecomposePNP $T1 $T2)))
(= (|-nal ((--> $S $M) $T1) ((--> (~ $P $S) $M) $T2)) ((--> $P $M) (Truth_DecomposeNNN $T1 $T2)))
(= (|-nal ((--> $M $S) $T1) ((--> $M (∩ $S $P)) $T2)) ((--> $M $P) (Truth_DecomposePNN $T1 $T2)))
(= (|-nal ((--> $M $P) $T1) ((--> $M (∩ $S $P)) $T2)) ((--> $M $S) (Truth_DecomposePNN $T1 $T2)))
(= (|-nal ((--> $M $S) $T1) ((--> $M (∪ $S $P)) $T2)) ((--> $M $P) (Truth_DecomposeNPP $T1 $T2)))
(= (|-nal ((--> $M $P) $T1) ((--> $M (∪ $S $P)) $T2)) ((--> $M $S) (Truth_DecomposeNPP $T1 $T2)))
(= (|-nal ((--> $M $S) $T1) ((--> $M (− $S $P)) $T2)) ((--> $M $P) (Truth_DecomposePNP $T1 $T2)))
(= (|-nal ((--> $M $S) $T1) ((--> $M (− $P $S)) $T2)) ((--> $M $P) (Truth_DecomposeNNN $T1 $T2)))

;; NAL-4
;;!Rules for more efficient reasoning about relation components:
(= (|-nal ((--> (× $A $B) $R) $T1) ((--> (× $C $B) $R) $T2)) ((--> $C $A) (Truth_Abduction $T1 $T2)))
(= (|-nal ((--> (× $A $B) $R) $T1) ((--> (× $A $C) $R) $T2)) ((--> $C $B) (Truth_Abduction $T1 $T2)))
(= (|-nal ((--> $R (× $A $B)) $T1) ((--> $R (× $C $B)) $T2)) ((--> $C $A) (Truth_Induction $T1 $T2)))
(= (|-nal ((--> $R (× $A $B)) $T1) ((--> $R (× $A $C)) $T2)) ((--> $C $B) (Truth_Induction $T1 $T2)))
(= (|-nal ((--> (× $A $B) $R) $T1) ((--> $C $A) $T2)) ((--> (× $C $B) $R) (Truth_Deduction $T1 $T2)))
(= (|-nal ((--> (× $A $B) $R) $T1) ((--> $A $C) $T2)) ((--> (× $C $B) $R) (Truth_Induction $T1 $T2)))
(= (|-nal ((--> (× $A $B) $R) $T1) ((--> $C $B) $T2)) ((--> (× $A $C) $R) (Truth_Deduction $T1 $T2)))
(= (|-nal ((--> (× $A $B) $R) $T1) ((--> $B $C) $T2)) ((--> (× $A $C) $R) (Truth_Induction $T1 $T2)))
(= (|-nal ((--> $R (× $A $B)) $T1) ((--> $A $C) $T2)) ((--> $R (× $C $B)) (Truth_Deduction $T1 $T2)))
(= (|-nal ((--> $R (× $A $B)) $T1) ((--> $C $A) $T2)) ((--> $R (× $C $B)) (Truth_Abduction $T1 $T2)))
(= (|-nal ((--> $R (× $A $B)) $T1) ((--> $B $C) $T2)) ((--> $R (× $A $C)) (Truth_Deduction $T1 $T2)))
(= (|-nal ((--> $R (× $A $B)) $T1) ((--> $C $B) $T2)) ((--> $R (× $A $C)) (Truth_Abduction $T1 $T2)))

;;NAL-5
;;Syllogisms:
(= (|-nal ((==> $a $b) $T1) ((==> $b $c) $T2)) ((==> $a $c) (Truth_Deduction $T1 $T2)))
(= (|-nal ((==> $a $b) $T1) ((==> $a $c) $T2)) ((==> $c $b) (Truth_Induction $T1 $T2)))
(= (|-nal ((==> $a $c) $T1) ((==> $b $c) $T2)) ((==> $b $a) (Truth_Abduction $T1 $T2)))
;;!Negation ∧ and ∨ decomposition:
(= (|-nal ((¬ $A) $T)) ($A (Truth_Negation $T)))
(= (|-nal ((∧ $A $B) $T)) ($A (Truth_StructuralDeduction $T)))
(= (|-nal ((∧ $A $B) $T)) ($B (Truth_StructuralDeduction $T)))
(= (|-nal ($S $T1) ((∧ $S $A) $T2)) ($A (Truth_DecomposePNN $T1 $T2)))
(= (|-nal ($S $T1) ((∨ $S $A) $T2)) ($A (Truth_DecomposeNPP $T1 $T2)))
(= (|-nal ($S $T1) ((∧ (¬ $S) $A) $T2)) ($A (Truth_DecomposeNNN $T1 $T2)))
(= (|-nal ($S $T1) ((∨ (¬ $S) $A) $T2)) ($A (Truth_DecomposePPP $T1 $T2)))
;;!Higher-order decomposition
(= (|-nal ($A $T1) ((==> $A $B) $T2)) ($B (Truth_Deduction $T1 $T2)))
(= (|-nal ($A $T1) ((==> (∧ $A $B) $C) $T2)) ((==> $B $C) (Truth_Deduction $T1 $T2)))
(= (|-nal ($B $T1) ((==> $A $B) $T2)) ($A (Truth_Abduction $T1 $T2)))

(= (|- $a $b)
   (unique-atom (collapse (superpose ((|-nal $a $b) (|-nal $b $a))))))
