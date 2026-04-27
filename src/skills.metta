(= (getSkills)
   (;INTERNAL:
    "- Remember a particular string such as skills and memories: remember string"
    "- Query long-term embedding memory for skills and memories with short phrases only: query string"
    "- Episodes searches history for episodes around a time stamp, time format is same as in TIME: episodes time_string"
    "- Pin a certain string as short-term working memory item to keep track of task state: pin string"
    ;SHELL AND FILE I/O:
    "- Execute shell command without apostrophe in string, it returns the command output to you: shell string"
    "- Read file to string: read-file filename"
    "- Write string to file: write-file filename string"
    "- Append line to file: append-file filename string",
    ;COMMUNICATION CHANNELS:
    "- Send message to user: send string"
    "- Search the web: search string"
    "- Search the web using the Tavily Search Agent: tavily-search string"
    "- Get technical analysis for a stock ticker using the Technical Analysis Agent: technical-analysis ticker"
    ;CRO / ETHICS RISK GOVERNANCE:
    "- Add, list, get, or summarize structured AI ethics and enterprise risk records: risk-register action payload_json_or_text"
    "- Update an existing structured risk record by ID: risk-update risk_id patch_json"
    "- Return JSON dashboard data for the AI ethics and risk cockpit: risk-dashboard"
    ;CODE EXECUTION:
    "- Execute MeTTa expression: metta sexpression"
    "Example to invoke Non-Axiomatic Logic via MeTTa: "
    "metta (|- ((--> (× sam garfield) friend) (stv 1.0 0.9))"
    "          ((--> garfield animal) (stv 1.0 0.9)))"
    "metta (|- ((==> (--> (× $1 elephant) eat) (--> $1 ([] dangerous))) (stv 1.0 0.9))"
    "          ((--> (× tiger elephant) eat) (stv 1.0 0.9)))"
    "Also: note the $1 for independent variables, and for negated knowledge use (stv 0.0 0.9)"
    "Additionally |- also works for revision, to merge evidence even when the term of both premises is the same."
    "You can also use PLN:"
    "metta (|~ ((Implication (Inheritance $1 (IntSet Feathered))"
    "           (Inheritance $1 Bird)) (stv 1.0 0.9))"
    "          ((Inheritance Pingu (IntSet Feathered)) (stv 1.0 0.9)))"))


(= (read-file $file)
   (progn (translatePredicate (exists_file $file))
          (translatePredicate (read_file_to_string $file $content ()))
          $content))

(= (write-file $file $str)
   (progn (translatePredicate (open $file write $Out))
          (translatePredicate (write $Out $str))
          (translatePredicate (close $Out))
          WRITE-FILE-SUCCESS))

(= (append-file $file $str)
   (progn (translatePredicate (exists_file $file))
          (translatePredicate (open $file append $Out))
          (translatePredicate (write $Out $str))
          (translatePredicate (nl $Out)),
          (translatePredicate (close $Out))
          APPEND-FILE-SUCCESS))

(= (tavily-search $query)
   (py-call (agentverse.tavily_search $query)))

(= (technical-analysis $ticker)
   (py-call (agentverse.technical_analysis $ticker)))

(= (risk-register $action $payload)
   (py-call (risk_register.risk_register $action $payload)))

(= (risk-register $action)
   (py-call (risk_register.risk_register $action "")))

(= (risk-update $risk_id $payload)
   (py-call (risk_register.risk_register_update $risk_id $payload)))

(= (risk-dashboard)
   (py-call (risk_register.dashboard_data)))

!(import_prolog_functions_from_file (library OmegaClaw-Core ./src/skills.pl) (shell first_char))

(= (metta $str)
   (let $code (sread $str)
        (repr (swrite (eval $code)))))

(= (pin $x)
   PIN-SUCCESS)

;; ----------------------------------------------------------------------
;; Keyword-argument shims (B-tolerant, 2026-04-25).
;;
;; Reasoning models that emit JSON tool calls go through lib_llm_ext's
;; format adapter, which produces kwarg-shaped MeTTa s-exprs:
;;     (send (text "hi"))
;;     (write-file (filename "x.txt") (content "hi"))
;; The shims below match those forms and delegate to the existing
;; positional rules. The original positional callsites still work, so
;; Gemma/Qwen/Claude (metta-mode) see zero behavior change.
;;
;; Argument order in each shim head MUST match the order in
;; lib_llm_ext._SKILL_ARG_ORDER for that skill.
;; ----------------------------------------------------------------------

(= (send         (text $x))                           (send         $x))
(= (remember     (text $x))                           (remember     $x))
(= (query        (text $x))                           (query        $x))
(= (episodes     (time $x))                           (episodes     $x))
(= (pin          (text $x))                           (pin          $x))
(= (shell        (cmd $x))                            (shell        $x))
(= (read-file    (filename $f))                       (read-file    $f))
(= (write-file   (filename $f) (content $s))          (write-file   $f $s))
(= (append-file  (filename $f) (content $s))          (append-file  $f $s))
(= (search       (query $q))                          (search       $q))
(= (tavily-search       (query $q))                   (tavily-search       $q))
(= (technical-analysis  (ticker $t))                  (technical-analysis  $t))
(= (risk-register       (action $a) (payload $p))     (risk-register       $a $p))
(= (risk-register       (action $a))                  (risk-register       $a))
(= (risk-update         (risk_id $id) (payload $p))   (risk-update         $id $p))
(= (metta        (code $s))                           (metta        $s))
