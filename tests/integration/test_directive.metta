; Task-coordination layer tests: extraction (next / status / board / summary /
; info), state classification, and the full claim / complete / unclaim / block /
; unblock lifecycle drilled on a temp plan copy. Goldens are the expected
; coordination results for each fixture.

!(import! &self (library OmegaClaw-Core lib_directive))

; ---------------------------------------------------------------
; extraction + next on basic-tasks.metta
; expected next-actions: models@coder, auth@coder, auth@reviewer
; ---------------------------------------------------------------
!(test (directive-next (dl-path tests/deontic/fixtures/basic-tasks.metta))
       (next-actions ((assign auth coder assign-to-auth-coder)
                      (assign auth reviewer assign-to-auth-reviewer)
                      (assign models coder assign-to-models-coder))))

!(test (directive-status (dl-path tests/deontic/fixtures/basic-tasks.metta))
       (status (tasks (auth crud models tests))
               (ready (auth models))
               (claimed ())
               (blocked ())
               (upstream-blocked ())
               (completed ())))

; board groups by state; summary counts; info extracts plan metadata
!(test (directive-board (dl-path tests/deontic/fixtures/basic-tasks.metta))
       (board (backlog (crud tests))
              (ready (auth models))
              (in-progress ())
              (blocked ())
              (done ())))

!(test (directive-summary (dl-path tests/deontic/fixtures/basic-tasks.metta))
       (summary (total 4) (backlog 2) (ready 2) (in-progress 0)
                (blocked 0) (done 0) (progress-pct 0)))

; info extracts the (meta plan ...) KVs; query specific values via meta-get
; (the raw KV list isn't compared directly because keys like `id`/`status`
; collide with stdlib function names under evaluation).
!(dl-run (dl-path tests/deontic/fixtures/basic-tasks.metta))
!(test (meta-get (plan-meta-kvs) title) "Basic Task Test")
!(test (meta-get (plan-meta-kvs) author) "agent:tester")
!(test (meta-get (plan-meta-kvs) missing-key) none)

; state classification precedence (a completed task is `done`, not `ready`)
!(test (let $names (directive-pos-names) (directive-task-state models $names)) ready)

; ---------------------------------------------------------------
; full lifecycle drill on a temp copy
; ---------------------------------------------------------------
!(mm_write_file "/tmp/mm_directive_drill.metta"
                (mm_read_file (dl-path tests/deontic/fixtures/basic-tasks.metta)))

; claiming an unready task fails
!(test (directive-claim "/tmp/mm_directive_drill.metta" crud tester False)
       (err not-ready crud))

; force-claim bypasses readiness; not exercised further here
; complete models -> crud becomes ready
!(test (directive-complete "/tmp/mm_directive_drill.metta" models tester)
       (completed models))
; NOTE: ready-models REMAINS concluded after completion — readiness rules do
; not retract; `next` filters completed tasks instead.
!(test (let (status $t (ready $r) $c $b $u $d)
            (directive-status "/tmp/mm_directive_drill.metta")
            $r)
       (auth crud models))

; claim crud v1
!(test (directive-claim "/tmp/mm_directive_drill.metta" crud tester False)
       (claimed crud 1))
!(test (let (status $t $r (claimed $c) $b $u $d)
            (directive-status "/tmp/mm_directive_drill.metta")
            $c)
       (crud))

; claimed task no longer in next actions
!(test (let (next-actions $as) (directive-next "/tmp/mm_directive_drill.metta")
         (filter-atom $as $a (let (assign $t $ag $l) $a (== $t crud))))
       ())

; double-claim is reported
!(test (directive-claim "/tmp/mm_directive_drill.metta" crud tester False)
       (already-claimed crud 1))

; unclaim cancels the chain (defeats state-claimed-v1)
!(test (directive-unclaim "/tmp/mm_directive_drill.metta" crud tester)
       (unclaimed crud 2))
!(test (let (status $t $r (claimed $c) $b $u $d)
            (directive-status "/tmp/mm_directive_drill.metta")
            $c)
       ())

; reclaim v3 beats the v2 unclaim chain
!(test (directive-claim "/tmp/mm_directive_drill.metta" crud tester False)
       (claimed crud 3))
!(test (let (status $t $r (claimed $c) $b $u $d)
            (directive-status "/tmp/mm_directive_drill.metta")
            $c)
       (crud))

; block auth -> blocked state; readiness untouched (plans gate via rules)
!(test (directive-block "/tmp/mm_directive_drill.metta" auth tester)
       (blocked auth 1))
!(test (let (status $t $r $c (blocked $b) $u $d)
            (directive-status "/tmp/mm_directive_drill.metta")
            $b)
       (auth))

; unblock cancels it
!(test (directive-unblock "/tmp/mm_directive_drill.metta" auth tester)
       (unblocked auth 2))
!(test (let (status $t $r $c (blocked $b) $u $d)
            (directive-status "/tmp/mm_directive_drill.metta")
            $b)
       ())

; complete remaining flow: crud done -> tests still needs auth
!(test (directive-complete "/tmp/mm_directive_drill.metta" crud tester)
       (completed crud))
!(test (directive-complete "/tmp/mm_directive_drill.metta" auth tester)
       (completed auth))
!(test (let (status $t (ready $r) $c $b $u $d)
            (directive-status "/tmp/mm_directive_drill.metta")
            $r)
       (auth crud models tests))

; finishing the last task reports plan completion
!(test (directive-complete "/tmp/mm_directive_drill.metta" tests tester)
       (completed tests plan-complete))

!(println! test-directive-done)
