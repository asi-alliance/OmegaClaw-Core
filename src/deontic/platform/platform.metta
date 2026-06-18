; Platform layer: registers the deterministic Prolog kernel (io.pl and the fast
; grounding / reasoning / deontic / event-calculus engines) as MeTTa functions.
; This is the only module that knows the engine runs on PeTTa (SWI-Prolog).
;
; Paths resolve through PeTTa's own (library OmegaClaw-Core <file>) helper, since
; the engine ships as a repo inside the PeTTa tree — no environment variable and
; no impl-specific root logic.

!(import! &self (library lib_import))

!(import_prolog_functions_from_file
   (library OmegaClaw-Core src/deontic/platform/io.pl)
   (mm_append_file mm_write_file mm_read_file mm_exists
    mm_now_iso mm_clear_space mm_gensym mm_halt mm_print mm_parse_lit mm_srand
    mm_log mm_log_set_level mm_log_set_path
    mm_dl_engine_get mm_dl_engine_set
    mm_arith_eval mm_acmp mm_num_eq mm_tcmp mm_pct mm_tp_le
    mm_load_into mm_plan_format mm_load_dfl mm_ingest mm_add_fact mm_at_filter
    mm_lit_str mm_concl_str mm_trust_str
    mm_print_concls mm_print_tconcls
    file-open! file-close! file-read-to-string! file-write! file-get-size! file-seek!))

; A few SWI builtins that already follow the function convention:
!(import_prolog_function string_length)
!(import_prolog_function string_concat)

; fast tabled Datalog grounding (+ semi-naive add-only incremental grounding)
!(import_prolog_functions_from_file
   (library OmegaClaw-Core src/deontic/platform/grounding.pl)
   (mm_ground mm_ground_incr_init mm_ground_delta))

; fast indexed DL(d) reasoner + conclusion enumerator
!(import_prolog_functions_from_file
   (library OmegaClaw-Core src/deontic/platform/reason.pl)
   (mm_reason mm_conclusions))

; Standard Deontic Logic bridges + report formatters
!(import_prolog_functions_from_file
   (library OmegaClaw-Core src/deontic/platform/deontic.pl)
   (mm_deontic_bridge mm_print_verdicts mm_print_dilemmas2 mm_print_deadlines2))

; Event-Calculus obligation lifecycle (obligations as inertial fluents)
!(import_prolog_functions_from_file
   (library OmegaClaw-Core src/deontic/platform/eventcalc.pl)
   (mm_dlit mm_print_timeline2))

; Repo-rooted path helper for data files: (dl-path tests/deontic/x.metta)
(= (dl-path $rel) (library OmegaClaw-Core $rel))

; Reset all engine spaces (theory, ground rules, herbrand base, statuses).
(= (dl-reset)
   (let* (($_1 (mm_clear_space &theory))
          ($_2 (mm_clear_space &ground))
          ($_3 (mm_clear_space &herb))
          ($_4 (mm_clear_space &st)))
     ()))
