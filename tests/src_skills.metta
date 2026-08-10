!(import! &self ./tests/lib/utils)
!(import! &self ./src/utils)
!(import! &self ../src/action_risk.py)
!(import! &self ./src/skills)
!(import! &self ./src/loop)

!(test (progn
         (add-skill test-skill "This is a test skill" (test_arg))
         (expression-count-item (getSkills) "- This is a test skill: test-skill test_arg"))
       1)

!(test (progn
         (remove-skill test-skill)
         (expression-count-item (getSkills) "- This is a test skill: test-skill test_arg"))
       0)

!(test (expression-count-item
         (getSkills)
         "- Advisory deterministic risk classification for an intended action; this does not execute or automatically intercept the action: action-risk-check skill_name target_or_argument")
       1)

!(test (contains-text
         (action-risk-check "read-file" "public/readme.txt")
         "decision=allow, risk=low, reason=read-only")
       True)

!(test (contains-text
         (action-risk-check "shell" "docker volume rm omegaclaw-memory")
         "decision=block, risk=critical, reason=destructive-action")
       True)

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
