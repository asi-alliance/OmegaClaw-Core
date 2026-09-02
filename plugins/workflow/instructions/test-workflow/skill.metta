(skill test-skill "Test skill to demonstrate workflow by sending message to the user" (message_in_quotes))

(= (test-skill $message)
   (send $message))
