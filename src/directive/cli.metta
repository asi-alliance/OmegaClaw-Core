; CLI — argv dispatch over the engine + task-coordination layers. Command
; surface (invoked as `dl <command> ...`):
;   dl reason <file>                       conclusion set
;   dl explain <lit> <file>                proof tree
;   dl why-not <lit> <file>                blockers
;   dl requires <lit> <file>               verified fact-set
;   dl what-if <file> <fact> <goal>        hypothetical reasoning
;   dl status <file>                       task status groups
;   dl next <file>                         next actions
;   dl claim|unclaim|block|unblock|complete <task> <file> <agent>
;   dl assert <file> <agent> <plan-text>
;
; The launcher passes: argv 0 = entry file, argv 1 = --silent, argv 2.. = ours.

(= (cli-arg $n) (argv (+ $n 2)))

; CLI literal syntax handled by the platform kernel (mm_parse_lit):
;   name | ~name | -name | (f a b) | ~(f a b)
(= (parse-cli-lit $a) (mm_parse_lit $a))

(= (print-concls $cs)
   (if (== $cs ()) ()
       (let* (($_ (mm_print (mm_concl_str (car-atom $cs))))
              ($__ (print-concls (cdr-atom $cs))))
         ())))

(= (print-tconcls $cs)
   (if (== $cs ()) ()
       (let* (($_ (mm_print (mm_trust_str (car-atom $cs))))
              ($__ (print-tconcls (cdr-atom $cs))))
         ())))

(= (cli-main)
   (let $cmd (cli-arg 0)
     (case $cmd
       ((reason
          (let* (($cs (dl-run (cli-arg 1)))
                 ($_ (mm_print "Conclusions:")))
            (mm_print_concls $cs)))
        (reason-at
          (let* (($cs (dl-run-at (cli-arg 2) (cli-arg 1)))
                 ($_ (mm_print "Conclusions:")))
            (mm_print_concls $cs)))
        (trust
          (let* (($cs (dl-trust-run (cli-arg 1)))
                 ($_ (mm_print "Conclusions:")))
            (mm_print_tconcls $cs)))
        (explain
          (let* (($_ (dl-run (cli-arg 2))))
            (println! (explain (parse-cli-lit (cli-arg 1))))))
        (justify
          (let* (($_ (dl-run (cli-arg 2))))
            (println! (justify (parse-cli-lit (cli-arg 1))))))
        (why-not
          (let* (($_ (dl-run (cli-arg 2))))
            (println! (dl-why-not (parse-cli-lit (cli-arg 1))))))
        (requires
          (println! (dl-requires (cli-arg 2) (parse-cli-lit (cli-arg 1)))))
        (what-if
          (println! (dl-what-if (cli-arg 1)
                                     ((parse-cli-lit (cli-arg 2)))
                                     (parse-cli-lit (cli-arg 3)))))
        (status   (println! (directive-status (cli-arg 1))))
        (next     (println! (directive-next (cli-arg 1))))
        (board    (println! (directive-board (cli-arg 1))))
        (summary  (println! (directive-summary (cli-arg 1))))
        (info     (println! (directive-info (cli-arg 1))))
        (claim    (println! (directive-claim (cli-arg 2) (cli-arg 1) (cli-arg 3) False)))
        (unclaim  (println! (directive-unclaim (cli-arg 2) (cli-arg 1) (cli-arg 3))))
        (block    (println! (directive-block (cli-arg 2) (cli-arg 1) (cli-arg 3))))
        (unblock  (println! (directive-unblock (cli-arg 2) (cli-arg 1) (cli-arg 3))))
        (complete (println! (directive-complete (cli-arg 2) (cli-arg 1) (cli-arg 3))))
        (assert   (println! (directive-assert (cli-arg 1) (cli-arg 2) (cli-arg 3))))
        ; process mining (`learn` namespace): args are argv-parsed (file
        ; list + --format/--min-support/--min-confidence/--against flags)
        (learn-extract-log (learn-extract-log))
        (learn-rules       (learn-rules))
        (learn-validate    (learn-validate))
        ; plan inspection
        (trace    (directive-trace (cli-arg 1)))
        (validate (directive-validate (cli-arg 1) (== (mm_argn_or 2 "") "--strict")))
        (analyze  (directive-analyze (cli-arg 1)))
        (compliance (deontic-compliance (cli-arg 1)))
        (dilemmas (deontic-dilemmas (cli-arg 1)))
        (deadlines (deontic-deadlines (cli-arg 1) (cli-arg 2)))
        (timeline (ec-timeline (cli-arg 1) (cli-arg 2)))
        (assign   (directive-assign (cli-arg 1) (mm_argn_or 2 "")))
        ; commands needing external services (LLM / OS / network / crypto / TTY)
        (translate (directive-stub translate "an LLM to translate natural language to MeTTa plans"))
        (review    (directive-stub review "an LLM to review the plan"))
        (llm       (directive-stub llm "an LLM provider"))
        (decompose (directive-stub decompose "an LLM to decompose a task into subtasks"))
        (spawn     (directive-stub spawn "OS process spawning of agents"))
        (watch     (directive-stub watch "filesystem/process watching"))
        (serve     (directive-stub serve "a network server"))
        (remote    (directive-stub remote "remote plan networking"))
        (forget    (directive-stub forget "remote plan networking"))
        (session   (directive-stub session "on-disk session state"))
        (repl      (directive-stub repl "an interactive terminal"))
        (completions (directive-stub completions "shell completion generation"))
        (whoami    (directive-stub whoami "an Ed25519 cryptographic identity"))
        (init      (directive-stub init "plan scaffolding on disk"))
        (journal   (directive-stub journal "on-disk plan journal storage"))
        (findings  (directive-stub findings "on-disk findings storage"))
        ($other
          (let* (($_ (println! (unknown-command $other)))
                 ($__ (println! "usage: dl reason|reason-at|trust|explain|justify|why-not|requires|what-if|trace|validate ..."))
                 ($___ (println! "       status|next|board|summary|info|analyze|assign|claim|unclaim|block|unblock|complete|assert|learn-extract-log|learn-rules|learn-validate ...")))
            ()))))))
