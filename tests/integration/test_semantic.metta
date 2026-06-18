!(import! &self (library OmegaClaw-Core src/integration/semantic))
; Semantic literal matching via faiss_ffi (FAISS + Structural Random Indexing).
; OPTIONAL: requires faiss_ffi in the PeTTa tree. SRI embeds literals by
; structure, so a query shares the most symbols with same-functor facts.


; deterministic SRI embeddings (the random vectors are otherwise per-process,
; making the nearest-neighbour assertions occasionally flip)
!(mm_srand 42)

; reason over a tiny zoo, index the concluded facts
!(dl-run (dl-path tests/deontic/fixtures/animals.metta))
!(sem-index &zoo 32)

; the nearest concluded literal to (bird woody) is a bird fact (shared functor
; + the lit/pos/none structural symbols dominate the SRI embedding)
!(test (let (lit $s $m $t $f $a) (sem-nearest &zoo (lit pos none none bird (woody)))
         $f)
       bird)

; nearest to (fish dory) is the fish fact
!(test (sem-nearest &zoo (lit pos none none fish (dory)))
       (lit pos none none fish (nemo)))

; k=2 nearest to (bird robin) both exist and the top hit is a bird
!(test (let $hits (sem-match 2 &zoo (lit pos none none bird (robin)))
         (let (lit $s $m $t $f $a) (atom-of $hits) $f))
       bird)

; ad-hoc semantic index: SRI similarity is STRUCTURAL (shared sub-symbols),
; not lexical-substring, so names are indexed as structured terms. A query
; sharing the most sub-symbols wins: (task auth api) is nearest (task auth ...).
!(sem-index-atoms &tasks 32
   ((task auth service) (task auth gateway) (task billing) (task models)))
!(test (let (task $a $b) (sem-nearest &tasks (task auth api)) $a)
       auth)

!(println! test-semantic-done)
