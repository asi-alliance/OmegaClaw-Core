; Core datatypes of a defeasible theory (Nute; Antoniou et al. 2001), reified
; as atoms in PeTTa spaces so rule instantiation is native unification.
;
; Literal:  (lit <sign> <mode> <temporal> <functor> <args>)   — 6-slot functor
;           sign: pos|neg   mode: none|O|P|F   temporal: none|(iv <s> <e>)
;           Carrying mode+temporal in the functor makes temporal/modal atom
;           identity automatic: two lits differing in any slot are distinct
;           atoms in the space, and grounding endpoint-binding falls out of
;           native unification.
; Rule:     (rule <label> <kind> <body> <head>)     in &theory (may hold vars)
;           (grule <label> <kind> <body> <head>)    in &ground (ground, logic-only body)
;           kind: fact | strict | defeasible | defeater
; Body item: (lit ...) | (acmp <op> <ax> <ax>) | (tcmp <op> <tp> <tp>) | (abind <var> <ax>)
; Superiority: (sup <winner> <loser>)               in &theory
; Statuses (in &st): (ulit <lit>) (defp <lit>) (dft <lit> true|false)

; Classical complement: ~p flips the sign slot,
; preserving mode and temporal slots.
(= (lit-neg (lit pos $m $t $f $a)) (lit neg $m $t $f $a))
(= (lit-neg (lit neg $m $t $f $a)) (lit pos $m $t $f $a))

; Rule-kind groups: which kinds license definite vs defeasible derivation.
(= (def-kind? fact) True)
(= (def-kind? strict) True)
(= (def-kind? defeasible) False)
(= (def-kind? defeater) False)

(= (sd-kind? fact) True)
(= (sd-kind? strict) True)
(= (sd-kind? defeasible) True)
(= (sd-kind? defeater) False)

; --- status accessors (absence = unknown / not proven) ---
(= (defp? $l)
   (case (once (match &st (defp $l) yes))
     ((yes True) (Empty False))))

(= (dft-of $l)
   (case (once (match &st (dft $l $v) $v))
     (($v $v) (Empty unknown))))

(= (set-dft $l $v)
   (let $_ (add-atom &st (dft $l $v)) 1))

(= (set-defp $l)
   (let $_ (add-atom &st (defp $l)) 1))

; Positive (provable at either level) — foundational status predicate used by
; explain/query/trust.
(= (pos? $l)
   (or (== (defp? $l) True) (== (dft-of $l) true)))

; --- body satisfaction (rule applicability, recomputed declaratively) ---
; Phase 1 level: all body literals definitely proven.
(= (body-all-defp $b)
   (if (== $b ()) True
       (if (== (defp? (car-atom $b)) True)
           (body-all-defp (cdr-atom $b))
           False)))

; Phase 2 level: applicable = every body literal +d (remaining == 0).
(= (body-all-pd $b)
   (if (== $b ()) True
       (if (== (dft-of (car-atom $b)) true)
           (body-all-pd (cdr-atom $b))
           False)))

; Phase 2 level: discarded = some body literal -d.
(= (body-some-nd $b)
   (if (== $b ()) False
       (if (== (dft-of (car-atom $b)) false)
           True
           (body-some-nd (cdr-atom $b)))))

; --- superiority (is one rule label ranked above another) ---
(= (sup? $w $l)
   (case (once (match &theory (sup $w $l) yes))
     ((yes True) (Empty False))))

; Generator over the reporting universe (every literal occurring in the
; ground theory; complements only if they occur themselves).
(= (ulit-gen) (match &st (ulit $l) $l))

(= (ulit-add $l)
   (if (== () (collapse (match &st (ulit $l) yes)))
       (let $_ (add-atom &st (ulit $l)) ())
       ()))
(= (ulits-add $ls)
   (if (== $ls ()) ()
       (let* (($_1 (ulit-add (car-atom $ls)))
              ($_2 (ulits-add (cdr-atom $ls))))
         ())))

; --- inf-aware time-point order (shared by temporal-deontic + Event Calculus) ---
; `inf` is the open/persistent end; mm_tp_le (io.pl) compares finite points.
(= (tp<= $a $b) (if (== $b inf) True (== (mm_tp_le $a $b) true)))
(= (tp<  $a $b)
   (if (== $b inf) (not (== $a inf))
       (if (== $a inf) False
           (and (== (mm_tp_le $a $b) true) (== (mm_tp_le $b $a) false)))))
