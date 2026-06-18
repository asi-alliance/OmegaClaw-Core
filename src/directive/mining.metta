; Process mining — the `learn` namespace (extract-log / rules / validate-rules).
;
; The engine lives in the process-mining kernel (platform/mining.pl): event-log
; extraction from MeTTa `(claims ... (given F) ...)` blocks, the Alpha footprint +
; directly-follows relations, trace-level support/confidence, and XOR/mutex
; conflict detection. These wrappers expose structured results to MeTTa and drive
; the CLI renderers.
;
; Rules and r_mined_N labels are emitted as a SET in a stable sorted order, so
; the output is deterministic across runs.

; --- structured results (queries / tests) ---
;   (mining-event-log (f1 f2 ...))        -> ((CaseId ((TS Act Actor) ...)) ...)
;   (mining-rules files minSup minConf)   -> ((Body Head Support "C.CC") ...) sorted
(= (mining-event-log $files) (mm_event_log $files))
(= (mining-rules $files $min-support $min-confidence)
   (mm_mine_rules $files $min-support $min-confidence))

; --- renderers (write the report / DFL / JSON output) ---
(= (mining-extract-print $files $format)
   (if (== $format summary)
       (mm_print_extract_summary $files)
       (mm_print_extract_json $files)))

(= (mining-rules-print $files $format $min-support $min-confidence)
   (if (== $format summary)
       (mm_print_mine_summary $files $min-support $min-confidence)
       (mm_print_mine_dfl $files $min-support $min-confidence)))

; validate: load the `against` plan, count its non-fact rules, mine the traces.
(= (mining-validate-print $traces $against)
   (let* (($_ (dl-load $against))
          ($n (mm_count_nonfact &theory)))
     (mm_print_validate $traces $n)))

; --- CLI entry points (argv-driven; `learn <cmd>` defaults) ---
(= (learn-extract-log)
   (mining-extract-print (mm_learn_files) (mm_learn_format json)))

(= (learn-rules)
   (mining-rules-print (mm_learn_files)
                       (mm_learn_format dfl)
                       (mm_learn_minsup 1)
                       (mm_learn_minconf 0.5)))

(= (learn-validate)
   (mining-validate-print (mm_learn_files) (mm_learn_against "")))
