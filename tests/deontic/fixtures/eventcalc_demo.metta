;; Event-Calculus obligation lifecycle (oPIEC/RTEC-style), a temporal extension.
;; Invoice at t=5 initiates "must pay"; pay at t=25 terminates it.
(happens invoice 5)
(happens pay 25)
(initiates invoice (must pay))
(terminates pay (must pay))
