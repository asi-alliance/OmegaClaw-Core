; Grounding: instantiate variable rules over the Herbrand base by Datalog-style
; conjunctive matching, so the propositional DL(d) engine only sees ground rules.
;
; Var rules live in &theory with real Prolog variables (the platform loader
; converted ?x). Retrieving a rule atom from the space yields a fresh copy,
; so matching its body literals against the herbrand space (&herb) performs
; the substitution natively; arithmetic constraints are evaluated inline and
; dropped from the instantiated body, leaving logic-only ground instances.
;
; The herbrand space grows with every new ground head (bottom-up fixpoint
; over derivable atoms), and every new instance registers its literals in
; the reporting universe.

; Instantiate one body: nondeterministic over substitutions.
(= (ground-body $b)
   (if (== $b ())
       ()
       (let ($x $rest) (decons-atom $b)
         (gb-item $x $rest))))

; Logic literal: match against herbrand atoms (same sign/mode/functor/args),
; binding any variables. Temporal uses a base-family wildcard:
;   - body temporal `none` matches ANY temporal variant of the atom; the ground
;     body literal carries the herbrand atom's actual temporal ($ht), so the
;     reasoner's status lookups align with the concrete fact.
;   - body temporal `(iv ?s ?e)` unifies with the herbrand interval, BINDING the
;     endpoint vars natively — those bindings flow to later Allen constraints.
(= (gb-item (lit $s $m none $f $a) $rest)
   (match &herb (ha (lit $s $m $ht $f $a))
     (cons-atom (lit $s $m $ht $f $a) (ground-body $rest))))
(= (gb-item (lit $s $m (iv $ts $te) $f $a) $rest)
   (match &herb (ha (lit $s $m (iv $ts $te) $f $a))
     (cons-atom (lit $s $m (iv $ts $te) $f $a) (ground-body $rest))))

(= (gb-item (acmp $op $l $r) $rest)
   (if (== (mm_acmp $op $l $r) true)
       (ground-body $rest)
       (empty)))

(= (gb-item (tcmp $op $l $r) $rest)
   (if (== (mm_tcmp $op $l $r) true)
       (ground-body $rest)
       (empty)))

(= (gb-item (abind $v $ax) $rest)
   (let $v (mm_arith_eval $ax)
     (ground-body $rest)))

; Add a ground instance if new; feeds the herbrand base and the universe.
(= (grule-add $l $k $b $h)
   (if (== () (collapse (match &ground (grule $l $k $b $h) yes)))
       (let* (($_1 (add-atom &ground (grule $l $k $b $h)))
              ($_2 (herb-add $h))
              ($_3 (ulit-add $h))
              ($_4 (ulits-add $b)))
         1)
       0))

(= (herb-add $h)
   (if (== () (collapse (match &herb (ha $h) yes)))
       (let $_ (add-atom &herb (ha $h)) ())
       ()))

; One pass: try to instantiate every theory rule against the current herbrand
; base; returns the number of NEW ground instances added.
(= (ground-instances)
   (match &theory (rule $l $k $b $h)
     (let $gb (ground-body $b)
       (if (== (is-ground ($gb $h)) true)
           (grule-add $l $k $gb $h)
           (empty)))))

(= (ground-pass) (foldall + (ground-instances) 0))

(= (ground!) (if (> (ground-pass) 0) (ground!) ()))

; =====================================================================
; Semi-naive grounding (the fast path). Instead of re-joining every rule against
; the whole herbrand base on each pass, join one body literal against the FRONTIER
; (&herb_new = heads added last round) and the rest against the full base. A rule
; can only yield a NEW instance if a body atom is new, so stable instances are
; never re-derived — same ground set as ground!, far fewer derivation attempts.
;
; Perf (measured): this is the native engine's grounder. It produces the IDENTICAL
; ground set as the Prolog kernel (grounding.pl) but runs ~4-5x slower on
; grounding-heavy theories (≈3000 instances: ~1.5s native vs ~0.3s prolog). The
; gap is per-operation MeTTa-eval overhead — each derived instance is ~6
; match/check/add round-trips — not the algorithm. Semi-naive (here) cuts the
; number of derivation attempts; functor-keying the herbrand base to index the
; join was also measured and was SLOWER (keying overhead, no scan win). Neither
; shrinks the per-op constant, so prolog stays the default for variable-rule-heavy
; theories; native grounding is for propositional plans (grounding is trivial)
; and inspection.
; =====================================================================

; gb-sn: ground bodies of $b that use >=1 frontier literal — the pivot matches
; &herb_new, the others match the base. Constraints evaluate and drop (logic-only
; output, as in ground-body). Superpose over pivot position. Output is stored
; reversed: order is irrelevant to the reasoner (body-all-pd folds over it) and
; processing stays left-to-right so interval/arith bindings still flow in order.
(= (gb-sn $b) (gb-scan () $b))

; a body item is a logic literal (matches atoms) vs a constraint (evaluated).
(= (is-logic-lit (lit $s $m $t $f $a)) True)
(= (is-logic-lit (acmp $o $l $r)) False)
(= (is-logic-lit (tcmp $o $l $r)) False)
(= (is-logic-lit (abind $v $x)) False)
; does the remaining body still hold a logic literal (a later pivot slot)?
(= (has-logic-lit $b)
   (if (== $b ()) False
       (let ($x $rest) (decons-atom $b)
         (if (== (is-logic-lit $x) True) True (has-logic-lit $rest)))))

; pre-pivot: each logic literal may BE the pivot (frontier) or ground on the base
; while scanning continues to its right; constraints evaluate and drop.
(= (gb-scan $acc $rem)
   (if (== $rem ())
       (empty)
       (let ($x $rest) (decons-atom $rem)
         (gb-scan-item $x $acc $rest))))
; the LAST logic literal can only be the pivot (matching the base here would just
; re-derive a delta-free, already-known instance) — so single-literal rules join
; the small frontier directly, never the full base.
(= (gb-scan-item (lit $s $m $tv $f $a) $acc $rest)
   (if (== (has-logic-lit $rest) True)
       (superpose ((gb-pivot (lit $s $m $tv $f $a) $acc $rest)
                   (gb-base  (lit $s $m $tv $f $a) $acc $rest)))
       (gb-pivot (lit $s $m $tv $f $a) $acc $rest)))
(= (gb-scan-item (acmp $op $l $r) $acc $rest)
   (if (== (mm_acmp $op $l $r) true) (gb-scan $acc $rest) (empty)))
(= (gb-scan-item (tcmp $op $l $r) $acc $rest)
   (if (== (mm_tcmp $op $l $r) true) (gb-scan $acc $rest) (empty)))
(= (gb-scan-item (abind $v $ax) $acc $rest)
   (let $v (mm_arith_eval $ax) (gb-scan $acc $rest)))

; pivot: match the literal on the frontier, then ground the suffix on the base.
(= (gb-pivot (lit $s $m none $f $a) $acc $rest)
   (match &herb_new (ha (lit $s $m $ht $f $a))
     (gb-suffix (cons-atom (lit $s $m $ht $f $a) $acc) $rest)))
(= (gb-pivot (lit $s $m (iv $ts $te) $f $a) $acc $rest)
   (match &herb_new (ha (lit $s $m (iv $ts $te) $f $a))
     (gb-suffix (cons-atom (lit $s $m (iv $ts $te) $f $a) $acc) $rest)))

; pre-pivot base match: keep seeking the pivot to the right.
(= (gb-base (lit $s $m none $f $a) $acc $rest)
   (match &herb (ha (lit $s $m $ht $f $a))
     (gb-scan (cons-atom (lit $s $m $ht $f $a) $acc) $rest)))
(= (gb-base (lit $s $m (iv $ts $te) $f $a) $acc $rest)
   (match &herb (ha (lit $s $m (iv $ts $te) $f $a))
     (gb-scan (cons-atom (lit $s $m (iv $ts $te) $f $a) $acc) $rest)))

; suffix: pivot already taken; ground remaining items on the base only.
(= (gb-suffix $acc $rem)
   (if (== $rem ())
       $acc
       (let ($x $rest) (decons-atom $rem)
         (gb-suffix-item $x $acc $rest))))
(= (gb-suffix-item (lit $s $m none $f $a) $acc $rest)
   (match &herb (ha (lit $s $m $ht $f $a))
     (gb-suffix (cons-atom (lit $s $m $ht $f $a) $acc) $rest)))
(= (gb-suffix-item (lit $s $m (iv $ts $te) $f $a) $acc $rest)
   (match &herb (ha (lit $s $m (iv $ts $te) $f $a))
     (gb-suffix (cons-atom (lit $s $m (iv $ts $te) $f $a) $acc) $rest)))
(= (gb-suffix-item (acmp $op $l $r) $acc $rest)
   (if (== (mm_acmp $op $l $r) true) (gb-suffix $acc $rest) (empty)))
(= (gb-suffix-item (tcmp $op $l $r) $acc $rest)
   (if (== (mm_tcmp $op $l $r) true) (gb-suffix $acc $rest) (empty)))
(= (gb-suffix-item (abind $v $ax) $acc $rest)
   (let $v (mm_arith_eval $ax) (gb-suffix $acc $rest)))

; add a new instance; a new head feeds both the base and the NEXT frontier.
(= (grule-add-sn $l $k $b $h)
   (if (== () (collapse (match &ground (grule $l $k $b $h) yes)))
       (let* (($_1 (add-atom &ground (grule $l $k $b $h)))
              ($_2 (herb-add-sn $h))
              ($_3 (ulit-add $h))
              ($_4 (ulits-add $b)))
         1)
       0))
(= (herb-add-sn $h)
   (if (== () (collapse (match &herb (ha $h) yes)))
       (let* (($_1 (add-atom &herb (ha $h)))
              ($_2 (add-atom &herb_next (ha $h))))
         ())
       ()))

; one round: instantiate every rule against the current frontier.
(= (ground-sn-instances)
   (match &theory (rule $l $k $b $h)
     (let $gb (gb-sn $b)
       (if (== (is-ground ($gb $h)) true)
           (grule-add-sn $l $k $gb $h)
           (empty)))))

; copy a (ha ...) space into the frontier &herb_new (clearing it first).
(= (frontier-load $from)
   (let* (($_c (mm_clear_space &herb_new))
          ($_m (collapse (match $from (ha $h) (add-atom &herb_new (ha $h))))))
     ()))

(= (ground-sn-round)
   (let* (($_clr (mm_clear_space &herb_next))
          ($n    (foldall + (ground-sn-instances) 0))
          ($_swp (frontier-load &herb_next)))
     $n))

(= (ground-sn-loop!)
   (let $n (ground-sn-round) (if (> $n 0) (ground-sn-loop!) ())))

; entry: seed the frontier with the whole initial base, iterate to fixpoint.
(= (ground-sn!)
   (let* (($_1 (frontier-load &herb))
          ($_2 (ground-sn-loop!)))
     ()))
