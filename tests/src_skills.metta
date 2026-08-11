!(import! &self ./tests/lib/utils)
!(import! &self ../src/config.py)
!(import! &self ./src/config)
!(import! &self ./src/utils)
!(import! &self ./src/skills)
!(import! &self ./src/loop)

; Keep listener tests independent of the Python logging module.
(= (log $type $module $message)
   (if (and (== $type INFO) (== $module "heartbeat"))
       (let $count (get-state &test_heartbeat_log_count)
         (change-state! &test_heartbeat_log_count (+ $count 1)))
       ()))

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

; Default logger fires on multiples of heartbeatLogInterval, silent otherwise
!(test (progn
         (change-state! &test_heartbeat_log_count 0)
         (heartbeat 100)
         (get-state &test_heartbeat_log_count))
       1)
!(test (progn
         (heartbeat 50)
         (get-state &test_heartbeat_log_count))
       1)
