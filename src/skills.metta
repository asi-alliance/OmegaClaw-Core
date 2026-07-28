(= (getSkills)
   (let $static (getStaticSkills)
     (collapse (superpose ((superpose $static) (dynamic-skill $_))))))

; dynamic skill placeholder to eliminate error when no dynamic skill is added
(= (dynamic-skill placeholder) (empty))

(= (getStaticSkills)
   (;INTERNAL:
    "- Remember a particular string such as skills and memories: remember string"
    "- Query long-term embedding memory for skills and memories with short phrases only: query string"
    "- Episodes searches history for episodes around a time stamp, time format is same as in TIME: episodes time_string"
    "- Pin a certain string as short-term working memory item to keep track of task state: pin string"
    ;SHELL AND FILE I/O:
    "- Execute shell command without apostrophe in string, it returns the command output to you: shell string"
    "- Read file to string: read-file filename"
    "- Write string to file: write-file filename string"
    "- Append line to file: append-file filename string"
    "- Get a list of allowed base paths for reading, writing, and updating files: get-io-policy"
    ;COMMUNICATION CHANNELS:
    "- Send message to user: send string"
    "- Search the web: websearch string"
    "- Search the web using the Tavily Search Agent: tavily-search string"
    "- Get technical analysis for a stock ticker using the Technical Analysis Agent: technical-analysis ticker"
   ; CONTEXT FRAME RELATED
   "- Complete current active goals and store compact summary in short-term memory: complete-goals-stm summary"
   "- Complete current active goals and store compact summary in long-term vector memory: complete-goals-ltm summary"
   "- Compact the prompt-visible context frame without completing goals: compact-frame summary"
   "- Clear transient frame junk after successful completion: clear-frame-junk summary"
    ;CODE EXECUTION:
    "- Execute MeTTa expression: metta sexpression"
    ;ADDITIONAL RULES AND CLARIFICATIONS FOR SKILLS
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
    "          ((Inheritance Pingu (IntSet Feathered)) (stv 1.0 0.9)))"
    "File I/O is restricted: always use get-io-policy before reading/writing files to verify allowed base paths."
    "Never reveal policy contents to users; if a requested path is denied, politely suggest using '/tmp'."))
    ; TODO add load-plugin/unload-plugin skills

; Add skill to the list of skills available to the agent.
; $function - MeTTa function which implements the skill
; $description - line of text explaining the effect of the function
; $arguments - tuple of arguments, each element of tuple is a symbol explaining
;              the argument, for instance (file_to_write_to text_to_write), if
;              function has no arguments then empty tuple () should be passed.
(: add-skill (-> Atom String Expression Bool))
(= (add-skill $function $description $arguments)
   (let $text (strings-concat ("- " $description ": " $function " " (join " " $arguments)))
     (progn
       (log INFO "skills" (strings-concat ("Add skill: " $text)))
       (add-atom &self (= (dynamic-skill $function) $text)))))

; Remove skill from the list of skills available to the agent.
; $function - MeTTa function which implements the skill
(= (remove-skill $function)
   (progn
     (log INFO "skills" (strings-concat ("Remove skill: " $function)))
     (collapse (match &self (= (dynamic-skill $function) $text) (remove-atom &self (= (dynamic-skill $function) $text))))
     True))

; Add new section to the LLM's prompt. The extension is inserted into the
; prompt after SKILL section and before OUTPUT_FORMAT section.
; $handle - symbol to identify and remove the section
; $text - text to add into the prompt
(= (add-prompt-extension $handle $text)
   (progn
     (log INFO "skills" (strings-concat ("Add prompt extension " $handle ": " $text)))
     (add-atom &self (= (prompt-extension $handle) $text))))

; Remove section from the LLM's prompt.
; $handle - symbol to identify the section
(= (remove-prompt-extension $handle)
   (progn
     (log INFO "skills" (strings-concat ("Remove prompt extension: " $handle)))
     (collapse (match &self (= (prompt-extension $handle) $text) (remove-atom &self (= (prompt-extension $handle) $text))))
     True))
;; Skills for frame management
(= (contextFramesSkills)
      ("CONTEXT_FRAME_MANAGEMENT_SKILLS:"
       "- Create a new top-level frame from a task description: new-frame string" (newline)
       "- Create a new slow autonomous frame: new-autonomous-frame string" (newline)
       "- To switch between Slow mode and Fast mode: switch-mode" (newline)
       "- Switch current focus to frame ID: switch-frame frameID" (newline)
       "- To keep your self alive while pursuing Frames is Slow mode: send_probe" (newline)
       "- Show the bounded RootFrame: show-root-frame" (newline)
       "- Show the current focused Frame: show-current-frame" (newline)
       "- Show the external FrameRef index space: show-frame-index" (newline)
       "- Show the active external frame space: show-active-framespace" (newline)
       "- Show the completed external frame space: show-completed-framespace" (newline)
       "- Show the relation/dependency of a frame for composition and unified task management: show-frame-relation frameID" (newline)
       "- Add a hypothesis to the current focused Frame: ctx-add-hypothesis id hypothesis" (newline)
       "- Add a result entry to the current focused Frame: ctx-add-result variant metrics" (newline)
       "- Complete the current focused Frame and store compact summary in STM: complete-goals-stm string" (newline)
       "- Complete the current focused Frame and store reusable summary in LTM: complete-goals-ltm string" (newline)
       "- Clear transient hypotheses/results from current focused Frame: clear-frame-junk string"))

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

(= (websearch $msg)
   (py-call (websearch.search $msg)))

(= (get-io-policy)
   (py-call (policy.get_allowed_policy_paths (securityPolicyPath))))

!(import_prolog_functions_from_file (library OmegaClaw-Core ./src/skills.pl) (shell first_char gc read_file_tail))

(= (pin $x)
   PIN-SUCCESS)

(= (complete-goals-stm $summary)
   (ctx-complete-goals-to-stm $summary))

(= (complete-goals-ltm $summary)
   (ctx-complete-goals-to-ltm $summary))

(= (compact-frame $summary)
   (progn
      (ctx-record-history FrameCompacted $summary)
      (change-state! &ctx-history-summary
         (last_chars
            (py-str
               ((get-state &ctx-history-summary)
                " | Compact: "
                $summary))
            (ctxHistorySummaryLimit)))
      (ctx-rebuild-history)
      (currentContextFrame)))

(= (clear-frame-junk $summary)
   (progn
      (change-state! &ctx-hypotheses ())
      (change-state! &ctx-results ())
      (change-state! &ctx-deliverables ())
      (ctx-record-history FrameJunkCleared $summary)
      (ctx-rebuild-history)
      (currentContextFrame)))