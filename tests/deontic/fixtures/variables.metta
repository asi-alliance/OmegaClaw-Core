(given (parent alice bob))
(given (parent bob carol))
(always r1 (parent ?x ?y) (ancestor ?x ?y))
(normally r2 (and (parent ?x ?y) (ancestor ?y ?z)) (ancestor ?x ?z))
