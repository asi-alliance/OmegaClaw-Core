(= (getSkills)
   (if (isTelegram)
       (;TELEGRAM ALLOWED SKILLS:
           "- Remember a particular string: (remember string)"
           "- Query long-term embedding memory: (query string)"
           "- Pin a short-term working memory item: (pin string)"
           "- Send message to user: (send string)"
        "- Search the web: (search string)")
       (;DEFAULT ALLOWED SKILLS:
        "- Remember a particular string: (remember string)"
        "- Query long-term embedding memory: (query string)"
        "- Pin a short-term working memory item: (pin string)"
        "- Execute shell command: (shell string)"
        "- Read file to string: (read-file filename)"
        "- Write string to file: (write-file filename string)"
        "- Append line to file: (append-file filename string)"
        "- Send message to user: (send string)"
        "- Search the web: (search string)"
        "- Execute MeTTa expression: (metta string)")))

(= (read-file $file)
   (if (isTelegram)
    (Error read-file "DENIED: File access is disabled in Telegram mode.")
       (progn (translatePredicate (exists_file $file))
              (translatePredicate (read_file_to_string $file $content ()))
              $content)))

(= (write-file $file $str)
   (if (isTelegram)
        (Error write-file "DENIED: File mutation is disabled in Telegram mode.")
       (progn (translatePredicate (open $file write $Out))
              (translatePredicate (write $Out $str))
              (translatePredicate (close $Out))
              True)))

(= (append-file $file $str)
   (if (isTelegram)
        (Error append-file "DENIED: File mutation is disabled in Telegram mode.")
        (progn (translatePredicate (exists_file $file))
              (translatePredicate (open $file append $Out))
              (translatePredicate (write $Out $str))
              (translatePredicate (nl $Out)),
              (translatePredicate (close $Out))
              True)))

!(import_prolog_functions_from_file (library mettaclaw ./src/skills.pl) (run_cmd first_char))

(= (shell $cmd)
   (if (isTelegram)
        (Error shell "DENIED: Shell access is disabled in Telegram mode.")
       (let $temp (cut) (translatePredicate (run_cmd $cmd $out)) $out)))

(= (metta $str)
   (if (isTelegram)
        (Error metta "DENIED: MeTTa evaluation is disabled in Telegram mode.")
       (let $code (sread $str) (eval $code))))
