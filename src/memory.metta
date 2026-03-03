;Configured at runtime memory and history in amount of characters:
(= (maxMemory) (empty))
(= (maxRecallItems) (empty))
(= (maxHistory) (empty))

(= (initMemory)
   (progn (println! "Initializing memory")
          (configure maxMemory 2000)
          (configure maxRecallItems 5)
          (configure maxHistory 5000)))

(= (getPrompt)
   (read-file (library mettaclaw ./memory/prompt.txt)))

(= (getMemory)
   (let $ret (read-file (library mettaclaw ./memory/STM.metta))
        (last_chars $ret (maxMemory))))

(= (getHistory)
   (let $ret (read-file (library mettaclaw ./memory/history.metta))
        (last_chars $ret (maxHistory))))

(= (addToHistory $lastmessage $response $sexpr $results)
   (appendToHistory (swrite ((get_time_as_string) $lastmessage $sexpr $results))))

(= (appendToHistory $addition)
   (append-file (library mettaclaw ./memory/history.metta) $addition))

(= (remember $str)
   (progn (append-file (library mettaclaw ./memory/STM.metta) (repr ((get_time_as_string) $str)))
          (let $embedding (useGPTEmbedding (string-safe $str))
               (append-file (library mettaclaw ./memory/LTM.metta) (repr ((get_time_as_string) $str $embedding))))))

(= (query $str)
   (let* (($embedding (useGPTEmbedding (string-safe $str)))
          ($text (read-file (library mettaclaw ./memory/LTM.metta)))
          ($atoms (parse (string_concat (string_concat "(" $text) ")"))))
        (progn (let $sorted (msort (collapse (for ($date $atom $vector) $atoms ((cosine $vector $embedding) $date $atom))))
                    (let $u (collapse (for ($sim $date $atom) (take (maxRecallItems) (reverse $sorted))
                                   ($date $atom)))
                                   (repr $u))))))
