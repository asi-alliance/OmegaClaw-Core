; Plan-inspection commands beyond the core surface:
;   trace     full reasoning trace (facts/rules/superiorities/conclusions)
;   validate  plan structure validation (undefined/unreachable/consistency)
;   assign    agent assignment listing
;
; The renderers live in the plan-inspection kernel (platform/inspect.pl) and emit
; a deterministic, stable-sorted output. Commands that need an LLM, OS process
; control, networking, a crypto identity, or an interactive terminal are out of
; scope for a pure-logic engine; the stub reports that honestly so every command
; name has a defined response.

; --- trace ---
(= (directive-trace $path)
   (let $cs (dl-run $path)
     (mm_print_trace &theory $cs)))

; --- validate (default non-strict) ---
(= (directive-validate $path $strict)
   (let* (($cs (dl-run $path))
          ($fmt (mm_plan_fmt $path)))
     (mm_print_plan_validate &theory $cs $fmt $strict)))

; --- analyze: dependency cycles (deadlocks) + self-inconsistency -------------
; The cycle ALGORITHM is native MeTTa (support-graph transitive closure +
; mutual-reachability SCCs); Prolog only renders the report and supplies the
; consistency lines (mn_consistency, the same lines `validate` emits).

; support edges (From To): each body literal of a non-defeater grule -> its head
; (defeaters block rather than support, so they add no dependency).
(= (dep-edges)
   (unique-atom (collapse
     (match &ground (grule $l $k $body $to)
       (if (== (sd-kind? $k) True)
           (let $from (superpose $body) ($from $to))
           (empty))))))

; transitive closure of the edge relation by naive fixpoint (small plan graphs):
; rel := rel ∪ {(a,d) | (a,b)∈rel, (b,d)∈edges} until it stops growing.
(= (tc-step $es $rel)
   (unique-atom (union-atom $rel
     (collapse (let* ((($a $b) (superpose $rel)) (($c $d) (superpose $es)))
                 (if (== $b $c) ($a $d) (empty)))))))
(= (tc-fix $es $rel)
   (let $next (tc-step $es $rel)
     (if (== (size-atom $next) (size-atom $rel)) $rel (tc-fix $es $next))))
(= (reach-rel) (let $es (dep-edges) (tc-fix $es $es)))

; a literal is cyclic iff it reaches itself; group cyclic literals into SCCs by
; mutual reachability (each group is a deadlock set).
(= (cyclic-nodes)
   (let $rel (reach-rel)
     (unique-atom (collapse (let ($a $b) (superpose $rel)
                              (if (== $a $b) $a (empty)))))))
(= (scc-of $a $cyc $rel)
   (sort-atom (filter-atom $cyc $b
     (and (== (is-member ($a $b) $rel) True) (== (is-member ($b $a) $rel) True)))))
(= (plan-cycle-groups)
   (let* (($rel (reach-rel)) ($cyc (cyclic-nodes)))
     (sort-atom (unique-atom (map-atom $cyc $a (scc-of $a $cyc $rel))))))

; --- self-consistency: no circular superiority, no contradictory +D pair ------
; (the report LINES come from Prolog mn_consistency so `validate` and `analyze`
;  share one renderer; this is the queryable boolean.)
(= (sup-pairs) (collapse (match &theory (sup $a $b) ($a $b))))
(= (circular-sup?)
   (let $ps (sup-pairs)
     (not (== () (collapse (let ($a $b) (superpose $ps)
       (if (and (== (is-member ($b $a) $ps) True) (not (== $a $b))) found (empty))))))))

; functor names that are definite (+D) with the given sign
(= (def-funcs $sgn $cs)
   (collapse (case (superpose $cs)
     (((pD (lit $sgn $m $t $f $a)) $f) ($_ (empty))))))
(= (contradiction? $cs)
   (let* (($poss (def-funcs pos $cs)) ($negs (def-funcs neg $cs)))
     (not (== () (collapse (let $f (superpose $poss)
       (if (== (is-member $f $negs) True) found (empty))))))))

(= (plan-consistent-cs? $cs)
   (and (not (== (circular-sup?) True)) (not (== (contradiction? $cs) True))))

; --- public queries + report --------------------------------------------------
(= (directive-analyze $path)
   (let* (($cs (dl-run $path)) ($groups (plan-cycle-groups)))
     (mm_print_analyze2 $groups &theory $cs)))
(= (plan-cycles $path) (let $_ (dl-run $path) (plan-cycle-groups)))
(= (plan-consistent? $path) (let $cs (dl-run $path) (plan-consistent-cs? $cs)))

; --- assign (optionally filtered by agent) ---
(= (assigns-active $names)
   (filter-atom (directive-assignments $names) $a
     (let (assign $t $ag $l) $a
       (== (is-member $t (directive-completed $names)) False))))

(= (assign-names $names $agent)
   (let $active (if (== $agent "")
                    (assigns-active $names)
                    (filter-atom (assigns-active $names) $a
                      (let (assign $t $ag $l) $a (== $ag $agent))))
     (sort-atom (map-atom $active $a (let (assign $t $ag $l) $a $l)))))

(= (directive-assign $path $agent)
   (let* (($_ (dl-run $path))
          ($names (directive-pos-names))
          ($ns (assign-names $names $agent)))
     (mm_print_assign $agent $ns)))

; --- honest stub for commands needing external services ---
(= (directive-stub $cmd $needs) (mm_print_stub $cmd $needs))
