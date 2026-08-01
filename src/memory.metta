;Configured at runtime memory and history in amount of characters:
(= (maxFeedback) (empty))
(= (maxRecallItems) (empty))
(= (maxEpisodeRecallLines) (empty))
(= (maxHistory) (empty))
(= (embeddingprovider) (empty))

(= (initMemory)
   (progn (log INFO "memory" "Initializing memory")
          (configure maxFeedback 50000)
          (configure maxRecallItems 20)
          (configure maxEpisodeRecallLines 20)
          (configure maxHistory 30000)
          (configure embeddingprovider Local) ;OpenAI or Local
          (if (== (embeddingprovider) Local)
              (py-call (lib_llm_ext.initLocalEmbedding)) _)))

(= (getPrompt $provider)
   (let $model_prompt
         (library OmegaClaw-Core (py-str ("./memory/prompt_" $provider ".txt")))
     (if (exists-file $model_prompt)
         (read-file $model_prompt)
         (let $default_prompt ;Safely read the default prompt. Return an empty string if the file does not exist.
               (library OmegaClaw-Core ./memory/prompt.txt)
           (if (exists-file $default_prompt)
               (read-file $default_prompt)
               "")))))

(= (getContextFramePrompt)
   (let $path
         (library OmegaClaw-Core ./memory/prompt_context_frame.txt)
      (if (exists-file $path)
          (read-file $path)
          "")))

(= (getHistory)
   (let $history_file
         (library OmegaClaw-Core ./memory/history.metta)
     (if (exists-file $history_file) ;Safely read the history. Return an empty string if the file does not exist.
         (read_file_tail $history_file (maxHistory))
         "")))

(= (addToHistory $lastmessage $response $sexpr $msgnew)
   (if $msgnew
       (if (== (get-state &error) ())
           (appendToHistory ((get_time_as_string) (newline) "HUMAN_MESSAGE: " $lastmessage (newline) $response (newline)))
           (appendToHistory ((get_time_as_string) (newline) "HUMAN_MESSAGE: " $lastmessage (newline) $response (newline) ERROR_FEEDBACK: (get-state &error))))
       (if (== (get-state &error) ())
           (appendToHistory ((get_time_as_string) (newline) $response (newline)))
           (appendToHistory ((get_time_as_string) (newline) $response (newline) ERROR_FEEDBACK: (get-state &error))))))

(= (embed $str)
   (if (== (embeddingprovider) Local)
       (py-call (lib_llm_ext.useLocalEmbedding (string-safe $str)))
       (py-call (rag.openai_embed (string-safe $str)))))

(= (appendToHistory $addition)
   (append-file-raw (library OmegaClaw-Core ./memory/history.metta) (swrite $addition)))

(= (remember $str)
   (progn (py-call (lib_chromadb.remember $str (embed $str) (get_time_as_string)))
          REMEMBER-SUCCESS))

(= (query $str)
   (py-call (lib_chromadb.query (embed $str) (maxRecallItems))))

(= (episodes $time)
   (py-call (helper.around_time $time (maxEpisodeRecallLines))))