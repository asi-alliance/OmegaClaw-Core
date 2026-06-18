;; A sample agent policy, written as a defeasible deontic theory.
;; While a request is unconfirmed: deleting is forbidden, and replying is
;; obligatory. Superiority/contrary-to-duty rules would refine this.
(given unconfirmed)
(normally pr1 unconfirmed (forbidden delete))
(normally pr2 unconfirmed (must reply))
