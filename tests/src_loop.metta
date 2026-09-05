!(import! &self ./tests/lib/utils)
!(import! &self ../src/helper.py)
!(import! &self ./src/utils)
!(import! &self (library lib_llm.py))
!(import! &self (library lib_llm.metta))
!(import! &self ./src/loop)

; orderContextTail is a pure function of the two section strings, so the ordering
; can be checked directly without loop state or the global flag.

; Flag off (default): the volatile results section stays ahead of HISTORY, which
; keeps the assembled prompt byte-for-byte identical to the original layout.
!(test (orderContextTail False "RESULT" "HIST")
       (py-str (" LAST_SKILL_USE_RESULTS: " "RESULT" " HISTORY: " "HIST")))

; Flag on: HISTORY moves ahead of the volatile results section.
!(test (orderContextTail True "RESULT" "HIST")
       (py-str (" HISTORY: " "HIST" " LAST_SKILL_USE_RESULTS: " "RESULT")))
