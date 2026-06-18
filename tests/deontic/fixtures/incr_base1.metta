;; Incremental-grounding base: transitive readiness over a dep chain.
(normally r1 (and (dep ?a ?b) (ready ?b)) (ready ?a))
(given (ready base0))
(given (dep n1 base0))
;; delta 1: extend the chain (propagates ready through existing rule r1)
(given (dep n2 n1))
