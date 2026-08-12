!(import! &self ./tests/lib/utils)
!(import! &self ../src/config.py)
!(import! &self ./src/config)
!(import! &self ../src/helper.py)
!(import! &self ./src/utils)
!(import! &self ./src/skills)
!(import! &self ./src/loop)

; Keep listener tests independent of the Python logger and channel modules.
(= (log $type $module $message)
   (if (and (== $type INFO) (== $module "heartbeat"))
       (let $count (get-state &test_heartbeat_log_count)
         (change-state! &test_heartbeat_log_count (+ $count 1)))
       ()))
(= (send $message)
   (progn
     (let $count (get-state &test_heartbeat_send_count)
       (change-state! &test_heartbeat_send_count (+ $count 1)))
     (change-state! &test_heartbeat_last_message $message)))

(= (command-line) ())
!(initConfig)
!(initLoop)
!(test (heartbeatLogInterval) 100)

!(test (progn
         (add-skill test-skill "This is a test skill" (test_arg))
         (expression-count-item (getSkills) "- This is a test skill: test-skill test_arg"))
       1)

!(test (progn
         (remove-skill test-skill)
         (expression-count-item (getSkills) "- This is a test skill: test-skill test_arg"))
       0)

!(test (progn
         (add-prompt-extension test-prompt "TEST PROMPT EXTENSION")
         (contains-text (getPromptExtensions) "TEST PROMPT EXTENSION"))
       True)

!(test (progn
         (remove-prompt-extension test-prompt)
         (contains-text (getPromptExtensions) "TEST PROMPT EXTENSION"))
       False)

(= (on-heartbeat $iter)
   (let $count (get-state &test_heartbeat_counter)
     (change-state! &test_heartbeat_counter (+ $count $iter))))

!(test (progn
         (change-state! &test_heartbeat_counter 0)
         (add-heartbeat-listener test-heartbeat (|-> ($iter) (on-heartbeat $iter)))
         (heartbeat 1)
         (heartbeat 2)
         (remove-heartbeat-listener test-heartbeat)
         (get-state &test_heartbeat_counter))
       3)

!(test (progn
         (change-state! &test_heartbeat_counter 0)
         (add-heartbeat-listener test-heartbeat (|-> ($iter) (on-heartbeat $iter)))
         (remove-heartbeat-listener test-heartbeat)
         (heartbeat 1)
         (get-state &test_heartbeat_counter))
       0)

; Default health checks fire on every configured interval.
!(test (progn
         (change-state! &test_heartbeat_send_count 0)
         (change-state! &test_heartbeat_log_count 0)
         (heartbeat 100)
         (heartbeat 200)
         (and (== (get-state &test_heartbeat_send_count) 2)
              (and (== (get-state &test_heartbeat_log_count) 2)
                   (== (get-state &test_heartbeat_last_message)
                       "Heartbeat: agent alive - iteration 200"))))
       True)
!(test (progn
         (heartbeat 50)
         (get-state &test_heartbeat_send_count))
       2)

; A failing listener does not stop the default health check or healthy listeners.
!(test (progn
         (change-state! &test_heartbeat_counter 0)
         (change-state! &test_heartbeat_send_count 0)
         (add-heartbeat-listener healthy-heartbeat (|-> ($iter) (on-heartbeat $iter)))
         (add-heartbeat-listener failing-heartbeat (|-> ($iter) (/ 1 0)))
         (heartbeat 100)
         (remove-heartbeat-listener healthy-heartbeat)
         (remove-heartbeat-listener failing-heartbeat)
         (and (== (get-state &test_heartbeat_counter) 100)
              (== (get-state &test_heartbeat_send_count) 1)))
       True)
