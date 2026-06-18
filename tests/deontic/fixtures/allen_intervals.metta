; Test: All 13 Allen interval relations
; Coverage: before, after, meets, met-by, overlaps, overlapped-by,
;           starts, started-by, within, contains, finishes, finished-by, equals
;
; Each relation is tested with a pair of temporal facts and a rule
; with the corresponding Allen constraint. Negative tests verify
; non-matching relations do NOT fire.

; =========================================================================
; 1. BEFORE — A ends before B starts (gap between)
;    A: [100,200]  B: [300,400]
; =========================================================================
(given (during (ev-bf-a) 100 200))
(given (during (ev-bf-b) 300 400))
(normally r-before
    (and (during (ev-bf-a) ?T) (during (ev-bf-b) ?S) (before ?T ?S))
    (result-before))

; EXPECT: +d result-before

; Negative: A is NOT after B
(normally r-before-neg
    (and (during (ev-bf-a) ?T) (during (ev-bf-b) ?S) (after ?T ?S))
    (neg-before))
; EXPECT-NOT: +d neg-before

; =========================================================================
; 2. AFTER — A starts after B ends (inverse of before)
;    A: [300,400]  B: [100,200]
; =========================================================================
(given (during (ev-af-a) 300 400))
(given (during (ev-af-b) 100 200))
(normally r-after
    (and (during (ev-af-a) ?T) (during (ev-af-b) ?S) (after ?T ?S))
    (result-after))

; EXPECT: +d result-after

; =========================================================================
; 3. MEETS — A ends exactly when B starts
;    A: [100,200]  B: [200,300]
; =========================================================================
(given (during (ev-mt-a) 100 200))
(given (during (ev-mt-b) 200 300))
(normally r-meets
    (and (during (ev-mt-a) ?T) (during (ev-mt-b) ?S) (meets ?T ?S))
    (result-meets))

; EXPECT: +d result-meets

; Negative: meets requires exact endpoint equality; before should fail
(normally r-meets-neg
    (and (during (ev-mt-a) ?T) (during (ev-mt-b) ?S) (before ?T ?S))
    (neg-meets))
; EXPECT-NOT: +d neg-meets

; =========================================================================
; 4. MET-BY — A starts exactly when B ends (inverse of meets)
;    A: [200,300]  B: [100,200]
; =========================================================================
(given (during (ev-mb-a) 200 300))
(given (during (ev-mb-b) 100 200))
(normally r-met-by
    (and (during (ev-mb-a) ?T) (during (ev-mb-b) ?S) (met-by ?T ?S))
    (result-met-by))

; EXPECT: +d result-met-by

; =========================================================================
; 5. OVERLAPS — A starts before B, A ends during B
;    A: [100,300]  B: [200,400]
; =========================================================================
(given (during (ev-ov-a) 100 300))
(given (during (ev-ov-b) 200 400))
(normally r-overlaps
    (and (during (ev-ov-a) ?T) (during (ev-ov-b) ?S) (overlaps ?T ?S))
    (result-overlaps))

; EXPECT: +d result-overlaps

; Negative: A does NOT start B (different start times)
(normally r-overlaps-neg
    (and (during (ev-ov-a) ?T) (during (ev-ov-b) ?S) (starts ?T ?S))
    (neg-overlaps))
; EXPECT-NOT: +d neg-overlaps

; =========================================================================
; 6. OVERLAPPED-BY — B starts before A, B ends during A (inverse of overlaps)
;    A: [200,400]  B: [100,300]
; =========================================================================
(given (during (ev-ob-a) 200 400))
(given (during (ev-ob-b) 100 300))
(normally r-overlapped-by
    (and (during (ev-ob-a) ?T) (during (ev-ob-b) ?S) (overlapped-by ?T ?S))
    (result-overlapped-by))

; EXPECT: +d result-overlapped-by

; =========================================================================
; 7. STARTS — A and B start together, A ends before B
;    A: [100,200]  B: [100,400]
; =========================================================================
(given (during (ev-st-a) 100 200))
(given (during (ev-st-b) 100 400))
(normally r-starts
    (and (during (ev-st-a) ?T) (during (ev-st-b) ?S) (starts ?T ?S))
    (result-starts))

; EXPECT: +d result-starts

; =========================================================================
; 8. STARTED-BY — A and B start together, B ends before A (inverse of starts)
;    A: [100,400]  B: [100,200]
; =========================================================================
(given (during (ev-sb-a) 100 400))
(given (during (ev-sb-b) 100 200))
(normally r-started-by
    (and (during (ev-sb-a) ?T) (during (ev-sb-b) ?S) (started-by ?T ?S))
    (result-started-by))

; EXPECT: +d result-started-by

; =========================================================================
; 9. WITHIN (during) — A is strictly contained within B
;    A: [200,300]  B: [100,400]
; =========================================================================
(given (during (ev-wi-a) 200 300))
(given (during (ev-wi-b) 100 400))
(normally r-within
    (and (during (ev-wi-a) ?T) (during (ev-wi-b) ?S) (within ?T ?S))
    (result-within))

; EXPECT: +d result-within

; Negative: A is NOT equal to B (different bounds)
(normally r-within-neg
    (and (during (ev-wi-a) ?T) (during (ev-wi-b) ?S) (equals ?T ?S))
    (neg-within))
; EXPECT-NOT: +d neg-within

; =========================================================================
; 10. CONTAINS — A strictly contains B (inverse of within)
;     A: [100,400]  B: [200,300]
; =========================================================================
(given (during (ev-cn-a) 100 400))
(given (during (ev-cn-b) 200 300))
(normally r-contains
    (and (during (ev-cn-a) ?T) (during (ev-cn-b) ?S) (contains ?T ?S))
    (result-contains))

; EXPECT: +d result-contains

; =========================================================================
; 11. FINISHES — A starts after B, both end together
;     A: [300,400]  B: [100,400]
; =========================================================================
(given (during (ev-fn-a) 300 400))
(given (during (ev-fn-b) 100 400))
(normally r-finishes
    (and (during (ev-fn-a) ?T) (during (ev-fn-b) ?S) (finishes ?T ?S))
    (result-finishes))

; EXPECT: +d result-finishes

; =========================================================================
; 12. FINISHED-BY — B starts after A, both end together (inverse of finishes)
;     A: [100,400]  B: [300,400]
; =========================================================================
(given (during (ev-fb-a) 100 400))
(given (during (ev-fb-b) 300 400))
(normally r-finished-by
    (and (during (ev-fb-a) ?T) (during (ev-fb-b) ?S) (finished-by ?T ?S))
    (result-finished-by))

; EXPECT: +d result-finished-by

; =========================================================================
; 13. EQUALS — A and B have identical start and end times
;     A: [100,400]  B: [100,400]
; =========================================================================
(given (during (ev-eq-a) 100 400))
(given (during (ev-eq-b) 100 400))
(normally r-equals
    (and (during (ev-eq-a) ?T) (during (ev-eq-b) ?S) (equals ?T ?S))
    (result-equals))

; EXPECT: +d result-equals

; Negative: equal intervals do NOT satisfy before
(normally r-equals-neg
    (and (during (ev-eq-a) ?T) (during (ev-eq-b) ?S) (before ?T ?S))
    (neg-equals))
; EXPECT-NOT: +d neg-equals
