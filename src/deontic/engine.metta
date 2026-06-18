; Engine facade: load a theory -> ground it -> run DL(d) inference -> read off
; the tagged conclusion set. The single entry point lib_deontic builds on.

; Load a plan/theory file into the engine spaces. dl-load resets engine state
; first, then dispatches on surface format: .metta plans are read with PeTTa's
; native loader and each form ingested; .dfl theories use the arrow-syntax parser.
(= (dl-load $path)
   (let $_ (dl-reset) (dl-ingest-file $path)))

(= (dl-ingest-file $path)
   (case (mm_plan_format $path)
     ((dfl   (mm_load_dfl $path &theory &ground &herb &st))
      (metta (dl-load-native $path)))))

; Native .metta load: load the file into the scratch &plan space, then ingest
; every form it holds into the theory / ground / herbrand / status spaces.
(= (dl-load-native $path)
   (let* (($_1 (mm_clear_space &plan))
          ($_2 (mm_load_into $path &plan)))
     (collapse (mm_ingest (match &plan $f $f) &theory &ground &herb &st))))

; Reasoning backend, switchable: prolog (fast indexed kernel, default) | native
; (the atomspace-native MeTTa engine in ground.metta / reason.metta — identical
; conclusions, ideal for propositional plans and inspection). Set per run with
; (dl-engine! native) or $OMEGACLAW_DL_ENGINE=native. Native reasoning is at
; parity, but native grounding runs ~4-5x the Prolog kernel on grounding-heavy
; theories (per-operation MeTTa-eval overhead, not algorithmic — see the perf
; note in ground.metta), so prolog stays the default.
(= (dl-engine! $m) (mm_dl_engine_set $m))

(= (dl-ground!)
   (case (mm_dl_engine_get)
     ((native (ground-sn!))
      ($_     (mm_ground &theory &ground &herb &st)))))
(= (dl-reason-only!)
   (case (mm_dl_engine_get)
     ((native (reason!))
      ($_     (mm_reason &ground &theory &st)))))

(= (dl-reason!)
   (let* (($_1 (dl-ground!))
          ($_2 (dl-reason-only!)))
     ()))

; conclusions: prolog reads the interned integer-indexed status (mm_conclusions);
; native reads off reason.metta's (conclusions). sort-atom normalizes ordering.
(= (dl-conclusions)
   (case (mm_dl_engine_get)
     ((native (sort-atom (conclusions)))
      ($_     (sort-atom (mm_conclusions))))))

(= (dl-run $path)
   (let* (($_1 (dl-load $path))
          ($_2 (dl-reason!)))
     (dl-conclusions)))

; As-of reasoning (--at <ref>): ground, drop temporally-inactive atoms at the
; reference time, then reason. Ref is millis (int) or an ISO-8601 string.
(= (dl-run-at $path $ref)
   (let* (($_1 (dl-load $path))
          ($_2 (dl-ground!))
          ($_3 (mm_at_filter &ground &herb &st $ref))
          ($_4 (dl-reason-only!)))
     (dl-conclusions)))

; --- Standard Deontic Logic reasoning (opt-in) -------------------------------
; Ground, inject SDL bridge grules (F p ≡ O ¬p; O p → P p), then reason. The
; default dl-run stays purely classical; this derives the deontic closure
; (and deontic conflicts fall out via the normal sign-complement attack).
(= (dl-run-deontic $path)
   (let* (($_1 (dl-load $path))
          ($_2 (dl-ground!))
          ($_3 (mm_deontic_bridge &ground &herb &st))
          ($_4 (dl-reason-only!)))
     (dl-conclusions)))

; Deontic compliance + dilemmas live in deontic.metta (deontic-compliance /
; compliance-of / deontic-dilemmas / deontic-dilemmas-report).

; Event-Calculus obligation lifecycle lives in eventcalc.metta
; (ec-intervals / ec-holds-at / ec-violated-at / ec-timeline).

; (temporal-deontic deadline compliance — deontic-deadlines / deadline-status —
;  also lives in deontic.metta.)

; --- incremental (append-only) session ---------------------------------------
; For workflows that mutate a theory by APPENDING new blocks of facts/rules:
; load once keeping the materialized base, then each append only
; grounds the new closure (semi-naive, add-only) instead of re-grounding from
; scratch. Reasoning is non-monotonic so it re-runs over the grown ground set,
; but grounding — usually the costly part on large plans — is incremental.
; Yields IDENTICAL conclusions to a from-scratch load of the concatenated plan.

(= (dl-load-incr $path)
   (let* (($_1 (dl-reset))
          ($_2 (dl-ingest-file $path))
          ($_3 (mm_ground_incr_init &theory &ground &herb &st)))
     ()))

; Append a delta plan file (new claims/facts/rules), ground only the delta.
(= (dl-append-incr! $path)
   (let* (($_1 (dl-ingest-file $path))
          ($_2 (mm_ground_delta &theory &ground &herb &st)))
     ()))

; Reason over the current (grown) ground set and read off conclusions.
(= (dl-reason-incr)
   (let $_ (mm_reason &ground &theory &st) (dl-conclusions)))

; Pretty printer: one "  +D penguin" line per conclusion, tagged with its
; defeasible-logic provability tag (+D/-D definite, +d/-d defeasible).
(= (print-concl $c)
   (println! (mm_concl_str $c)))
(= (dl-print $path)
   (for-each-in-atom (dl-run $path) print-concl))
