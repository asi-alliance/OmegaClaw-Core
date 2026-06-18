;; Temporal-deontic deadlines (Governatori et al. 2007), a temporal-deontic extension.
;; Achievement: pay by 30 (sanction: fine). Maintenance: no trespass in [0,100].
(deadline (must pay) achieve 0 30 fine)
(deadline (forbidden trespass) maintain 0 100 penalty)
(given (during pay 25 25))
