(given (val a 2))
(given (threshold 2.0))
(normally r1 (and (val ?x ?v) (threshold ?t) (>= ?v ?t)) (passes ?x))
