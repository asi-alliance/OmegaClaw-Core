; Idiomatic-MeTTa deontic analysis. The SDL bridge that injects grules is
; grounding-adjacent and stays in Prolog (like mm_ground); the ANALYSIS over the
; reasoned conclusions is expressed natively here with pattern-match clauses and
; match/collapse. Verdicts follow deolingo's O^f / O^v / O^u (fulfilled / violated
; / undetermined). Prolog is called only for primitives: literal rendering
; (mm_lit_str) and time comparison (mm_tp_le), plus the thin report formatter.

; --- sign flip; the ideal (fulfilling) and violating proposition of a duty ------
(= (flip-sign pos) neg)
(= (flip-sign neg) pos)

(= (deontic-ideal (lit $s O $t $f $a)) (lit $s none $t $f $a))            ; O p satisfied by p
(= (deontic-ideal (lit $s F $t $f $a)) (lit (flip-sign $s) none $t $f $a)); F p satisfied by ¬p
(= (deontic-viol  (lit $s O $t $f $a)) (lit (flip-sign $s) none $t $f $a)); O p broken by ¬p
(= (deontic-viol  (lit $s F $t $f $a)) (lit $s none $t $f $a))            ; F p broken by p

; --- compliance verdict for one duty against a conclusion set ------------------
(= (compliance-in $d $cs)
   (if (== (is-member (pd (deontic-ideal $d)) $cs) True) complied
   (if (== (is-member (pd (deontic-viol  $d)) $cs) True) violated
       pending)))
(= (compliance-of $d) (compliance-in $d (dl-conclusions)))

; --- the obligations/prohibitions among the +d conclusions --------------------
(= (deontic-mode? O) True)
(= (deontic-mode? F) True)
(= (deontic-mode? $m) False)

(= (obligations-in $cs)
   (collapse (case (superpose $cs)
     (((pd (lit $s $m $t $f $a))
       (if (== (deontic-mode? $m) True) (lit $s $m $t $f $a) (empty)))
      ($_ (empty))))))

; --- compliance report (logic in MeTTa; Prolog formats pre-rendered lines) -----
(= (verdict-of $d $cs) (let $ls (mm_lit_str $d) ($ls (compliance-in $d $cs))))
(= (deontic-compliance $path)
   (let* (($cs (dl-run $path))
          ($obls (sort-atom (obligations-in $cs))))
     (mm_print_verdicts "Deontic Compliance" (map-atom $obls $d (verdict-of $d $cs)))))

; --- deontic dilemmas: O p and O ¬p both applicable, neither resolved ----------
; an obligation is "applicable" iff some strict/defeasible grule derives it with
; an all-+d body (it fired) — checked declaratively with match over &ground.
(= (oblig-applicable $d)
   (not (== () (collapse (match &ground (grule $l $k $b $d)
                 (if (and (== (sd-kind? $k) True) (== (body-all-pd $b) True)) $l (empty)))))))

(= (dilemma? $d $cs)
   (and (== (oblig-applicable (lit-neg $d)) True)
   (and (== (is-member (pd $d) $cs) False)
        (== (is-member (pd (lit-neg $d)) $cs) False))))

; candidate obligations are the APPLICABLE positive ones (those whose rule fired)
; — the dilemma duties are defeated, so they are NOT among the +d conclusions.
(= (applicable-pos-obligations)
   (collapse (match &ground (grule $l $k $b (lit pos O $t $f $a))
     (if (and (== (sd-kind? $k) True) (== (body-all-pd $b) True)) (lit pos O $t $f $a) (empty)))))

(= (dilemmas-in $cs)
   (filter-atom (applicable-pos-obligations) $d (== (dilemma? $d $cs) True)))

(= (deontic-dilemmas $path)
   (let $cs (dl-run-deontic $path) (unique-atom (dilemmas-in $cs))))
(= (deontic-dilemmas-report $path)
   (let $cs (dl-run-deontic $path)
     (mm_print_dilemmas2 (unique-atom (dilemmas-in $cs)))))

; --- temporal-deontic deadline compliance (Governatori et al. 2007) -----------
; A deadline obligation has a window [St,En] and a type: ACHIEVEMENT (target must
; occur >=once by the deadline) or MAINTENANCE (target must not occur in the
; window). Evaluated at reference time `now`; occurrence is bounded by now (a
; future event isn't a breach yet). Metadata lives in &st as deadlineinfo.

; occurrence times of the target proposition among the +d conclusions
(= (dl-occ-times $sgn $f $a $cs)
   (collapse (case (superpose $cs)
     (((pd (lit $sgn none (iv $t $te) $f $a)) $t)
      ((pd (lit $sgn none none $f $a)) untimed)
      ($_ (empty))))))

(= (dl-in-window $t $st $en $now)
   (if (== $t untimed) True
       (and (== (tp<= $st $t) True) (and (== (tp<= $t $en) True) (== (tp<= $t $now) True)))))
(= (dl-occurred? $times $st $en $now)
   (if (== $times ()) False
       (let $t (car-atom $times)
         (if (== (dl-in-window $t $st $en $now) True) True
             (dl-occurred? (cdr-atom $times) $st $en $now)))))

; verdict per type (pattern-matched): achievement vs maintenance
(= (dl-verdict achieve $occurred $en $now)
   (if (== $occurred True) fulfilled (if (== (tp<= $now $en) True) pending violated)))
(= (dl-verdict maintain $occurred $en $now)
   (if (== $occurred True) violated (if (== (tp<= $now $en) True) pending fulfilled)))

(= (dl-verdict-of $sgn $f $a $type $st $en $now $cs)
   (dl-verdict $type (dl-occurred? (dl-occ-times $sgn $f $a $cs) $st $en $now) $en $now))

(= (deadline-status $path $now $functor)
   (let $cs (dl-run $path)
     (case (once (match &st (deadlineinfo $sgn $mode $functor $a $type $st $en $sanc)
                   ($sgn $a $type $st $en)))
       ((($sgn $a $type $st $en)
         (dl-verdict-of $sgn $functor $a $type $st $en $now $cs))
        (Empty none)))))

; deadline report: MeTTa builds rows (lit-with-window str, type, status, sanction);
; Prolog formats. Window carried in the literal so mm_lit_str renders [O]pay[0,30].
(= (deadline-rows $cs $now)
   (collapse (match &st (deadlineinfo $sgn $mode $f $a $type $st $en $sanc)
     ((mm_lit_str (lit $sgn $mode (iv $st $en) $f $a))
      $type
      (dl-verdict-of $sgn $f $a $type $st $en $now $cs)
      $sanc))))
(= (deontic-deadlines $path $now)
   (let $cs (dl-run $path) (mm_print_deadlines2 $now (deadline-rows $cs $now))))
