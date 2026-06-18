(given (pair a 10 3))
(normally r1 (and (pair ?n ?x ?y) (bind ?q (div ?x ?y))) (quot ?n ?q))
(normally r2 (and (pair ?n ?x ?y) (bind ?r (rem ?x ?y))) (rema ?n ?r))
