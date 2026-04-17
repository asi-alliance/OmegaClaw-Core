(= (getSkills)
   (if (isTelegram)
       (;TELEGRAM ALLOWED SKILLS:
           "- Remember a particular string: (remember string)"
           "- Query long-term embedding memory: (query string)"
           "- Pin a short-term working memory item: (pin string)"
           "- Send message to user: (send string)"
        "- Search the web: (search string)")
       (;DEFAULT ALLOWED SKILLS:
        ;INTERNAL:
        "- Remember a particular string such as skills and memories: (remember string_in_quotes)"
        "- Query long-term embedding memory for skills and memories with short phrases only: (query string_in_quotes)"
        "- Episodes searches history for episodes around a time stamp, time format is same as in TIME: (episodes time_string_in_quotes)"
        "- Pin a certain string as short-term working memory item to keep track of task state: (pin string_in_quotes)"
        ;SHELL AND FILE I/O:
        "- Execute shell command without apostrophe in string, it returns the command output to you: (shell string_in_quotes)"
        "- Read file to string: (read-file filename_in_quotes)"
        "- Write string to file: (write-file filename_in_quotes string_in_quotes)"
        "- Append line to file: (append-file filename_in_quotes string_in_quotes)",
        ;COMMUNICATION CHANNELS:
        "- Send message to user: (send string_in_quotes)"
        "- Search the web: (search string_in_quotes)"
        "- Search the web using the Tavily Search Agent: (tavily-search string_in_quotes)"
        "- Get technical analysis for a stock ticker using the Technical Analysis Agent: (technical-analysis ticker_in_quotes)"
        ;CODE EXECUTION:
        "- Execute MeTTa expression: (metta sexpression)"
        "Example to invoke Non-Axiomatic Logic via MeTTa: "
        "(metta (|- ((--> (× sam garfield) friend) (stv 1.0 0.9))"
        "           ((--> garfield animal) (stv 1.0 0.9))))"
        "(metta (|- ((==> (--> (× $1 elephant) eat) (--> $1 ([] dangerous))) (stv 1.0 0.9))"
        "           ((--> (× tiger elephant) eat) (stv 1.0 0.9))))"
        "Also: note the $1 for independent variables, and for negated knowledge use (stv 0.0 0.9)"
        "Additionally |- also works for revision, to merge evidence even when the term of both premises is the same."
        "You can also use PLN:"
        "(metta (|~ ((Implication (Inheritance $1 (IntSet Feathered))"
        "            (Inheritance $1 Bird)) (stv 1.0 0.9))"
        "           ((Inheritance Pingu (IntSet Feathered)) (stv 1.0 0.9))))")))

(= (read-file $file)
   (if (isTelegramButNotRequired $file)
    (Error read-file "DENIED: File access is disabled in Telegram mode.")
       (progn (translatePredicate (exists_file $file))
              (translatePredicate (read_file_to_string $file $content ()))
              $content))
              )

(= (write-file $file $str)
   (if (isTelegram)
        (Error write-file "DENIED: File mutation is disabled in Telegram mode.")
       (progn (translatePredicate (open $file write $Out))
              (translatePredicate (write $Out $str))
              (translatePredicate (close $Out))
              WRITE-FILE-SUCCESS)))

(= (append-file $file $str)
   (if (isTelegramButNotRequired $file)
        (Error append-file "DENIED: File mutation is disabled in Telegram mode.")
        (progn (translatePredicate (exists_file $file))
              (translatePredicate (open $file append $Out))
              (translatePredicate (write $Out $str))
              (translatePredicate (nl $Out)),
              (translatePredicate (close $Out))
              APPEND-FILE-SUCCESS)))

(= (tavily-search $query)
   (py-call (agentverse.tavily_search $query)))

(= (technical-analysis $ticker)
   (py-call (agentverse.technical_analysis $ticker)))

!(import_prolog_functions_from_file (library OmegaClaw-Core ./src/skills.pl) (run_cmd first_char))

(= (shell $cmd)
   (if (isTelegram)
        (Error shell "DENIED: Shell access is disabled in Telegram mode.")
       (let $temp (cut) (translatePredicate (run_cmd $cmd $out)) $out)))

(= (metta $str)
   (if (isTelegram)
        (Error metta "DENIED: MeTTa evaluation is disabled in Telegram mode.")
       (let $code (sread $str)
            (repr (swrite (eval $code))))))

(= (pin $x)
   PIN-SUCCESS)
