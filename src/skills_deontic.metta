; Agent-facing wrappers over lib_deontic, callable as skills during the loop.
!(import! &self (library OmegaClaw-Core lib_deontic))

; Defeasible conclusions of a theory file (tags +D/-D definite, +d/-d defeasible).
(= (deontic-conclude $path) (dl-run $path))

; Conclusions under the Standard Deontic Logic closure (O/P/F; F p = O not p).
(= (deontic-norms $path) (dl-run-deontic $path))

; Unresolved deontic dilemmas: O p and O not-p both applicable, neither defeated.
(= (deontic-conflicts $path) (deontic-dilemmas $path))
