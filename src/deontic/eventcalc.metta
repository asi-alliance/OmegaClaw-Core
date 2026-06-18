; Event-Calculus obligation lifecycle in idiomatic MeTTa (RTEC/oPIEC style).
; Obligations are inertial fluents: initiated by an event, persisting until a
; terminating event. Maximal validity intervals are computed by one-pass
; amalgamation over the sorted event time-points (O(n log n), not per-time-point).
; Prolog is used only for the inf-aware time comparison primitive (mm_tp_le) and
; literal rendering (mm_lit_str); the algorithm itself is native MeTTa recursion.

; (tp<= / tp< — inf-aware time order — are shared helpers in types.metta)

; sorted initiation / termination time-points of a fluent
(= (ec-inits $f)
   (sort-atom (collapse (match &theory (ec_init $e $f) (match &theory (happens $e $t) $t)))))
(= (ec-terms $f)
   (sort-atom (collapse (match &theory (ec_term $e $f) (match &theory (happens $e $t) $t)))))

; earliest termination strictly after $s, else inf
(= (first-after $terms $s)
   (if (== $terms ()) inf
       (let $t (car-atom $terms)
         (if (== (tp< $s $t) True) $t (first-after (cdr-atom $terms) $s)))))

; drop leading initiations strictly below $e (re-inits inside an open period)
(= (drop-below $inits $e)
   (if (== $inits ()) ()
       (let $i (car-atom $inits)
         (if (== (tp< $i $e) True) (drop-below (cdr-atom $inits) $e) $inits))))

; amalgamate sorted inits + terms into maximal [S,E) intervals (E = inf if open)
(= (amalg $inits $terms)
   (if (== $inits ()) ()
       (let* (($s (car-atom $inits))
              ($e (first-after $terms $s))
              ($rest (drop-below (cdr-atom $inits) $e)))
         (cons-atom ($s $e) (amalg $rest $terms)))))

(= (fluent-intervals $f) (amalg (ec-inits $f) (ec-terms $f)))

; T lies in some in-force interval [S,E)
(= (in-some-interval $ints $t)
   (if (== $ints ()) False
       (let ($s $e) (car-atom $ints)
         (if (and (== (tp<= $s $t) True) (== (tp< $t $e) True))
             True
             (in-some-interval (cdr-atom $ints) $t)))))

; --- public queries (fluent given as a deontic s-expr, e.g. (must pay)) --------
(= (ec-intervals $path $m)
   (let* (($_ (dl-load $path)) ($f (mm_dlit $m))) (fluent-intervals $f)))
(= (ec-holds-at $path $m $t)
   (let* (($_ (dl-load $path)) ($f (mm_dlit $m)))
     (in-some-interval (fluent-intervals $f) $t)))
; a violation = the obligation is still in force at its deadline
(= (ec-violated-at $path $m $d) (ec-holds-at $path $m $d))

; --- timeline: MeTTa builds structured rows; Prolog formats the table ----------
; row = (LitString IntervalsList StatusSymbol); Prolog renders intervals + status.
(= (ec-fluents) (unique-atom (collapse (match &theory (ec_init $e $f) $f))))
(= (timeline-row $f $now)
   (let* (($ints (fluent-intervals $f))
          ($held (in-some-interval $ints $now)))
     ((mm_lit_str $f) $ints (if (== $held True) active inactive))))
(= (ec-timeline $path $now)
   (let $_ (dl-load $path)
     (mm_print_timeline2 $now (map-atom (ec-fluents) $f (timeline-row $f $now)))))
