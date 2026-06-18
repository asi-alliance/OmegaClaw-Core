!(import! &self (library OmegaClaw-Core lib_deontic))
; Temporal-deontic deadline obligations — Governatori, Hulstijn, Riveret & Rotolo
; (2007), "Characterising Deadlines in Temporal Modal Defeasible Logic", via the
; (deadline ...) syntax (a temporal-deontic extension). Achievement obligations
; must be fulfilled by the deadline; maintenance obligations (prohibitions) must
; hold throughout the window. Compliance is evaluated at a reference time `now`:
; fulfilled / violated / pending (deolingo's O^f / O^v / O^u), with sanctions
; triggered on violation.


; --- ACHIEVEMENT: pay by 30, actually paid at t=25 ---
; at now=40 the payment is in the past and in window -> fulfilled
!(test (deadline-status (dl-path tests/deontic/fixtures/deadline_demo.metta) 40 pay) fulfilled)
; at now=20 the payment (t=25) hasn't happened yet, deadline not passed -> pending
!(test (deadline-status (dl-path tests/deontic/fixtures/deadline_demo.metta) 20 pay) pending)

; --- ACHIEVEMENT violated: never paid, deadline 30 passed (now=40) ---
!(test (deadline-status (dl-path tests/deontic/fixtures/deadline_missed.metta) 40 pay) violated)
; ...but before the deadline it is only pending
!(test (deadline-status (dl-path tests/deontic/fixtures/deadline_missed.metta) 10 pay) pending)

; --- MAINTENANCE: no trespass yet -> pending while in window; clean past window ---
!(test (deadline-status (dl-path tests/deontic/fixtures/deadline_demo.metta) 40 trespass) pending)
!(test (deadline-status (dl-path tests/deontic/fixtures/deadline_clean.metta) 60 trespass) fulfilled)

; --- MAINTENANCE violated: trespass at t=20 in window [0,50] (a breach by now=40) ---
!(test (deadline-status (dl-path tests/deontic/fixtures/deadline_missed.metta) 40 trespass) violated)
; ...but at now=10 the breach (t=20) hasn't occurred yet -> still pending
!(test (deadline-status (dl-path tests/deontic/fixtures/deadline_missed.metta) 10 trespass) pending)

; --- the renderer runs end-to-end ---
!(test (deontic-deadlines (dl-path tests/deontic/fixtures/deadline_demo.metta) 40) true)

!(println! test-deadline-done)
