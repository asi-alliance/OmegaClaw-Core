(= (getSkills)
   (;INTERNAL:
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
    "Additionally |- also works for revision, to merge evidence even when the term of both premises is the same."))


(= (read-file $file)
   (progn (translatePredicate (exists_file $file))
          (translatePredicate (read_file_to_string $file $content ()))
          $content))

(= (write-file $file $str)
   (progn (translatePredicate (open $file write $Out))
          (translatePredicate (write $Out $str))
          (translatePredicate (close $Out))
          True))

(= (append-file $file $str)
   (progn (translatePredicate (exists_file $file))
          (translatePredicate (open $file append $Out))
          (translatePredicate (write $Out $str))
          (translatePredicate (nl $Out)),
          (translatePredicate (close $Out))
          True))

(= (tavily-search $query)
   (py-call (agentverse.tavily_search $query)))

(= (technical-analysis $ticker)
   (py-call (agentverse.technical_analysis $ticker)))

!(import_prolog_functions_from_file (library omegaclaw ./src/skills.pl) (shell first_char))

(= (metta $str)
   (let $code (sread $str)
        (eval $code)))
