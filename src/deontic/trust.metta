; Trust-weighted defeasible reasoning (weakest link over the proof tree).
;
; Trust is the WEAKEST LINK along the derivation:
; the trust of a conclusion is the minimum trust over its proof tree, where
;   - a claimed fact leaf has its source's trust  (trusts S V);
;   - a rule node has the rule's trust, which has no MeTTa surface syntax and so
;     defaults to 0.0, so any rule-derived literal carries trust 0.00 unless
;     every step in its derivation is a trusted fact.
; Source attribution is the union of the claiming sources across the tree.
;
; Reuses the proof tree from explain.metta, so trust = a fold over (explain lit).

; --- source / trust lookups (populated by the platform ingester into &st) ---
(= (source-trust-val $s)
   (case (once (match &st (trustval $s $v) $v))
     (($v $v) (Empty 0.0))))          ; source absent from trust map -> default 0.0

(= (lit-sources $l) (sort-atom (collapse (match &st (src $l $s) $s))))

; A fact's trust: best (max) of its claiming sources; an unclaimed fact is
; taken at face value (1.0 — asserted without provenance).
(= (fact-trust $l)
   (let $ss (lit-sources $l)
     (if (== $ss ()) 1.0
         (foldl-atom (map-atom $ss $s (source-trust-val $s)) 0.0 $a $x (max $a $x)))))

; Rules carry no trust in MeTTa -> default 0.0 (weakest link of any derivation).
(= (rule-trust $lbl) 0.0)

; --- weakest-link over the proof tree ---
(= (trust-of $lit) (proof-trust (explain $lit)))

(= (proof-trust (no-proof $l)) 0.0)
(= (proof-trust (cycle $l)) 0.0)
(= (proof-trust (proof $l (fact $lbl))) (fact-trust $l))
(= (proof-trust (proof $l (rule $lbl $subs)))
   (foldl-atom (map-atom $subs $s (proof-trust $s))
               (rule-trust $lbl) $a $x (min $a $x)))

; --- source union over the proof tree ---
(= (sources-of $lit) (sort-atom (proof-sources (explain $lit))))

(= (proof-sources (no-proof $l)) ())
(= (proof-sources (cycle $l)) ())
(= (proof-sources (proof $l (fact $lbl))) (lit-sources $l))
(= (proof-sources (proof $l (rule $lbl $subs)))
   (unique-atom (foldl-atom (map-atom $subs $s (proof-sources $s))
                            () $a $x (union-atom $a $x))))

; --- threshold filtering (a literal passes iff its trust >= threshold) ---
(= (threshold-val $name)
   (case (once (match &st (threshval $name $v) $v))
     (($v $v) (Empty 0.0))))

(= (meets-threshold $lit $name) (>= (trust-of $lit) (threshold-val $name)))

; --- unified justification (a single-call "why does this hold?" view) --------
; Bundles everything known about why a literal holds: DL status + proof tree +
; weakest-link trust + claiming sources + a confidence label — proof and trust
; together rather than through separate queries.
(= (status-of $lit)
   (if (== (defp? $lit) True) definitely-provable
   (if (== (dft-of $lit) true) defeasibly-provable
       not-provable)))

(= (confidence-label $t)
   (if (>= $t 0.7) high (if (> $t 0.0) low none)))

(= (justify $lit)
   (let $t (trust-of $lit)
     (justification (literal $lit)
                    (status (status-of $lit))
                    (trust $t)
                    (confidence (confidence-label $t))
                    (sources (sources-of $lit))
                    (proof (explain $lit)))))

; --- trust-annotated conclusions: (tconcl <tag> <lit> <trust> <sources>) ---
; Only positive conclusions carry trust/sources (negatives have no derivation).
(= (trust-concl-of $q)
   (superpose
     ((if (== (defp? $q) True)
          (tconcl pD $q (trust-of $q) (sources-of $q))
          (tconcl nD $q 0.0 ()))
      (if (== (dft-of $q) true)
          (tconcl pd $q (trust-of $q) (sources-of $q))
          (tconcl nd $q 0.0 ())))))

(= (trust-conclusions)
   (sort-atom (collapse (let $q (ulit-gen) (trust-concl-of $q)))))

(= (dl-trust-run $path)
   (let* (($_1 (dl-load $path))
          ($_2 (dl-reason!)))
     (trust-conclusions)))
