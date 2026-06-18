; lib_deontic <-> NAL belief bridge  (opt-in feature; not loaded by default).
;
; The two reasoners are complementary: NAL (lib_nal) grades HOW MUCH a fact is
; believed from evidence — an (stv frequency confidence) truth value — while
; lib_deontic decides WHAT DEFEASIBLY HOLDS and what is obligated/permitted/
; forbidden. This seam lets graded belief flow into defeasible/deontic reasoning
; and lets defeasible conclusions flow back out as graded belief. It is the
; NARS-family successor to an earlier Subjective-Logic seam: NAL's (frequency,
; confidence) is exactly the evidential model that bridge needed, and revision
; (Truth_Revision) fuses conclusions from both engines.
;
; Engine-parametric: PLN (lib_pln) shares the (stv f c) format, so the same
; mappings drive PLN by swapping the inference operator |- for |~ — only the
; `infer` indirection below changes.

!(import! &self (library OmegaClaw-Core lib_deontic))
!(import! &self (library OmegaClaw-Core lib_nal))

; Inference operator (NAL by default; set to |~ to drive PLN instead).
(= (infer $b1 $b2) (|- $b1 $b2))

; --- trust  <->  truth value -----------------------------------------------
; lib_deontic trust is a calibrated degree in [0,1]; map it to NAL evidence at a
; total weight W (the k=W convention): frequency = trust, confidence = w2c(W).
; The inverse reads NAL's projected expectation E = c*(f-0.5)+0.5 back as trust.
(= (bridge-weight) 2.0)
(= (trust->stv $t) (stv $t (Truth_w2c (bridge-weight))))
(= (stv->trust $stv) (Truth_Expectation $stv))

; --- literal  <->  NAL term ------------------------------------------------
; Only FACTUAL literals (deontic mode `none`) cross: NAL reasons about what IS,
; lib_deontic about what OUGHT, so the modality stays on the deontic side.
;   nullary  p        -> atomic term  p
;   unary    P(X)     -> inheritance  (--> X P)            "X is a P"
;   binary   REL(S,O) -> product inh. (--> (× S O) REL)    idiomatic NAL relation
(= (lit->term (lit $sg $m $tm $f ()))      $f)
(= (lit->term (lit $sg $m $tm $f ($x)))    (--> $x $f))
(= (lit->term (lit $sg $m $tm $f ($s $o))) (--> (× $s $o) $f))

; NAL term -> positive literal (ordered: match the product/relation shape first).
(= (term->plit $term)
   (case $term
     (((--> (× $s $o) $rel) (lit pos none none $rel ($s $o)))
      ((--> $x $p)          (lit pos none none $p ($x)))
      ($atom                (lit pos none none $atom ())))))

; --- conclusion -> belief (project a defeasible conclusion OUT to NAL) ------
; A defeasibly-provable (+d) literal HOLDS, so its sign sets frequency (positive
; -> 1.0, negative -> 0.0); confidence is the deduction-level base. -d/-D/+D and
; deontic-mode literals do not project (no belief).
(= (sign-freq pos) 1.0)
(= (sign-freq neg) 0.0)
(= (concl->belief $c)
   (case $c
     (((pd (lit $sg none $tm $f $a))
       ((lit->term (lit pos none $tm $f $a)) (stv (sign-freq $sg) 0.81)))
      ($other ()))))

; Run a defeasible theory and project every "what holds" conclusion to a belief.
(= (theory->beliefs $path)
   (let $cs (dl-run $path)
     (unique-atom
       (filter-atom (map-atom $cs $c (concl->belief $c)) $b (not (== $b ()))))))

; --- belief -> deontic fact (inject a credible belief IN) -------------------
; A belief whose projected expectation clears a credibility threshold becomes a
; deontic fact (signed by whether the term is believed true or false) carrying
; that expectation as its trust; below threshold -> ().
(= (get-freq (stv $f $c)) $f)
(= (belief->fact ($term $stv) $threshold)
   (let* (($f (get-freq $stv))
          ($plit (term->plit $term))
          ($lit (if (< $f 0.5) (lit-neg $plit) $plit))
          ($e (Truth_Expectation (if (< $f 0.5) (Truth_Negation $stv) $stv))))
     (if (> $e $threshold) (dfact $lit $e) ())))

; --- combined step (the payoff round-trip) ---------------------------------
; Inject credible NAL beliefs into a loaded theory as facts, run the defeasible
; + deontic engine, then reflect the resulting conclusions back out as beliefs.
; The reflected beliefs can be fused with prior evidence via (infer b b').
(= (inject-belief-facts $beliefs $threshold)
   (map-atom $beliefs $b
     (let $df (belief->fact $b $threshold)
       (case $df
         (((dfact $lit $tr) (mm_add_fact $lit &theory &ground &herb &st))
          ($_ ()))))))

(= (combined-step $path $beliefs $threshold)
   (let* (($_l (dl-load $path))
          ($_i (inject-belief-facts $beliefs $threshold))
          ($_r (dl-reason!))
          ($cs (dl-conclusions)))
     (unique-atom
       (filter-atom (map-atom $cs $c (concl->belief $c)) $b (not (== $b ()))))))
