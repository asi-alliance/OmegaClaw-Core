;; CTD: O(¬litter ⊗ pay_fine ⊗ apologize). Person littered (primary violated)
;; -> reparation O pay_fine activates. Fine unpaid -> apologize not yet due.
(given person)
(given litter)
(normally r1 person (otherwise (forbidden litter) (must pay_fine) (must apologize)))
