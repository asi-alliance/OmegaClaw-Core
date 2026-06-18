; Semantic literal matching via faiss_ffi (FAISS k-NN over Structural Random
; Indexing). SRI gives similarity-preserving embeddings with NO external model:
; literals are terms, so they embed by STRUCTURE — same functor and shared
; arguments yield nearby vectors. Opt-in module (requires faiss_ffi present in
; the PeTTa tree, built by its build.sh).
;
; Use: fuzzy retrieval over a reasoned state — "which concluded facts are most
; like this one?" — e.g. to surface similar tasks/plans, or to align two
; knowledge bases by structural similarity before fusing their evidence.

!(import! &self (library OmegaClaw-Core lib_deontic))
!(import! &self (library faiss_ffi lib_faiss))

; Index every positively-concluded literal into a fresh SRI vector space.
; Literals are terms, so add-atom-SRI embeds them by structure: same functor
; and similar args => nearby vectors.
(= (sem-index $space $dim)
   (let* (($_1 (new-atom-vectorspace $space $dim))
          ($lits (positive-lits)))
     (sem-add-list $space $lits)))

(= (sem-add-list $space $ls)
   (let $_ (map-atom $ls $x (add-atom-SRI $space $x)) ()))

; k most similar indexed literals to a query literal (k-NN by SRI embedding).
(= (sem-match $k $space $query) (match-SRI $k $space $query))

; the single nearest indexed literal to a query.
(= (sem-nearest $space $query) (atom-of (match-SRI 1 $space $query)))

; Index an explicit list of atoms (e.g. task names, plan facts) for ad-hoc
; semantic retrieval independent of the reasoner.
(= (sem-index-atoms $space $dim $atoms)
   (let* (($_1 (new-atom-vectorspace $space $dim))
          ($_2 (sem-add-list $space $atoms)))
     ()))
