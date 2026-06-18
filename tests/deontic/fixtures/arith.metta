(given (salary alice 120000))
(given (salary bob 85000))
(normally r1 (and (salary ?e ?s) (> ?s 100000)) (high-earner ?e))
(normally r2 (and (salary ?e ?s) (bind ?d (* ?s 2))) (double-pay ?e ?d))
