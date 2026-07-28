!(import! &self ./tests/lib/utils)
!(import! &self ./src/utils)
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

!(test (progn
         (add-prompt-extension test-prompt "TEST PROMPT EXTENSION")
         (contains-text (getPromptExtensions) "TEST PROMPT EXTENSION"))
       True)

!(test (progn
         (remove-prompt-extension test-prompt)
         (contains-text (getPromptExtensions) "TEST PROMPT EXTENSION"))
       False)
