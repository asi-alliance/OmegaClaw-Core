(given (during (ev a) 10 20))
(given (during (ev b) 25 35))
(normally r1 (and (during (ev a) ?T) (during (ev b) ?S) (before ?T ?S)) seq-ab)
