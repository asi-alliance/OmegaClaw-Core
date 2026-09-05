!(import! &self ./tests/lib/utils)
!(import! &self ../src/helper.py)
!(import! &self ./src/utils)
!(import! &self (library lib_llm.py))
!(import! &self (library lib_llm.metta))
!(import! &self ./src/loop)

; Stub the sections contextVolatileTail reads so the ordering is the only variable.
(= (getHistory) "HIST")
(= (maxFeedback) 100)
!(change-state! &lastresults "RESULT")

; Importing ./src/loop adds the (empty) placeholder; drop it so the flag has a
; single, deterministic value for each case (initLoop's configure does the same).
!(remove-atom &self (= (stableContextOrder) (empty)))

; --- flag OFF (default): tail must stay byte-for-byte identical to the old layout ---
!(add-atom &self (= (stableContextOrder) False))
!(test (contextVolatileTail)
       (py-str (" LAST_SKILL_USE_RESULTS: " (last_chars (get-state &lastresults) (maxFeedback))
                " HISTORY: " (getHistory))))
!(remove-atom &self (= (stableContextOrder) False))

; --- flag ON: HISTORY moves ahead of the volatile results section ---
!(add-atom &self (= (stableContextOrder) True))
!(test (contextVolatileTail)
       (py-str (" HISTORY: " (getHistory)
                " LAST_SKILL_USE_RESULTS: " (last_chars (get-state &lastresults) (maxFeedback)))))
!(remove-atom &self (= (stableContextOrder) True))
