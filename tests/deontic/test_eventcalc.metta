!(import! &self (library OmegaClaw-Core lib_deontic))
; Event-Calculus obligation lifecycle — obligations as inertial fluents
; (RTEC/oPIEC, Mantenoglou & Artikis; Governatori init/term templates), via the
; happens/initiates/terminates syntax (a temporal extension). An obligation is
; initiated by an event, persists by inertia (the Event Calculus initiates/
; terminates/holdsAt frame), terminated by another event (its fulfilment).
; Maximal in-force intervals computed by one-pass amalgamation (O(n log n) in the
; number of events). A violation = the obligation still holds at its deadline.


; invoice@5 initiates O pay; pay@25 terminates it -> in force [5,25)
!(test (ec-intervals (dl-path tests/deontic/fixtures/eventcalc_demo.metta) (must pay)) ((5 25)))
!(test (ec-holds-at (dl-path tests/deontic/fixtures/eventcalc_demo.metta) (must pay) 3)  False) ; before init
!(test (ec-holds-at (dl-path tests/deontic/fixtures/eventcalc_demo.metta) (must pay) 10) True)  ; in force
!(test (ec-holds-at (dl-path tests/deontic/fixtures/eventcalc_demo.metta) (must pay) 30) False) ; discharged

; violation = obligation still in force at the deadline (not fulfilled in time)
!(test (ec-violated-at (dl-path tests/deontic/fixtures/eventcalc_demo.metta) (must pay) 20) True)  ; unpaid at 20
!(test (ec-violated-at (dl-path tests/deontic/fixtures/eventcalc_demo.metta) (must pay) 30) False) ; paid by 25

; never discharged -> open interval [5,inf); always in force / violated afterwards
!(test (ec-intervals (dl-path tests/deontic/fixtures/eventcalc_open.metta) (must pay)) ((5 inf)))
!(test (ec-holds-at (dl-path tests/deontic/fixtures/eventcalc_open.metta) (must pay) 1000) True)
!(test (ec-violated-at (dl-path tests/deontic/fixtures/eventcalc_open.metta) (must pay) 1000) True)

; the timeline renderer runs end-to-end
!(test (ec-timeline (dl-path tests/deontic/fixtures/eventcalc_demo.metta) 15) true)

!(println! test-eventcalc-done)
