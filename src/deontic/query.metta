; Non-monotonic query operators over a defeasible theory. Because adding premises
; can RETRACT conclusions, these are not classical-entailment queries: what-if,
; why-not, abduce, requires.
;
; All operators work over the engine state after (dl-run ...); operators that
; need a MODIFIED theory (what-if, requires verification) reload the file and
; inject hypothesis facts via the platform kernel (a clone-and-add-fact step).

; --- positive-status helpers over the current state (pos? lives in types) ---
(= (positive-lits)
   (collapse (let $q (ulit-gen)
     (if (== (pos? $q) True) $q (empty)))))

; goal status in the current state: provable | refuted | unknown
(= (goal-status $goal)
   (if (== (pos? $goal) True)
       provable
       (if (== (pos? (lit-neg $goal)) True)
           refuted
           unknown)))

; =====================================================================
; what-if: assume facts, re-reason, diff against baseline
;   -> (whatif <status> (new <lits...>) (assumed <lits...>))
; =====================================================================
(= (inject-facts $lits)
   (let $_ (map-atom $lits $l (mm_add_fact $l &theory &ground &herb &st)) ()))

(= (dl-what-if $path $hyps $goal)
   (let* (($_b (dl-run $path))
          ($pos0 (positive-lits))
          ($_l (dl-load $path))
          ($_i (inject-facts $hyps))
          ($_r (dl-reason!))
          ($status (goal-status $goal))
          ($new (subtraction-atom (positive-lits) $pos0)))
     (whatif $status (new (sort-atom $new)) (assumed $hyps))))

; =====================================================================
; abduce: one backward step over supporting ground rules
;   -> (abduction <goal> (solutions ((facts...) ...)))
;      empty fact-set as first solution means "already provable"
; =====================================================================
; body literals not already in the proven set (order-preserving)
(= (missing-of $b $pos)
   (filter-atom $b $h (not (== (is-member $h $pos) True))))

(= (abduce-candidates $goal $pos)
   (collapse
     (match &ground (grule $l $k $b $goal)
       (if (== $k defeater)
           (empty)
           (let $miss (missing-of $b $pos)
             (if (== $miss ()) (empty) (sort-atom $miss)))))))

(= (dl-abduce $goal)
   (if (== (pos? $goal) True)
       (abduction $goal (solutions (())))
       (let* (($pos (positive-lits))
              ($cands (unique-atom (abduce-candidates $goal $pos))))
         (if (== $cands ())
             (abduction $goal (solutions (($goal))))
             (abduction $goal (solutions (sort-by-size $cands)))))))

; smallest-first ordering (fewest assumed facts first)
(= (sort-by-size $xs)
   (map-atom (sort-atom (map-atom $xs $x ((size-atom $x) $x))) $p
             (index-atom $p 1)))

; =====================================================================
; requires: verify candidates by injection + re-reasoning
;   -> (requires <goal> already-provable)
;    | (requires <goal> (verified <facts...>))
;    | (requires <goal> none)
; =====================================================================
(= (verify-candidate $path $goal $facts)
   (let* (($_l (dl-load $path))
          ($_i (inject-facts $facts))
          ($_r (dl-reason!)))
     (pos? $goal)))

(= (first-verified $path $goal $cands)
   (if (== $cands ())
       none
       (if (== (verify-candidate $path $goal (car-atom $cands)) True)
           (verified (car-atom $cands))
           (first-verified $path $goal (cdr-atom $cands)))))

(= (dl-requires $path $goal)
   (let* (($_ (dl-run $path))
          ($abd (dl-abduce $goal)))
     (let (abduction $g (solutions $sols)) $abd
       (if (== (car-atom $sols) ())
           (requires $goal already-provable)
           (requires $goal (first-verified $path $goal $sols))))))

; =====================================================================
; why-not: blockers per supporting rule
;   -> (whynot <goal> (would <label>|()) (blockers (...)))
;      blocker: (missing <rule> (<lits>)) | (defeated <rule> <by>)
;             | (contradicted <rule> <by>) | (ambiguity <rule>)
;             | (complement-proven)
; =====================================================================
(= (dl-why-not $goal)
   (if (== (pos? $goal) True)
       (whynot $goal provable)
       (let* (($pos (positive-lits))
              ($supps (collapse (match &ground (grule $l $k $b $goal)
                        (if (== $k defeater) (empty) ($l $b)))))
              ($would (if (== $supps ()) () (car-atom (car-atom $supps))))
              ($blockers (wn-blockers $supps $goal $pos)))
         (if (== $supps ())
             (whynot $goal (would ())
                     (blockers (if (== (is-member (lit-neg $goal) $pos) True)
                                   ((complement-proven))
                                   ())))
             (whynot $goal (would $would) (blockers $blockers))))))

(= (wn-blockers $supps $goal $pos)
   (if (== $supps ()) ()
       (let* ((($l $b) (car-atom $supps))
              ($rest (wn-blockers (cdr-atom $supps) $goal $pos))
              ($miss (missing-of $b $pos)))
         (if (not (== $miss ()))
             (cons-atom (missing $l $miss) $rest)
             (let $atts (wn-attackers $l $goal $pos)
               (if (== $atts ())
                   (cons-atom (ambiguity $l) $rest)
                   (union-atom $atts $rest)))))))

; attackers of <rule $l> for goal: applicable rules for ~goal
; (defeaters block unless the rule is superior; defeasible attackers block
;  unless the rule is strictly superior)
(= (wn-attackers $l $goal $pos)
   (let $nq (lit-neg $goal)
     (collapse
       (match &ground (grule $ls $ks $bs $nq)
         (if (== (missing-of $bs $pos) ())
             (if (== $ks defeater)
                 (if (== (sup? $l $ls) True) (empty) (defeated $l $ls))
                 (if (and (== (sup? $l $ls) True) (== (sup? $ls $l) False))
                     (empty)
                     (contradicted $l $ls)))
             (empty))))))
