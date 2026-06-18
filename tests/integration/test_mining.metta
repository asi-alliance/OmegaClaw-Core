; Process-mining tests (rule learning from event logs). These assertions pin the
; deterministic structured results — learned causal rules with their support and
; confidence, the per-case event log, and that the renderers run end to end — so
; regressions surface fast.

!(import! &self (library OmegaClaw-Core lib_directive))

; --- rule learning: linear trace step1 -> step2 -> step3 ---
; two causal pairs, full support/confidence, sorted by (body,head).
!(test (mining-rules ((dl-path tests/deontic/fixtures/mining_seq.metta)) 1 0.5)
       ((step1 step2 1 "1.00") (step2 step3 1 "1.00")))

; --- multi-trace XOR branch: start -> {pick_b | pick_c} -> join ---
; fractional confidence (start has two outgoing edges across the 2 traces).
!(test (mining-rules ((dl-path tests/deontic/fixtures/mining_branchA.metta)
                      (dl-path tests/deontic/fixtures/mining_branchB.metta)) 1 0.5)
       ((pick_b join 1 "1.00") (pick_c join 1 "1.00")
        (start pick_b 1 "0.50") (start pick_c 1 "0.50")))

; min-confidence filter drops the 0.50 edges, keeping the certain ones.
!(test (mining-rules ((dl-path tests/deontic/fixtures/mining_branchA.metta)
                      (dl-path tests/deontic/fixtures/mining_branchB.metta)) 1 0.7)
       ((pick_b join 1 "1.00") (pick_c join 1 "1.00")))

; --- event log: one case per file, events in timestamp order ---
!(test (size-atom (mining-event-log ((dl-path tests/deontic/fixtures/mining_seq.metta)))) 1)
!(test (let ($id $evs) (car-atom (mining-event-log ((dl-path tests/deontic/fixtures/mining_seq.metta)))) $id)
       mining_seq)

; --- renderers run and return true (exact output shape exercised here) ---
!(test (mining-extract-print ((dl-path tests/deontic/fixtures/mining_seq.metta)) json) true)
!(test (mining-rules-print ((dl-path tests/deontic/fixtures/mining_seq.metta)) dfl 1 0.5) true)
!(test (mining-rules-print ((dl-path tests/deontic/fixtures/mining_branchA.metta)
                            (dl-path tests/deontic/fixtures/mining_branchB.metta)) summary 1 0.0) true)

!(println! test-mining-done)
