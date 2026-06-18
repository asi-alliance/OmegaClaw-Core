;; Obligation never discharged: invoice at 5, no payment -> in force [5, inf).
(happens invoice 5)
(initiates invoice (must pay))
(terminates pay (must pay))
