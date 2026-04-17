;Configured at runtime memory and history in amount of characters:
(= (maxFeedback) (empty))
(= (maxRecallItems) (empty))
(= (maxEpisodeRecallLines) (empty))
(= (maxHistory) (empty))

(= (initMemory)
   (progn (println! "Initializing memory")
          (configure maxFeedback 50000)
          (configure maxRecallItems 20)
          (configure maxEpisodeRecallLines 20)
          (configure maxHistory 30000)
          (configure embeddingprovider Local) ;OpenAI or Local
          (if (== (embeddingprovider) Local)
              (py-call (lib_llm_ext.initLocalEmbedding)) _)))

(= (getPrompt)
   (if (isTelegram)
       (read-file-raw (library OmegaClaw-Core ./memory/tg_prompt.txt))
       (read-file-raw (library OmegaClaw-Core ./memory/prompt.txt))))

(= (getHistory)
   (let $ret (read-file-raw (library OmegaClaw-Core ./memory/history.metta))
        (last_chars $ret (maxHistory))))

(= (addToHistory $lastmessage $response $sexpr $msgnew)
   (if $msgnew
       (if (== (get-state &error) ())
           (appendToHistory ((get_time_as_string) (newline) "HUMAN_MESSAGE: " $lastmessage (newline) $response (newline)))
           (appendToHistory ((get_time_as_string) (newline) "HUMAN_MESSAGE: " $lastmessage (newline) $response (newline) ERROR_FEEDBACK: (get-state &error))))
       (if (== (get-state &error) ())
           (appendToHistory ((get_time_as_string) (newline) $response (newline)))
           (appendToHistory ((get_time_as_string) (newline) $response (newline) ERROR_FEEDBACK: (get-state &error))))))

(= (appendToHistory $addition)
   (append-file-raw (library OmegaClaw-Core ./memory/history.metta) (swrite $addition)))

(= (remember $str)
   (if (isTelegram)
       (if (py-call (config_helper.is_memory_forbidden $str))
           (Error remember "Refused: Sensitive traits/profiling blocked.")
           (progn (py-call (lib_chromadb.remember $str (embed $str) (get_time_as_string)))
                  REMEMBER-SUCCESS))
       (progn (py-call (lib_chromadb.remember $str (embed $str) (get_time_as_string)))
              REMEMBER-SUCCESS)))

(= (query $str)
   (py-call (lib_chromadb.query (embed (string-safe $str)) (maxRecallItems))))

(= (episodes $time)
   (py-call (helper.around_time $time (maxEpisodeRecallLines))))
