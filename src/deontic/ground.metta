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
