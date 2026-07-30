; Health/status endpoint plugin.
;
; Starts the HTTP server (health.py) and reports the agent's state once per
; loop iteration through the heartbeat API, so the core loop needs no changes.
; The server, routes and staleness logic all live in health.py; this file only
; wires it to the loop. The heartbeat listener passes the iteration number and
; the current status (derived from &loops: >0 means the loop is working).
(= (loadOmegaClawPlugin)
   (progn
     (py-call (health.start))
     (add-heartbeat-listener health-endpoint
       (|-> ($iter)
         (py-call (health.heartbeat $iter
           (if (> (get-state &loops) 0) "thinking" "sleeping")))))
     ()))
